package com.chaosguard.service;

import com.chaosguard.model.Scan;
import com.chaosguard.model.Scan.ScanStatus;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.eclipse.jgit.api.CloneCommand;
import org.eclipse.jgit.api.Git;
import org.eclipse.jgit.api.errors.GitAPIException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Stream;

@Service
@RequiredArgsConstructor
@Slf4j
public class CloneService {

    private final ScanService scanService;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final RepoSanitizer repoSanitizer;

    @Value("${chaosguard.scan.clone-base-dir}")
    private String cloneBaseDir;

    @Value("${chaosguard.scan.max-repo-size-mb}")
    private long maxRepoSizeMb;

    @Value("${chaosguard.scan.max-file-count}")
    private long maxFileCount;

    @Value("${chaosguard.kafka.topics.index-events}")
    private String indexEventsTopic;

    private final List<String> ignoreExtensions = List.of(
        ".min.js", ".min.css", ".map", ".lock", ".sum", ".png", ".jpg", ".jpeg",
        ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3",
        ".pdf", ".zip", ".tar", ".gz", ".jar", ".war", ".class", ".pyc", ".so",
        ".dylib", ".dll", ".exe", ".bin"
    );

    private final List<String> ignoreDirectories = List.of(
        "node_modules", ".git", ".svn", ".hg", "vendor", "dist", "build",
        "target", "__pycache__", ".gradle", ".idea", ".vscode", ".DS_Store",
        "coverage", ".nyc_output", ".next", ".nuxt"
    );

    @KafkaListener(topics = "${chaosguard.kafka.topics.repo-clone-events}",
                   groupId = "chaosguard-gateway",
                   containerFactory = "kafkaListenerContainerFactory")
    public void handleCloneEvent(@Payload Map<String, Object> event, Acknowledgment ack) {
        String scanId = (String) event.get("scanId");
        String repoUrl = (String) event.get("repoUrl");
        String branch = (String) event.get("branch");
        String tier = (String) event.get("tier");

        log.info("Received clone event for scan {} repo {}", scanId, repoUrl);

        UUID scanUuid = UUID.fromString(scanId);

        try {
            scanService.updateScanStatus(scanUuid, ScanStatus.CLONING, null);

            File cloneDir = new File(cloneBaseDir, scanId);
            if (cloneDir.exists()) {
                deleteDirectory(cloneDir.toPath());
            }
            cloneDir.mkdirs();

            cloneRepository(repoUrl, branch, cloneDir);

            // Sanitize repository to prevent malicious content
            repoSanitizer.sanitize(cloneDir.toPath());

            long repoSizeBytes = calculateDirectorySize(cloneDir.toPath());
            long repoSizeMb = repoSizeBytes / (1024 * 1024);
            if (repoSizeMb > maxRepoSizeMb) {
                deleteDirectory(cloneDir.toPath());
                throw new IllegalStateException(
                        String.format("Repository size %dMB exceeds limit of %dMB", repoSizeMb, maxRepoSizeMb));
            }

            Map<String, Object> metadata = extractMetadata(cloneDir);
            long fileCount = (long) metadata.get("totalFiles");
            if (fileCount > maxFileCount) {
                deleteDirectory(cloneDir.toPath());
                throw new IllegalStateException(
                        String.format("File count %d exceeds limit of %d", fileCount, maxFileCount));
            }

            metadata.put("repoSizeMb", repoSizeMb);
            scanService.updateScanMetadata(scanUuid, metadata);
            scanService.updateScanStatus(scanUuid, ScanStatus.CLONING_COMPLETE, null);

            Map<String, Object> indexEvent = new HashMap<>();
            indexEvent.put("scanId", scanId);
            indexEvent.put("repoUrl", repoUrl);
            indexEvent.put("branch", branch);
            indexEvent.put("tier", tier);
            indexEvent.put("clonePath", cloneDir.getAbsolutePath());
            indexEvent.put("metadata", metadata);
            indexEvent.put("timestamp", Instant.now().toString());

            kafkaTemplate.send(indexEventsTopic, scanId, indexEvent);
            log.info("Published index event for scan {}", scanId);

            ack.acknowledge();

        } catch (Exception e) {
            log.error("Clone failed for scan {}: {}", scanId, e.getMessage(), e);
            scanService.updateScanStatus(scanUuid, ScanStatus.FAILED, "Clone failed: " + e.getMessage());
            ack.acknowledge();
        }
    }

    private void cloneRepository(String repoUrl, String branch, File targetDir) throws GitAPIException {
        log.info("Cloning {} branch {} to {}", repoUrl, branch, targetDir.getAbsolutePath());

        CloneCommand cloneCommand = Git.cloneRepository()
                .setURI(repoUrl)
                .setDirectory(targetDir)
                .setBranch(branch)
                .setDepth(1)
                .setCloneAllBranches(false);

        try (Git git = cloneCommand.call()) {
            log.info("Clone completed for {}", repoUrl);
        }
    }

    private Map<String, Object> extractMetadata(File repoDir) throws IOException {
        Map<String, Object> metadata = new HashMap<>();
        Map<String, Long> languageStats = new HashMap<>();
        List<String> directories = new ArrayList<>();
        AtomicLong totalFiles = new AtomicLong(0);
        AtomicLong filteredFiles = new AtomicLong(0);
        List<String> sourceFiles = new ArrayList<>();

        Files.walkFileTree(repoDir.toPath(), new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                String dirName = dir.getFileName().toString();
                if (ignoreDirectories.contains(dirName)) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                String relativePath = repoDir.toPath().relativize(dir).toString();
                if (!relativePath.isEmpty()) {
                    directories.add(relativePath);
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                totalFiles.incrementAndGet();
                String fileName = file.getFileName().toString();
                String extension = getFileExtension(fileName);

                if (shouldIgnoreFile(fileName, extension)) {
                    filteredFiles.incrementAndGet();
                    return FileVisitResult.CONTINUE;
                }

                String language = mapExtensionToLanguage(extension);
                if (language != null) {
                    languageStats.merge(language, 1L, Long::sum);
                }

                String relativePath = repoDir.toPath().relativize(file).toString();
                sourceFiles.add(relativePath);

                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFileFailed(Path file, IOException exc) {
                log.warn("Failed to visit file: {}", file);
                return FileVisitResult.CONTINUE;
            }
        });

        metadata.put("languages", languageStats);
        metadata.put("totalFiles", totalFiles.get());
        metadata.put("filteredFiles", filteredFiles.get());
        metadata.put("sourceFileCount", sourceFiles.size());
        metadata.put("directoryCount", directories.size());
        metadata.put("topDirectories", directories.stream().limit(50).toList());
        metadata.put("primaryLanguage", languageStats.entrySet().stream()
                .max(Map.Entry.comparingByValue())
                .map(Map.Entry::getKey)
                .orElse("unknown"));

        return metadata;
    }

    private boolean shouldIgnoreFile(String fileName, String extension) {
        if (extension.isEmpty()) {
            return false;
        }
        return ignoreExtensions.contains("." + extension);
    }

    private String getFileExtension(String fileName) {
        int lastDot = fileName.lastIndexOf('.');
        if (lastDot == -1 || lastDot == fileName.length() - 1) {
            return "";
        }
        return fileName.substring(lastDot + 1).toLowerCase();
    }

    private String mapExtensionToLanguage(String extension) {
        return switch (extension) {
            case "java" -> "Java";
            case "py" -> "Python";
            case "js" -> "JavaScript";
            case "ts" -> "TypeScript";
            case "tsx" -> "TypeScript (React)";
            case "jsx" -> "JavaScript (React)";
            case "go" -> "Go";
            case "rs" -> "Rust";
            case "rb" -> "Ruby";
            case "php" -> "PHP";
            case "cs" -> "C#";
            case "cpp", "cc", "cxx" -> "C++";
            case "c", "h" -> "C";
            case "swift" -> "Swift";
            case "kt", "kts" -> "Kotlin";
            case "scala" -> "Scala";
            case "sql" -> "SQL";
            case "sh", "bash" -> "Shell";
            case "yml", "yaml" -> "YAML";
            case "json" -> "JSON";
            case "xml" -> "XML";
            case "html", "htm" -> "HTML";
            case "css", "scss", "sass", "less" -> "CSS";
            case "tf", "hcl" -> "Terraform";
            case "dockerfile" -> "Dockerfile";
            case "md" -> "Markdown";
            case "sol" -> "Solidity";
            case "r" -> "R";
            case "dart" -> "Dart";
            case "ex", "exs" -> "Elixir";
            default -> null;
        };
    }

    private long calculateDirectorySize(Path path) throws IOException {
        AtomicLong size = new AtomicLong(0);
        Files.walkFileTree(path, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                size.addAndGet(attrs.size());
                return FileVisitResult.CONTINUE;
            }
        });
        return size.get();
    }

    private void deleteDirectory(Path path) throws IOException {
        if (Files.exists(path)) {
            Files.walkFileTree(path, new SimpleFileVisitor<>() {
                @Override
                public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                    Files.delete(file);
                    return FileVisitResult.CONTINUE;
                }

                @Override
                public FileVisitResult postVisitDirectory(Path dir, IOException exc) throws IOException {
                    Files.delete(dir);
                    return FileVisitResult.CONTINUE;
                }
            });
        }
    }
}
