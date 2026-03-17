package com.chaosguard.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

@Service
@Slf4j
public class RepoSanitizer {

    private static final long MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB per file
    private static final int MAX_DIR_DEPTH = 20;
    private static final long MAX_TOTAL_SIZE = 500L * 1024 * 1024; // 500MB total

    public void sanitize(Path cloneDir) throws IOException {
        log.info("Sanitizing repository at {}", cloneDir);

        // 1. Delete .git/hooks/ to prevent hook execution
        deleteGitHooks(cloneDir);

        // 2. Remove symlinks
        removeSymlinks(cloneDir);

        // 3. Enforce per-file size limit and directory depth
        enforceFileLimits(cloneDir);

        // 4. Validate total size
        validateTotalSize(cloneDir);

        log.info("Repository sanitization complete for {}", cloneDir);
    }

    private void deleteGitHooks(Path cloneDir) throws IOException {
        Path hooksDir = cloneDir.resolve(".git").resolve("hooks");
        if (Files.exists(hooksDir)) {
            Files.walkFileTree(hooksDir, new SimpleFileVisitor<>() {
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
            log.info("Deleted .git/hooks/ directory");
        }
    }

    private void removeSymlinks(Path cloneDir) throws IOException {
        AtomicInteger removed = new AtomicInteger(0);
        Files.walkFileTree(cloneDir, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                if (Files.isSymbolicLink(file)) {
                    Files.delete(file);
                    removed.incrementAndGet();
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) throws IOException {
                if (Files.isSymbolicLink(dir)) {
                    Files.delete(dir);
                    removed.incrementAndGet();
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }
        });
        if (removed.get() > 0) {
            log.warn("Removed {} symlinks from repository", removed.get());
        }
    }

    private void enforceFileLimits(Path cloneDir) throws IOException {
        AtomicInteger oversized = new AtomicInteger(0);
        AtomicInteger tooDeep = new AtomicInteger(0);

        Files.walkFileTree(cloneDir, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) throws IOException {
                int depth = cloneDir.relativize(dir).getNameCount();
                if (depth > MAX_DIR_DEPTH) {
                    // Delete directories that are too deep
                    deleteRecursive(dir);
                    tooDeep.incrementAndGet();
                    return FileVisitResult.SKIP_SUBTREE;
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                if (attrs.size() > MAX_FILE_SIZE) {
                    Files.delete(file);
                    oversized.incrementAndGet();
                }
                return FileVisitResult.CONTINUE;
            }
        });

        if (oversized.get() > 0) {
            log.warn("Removed {} files exceeding {}MB size limit", oversized.get(), MAX_FILE_SIZE / (1024 * 1024));
        }
        if (tooDeep.get() > 0) {
            log.warn("Removed {} directories exceeding depth limit of {}", tooDeep.get(), MAX_DIR_DEPTH);
        }
    }

    private void validateTotalSize(Path cloneDir) throws IOException {
        AtomicLong totalSize = new AtomicLong(0);
        Files.walkFileTree(cloneDir, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                totalSize.addAndGet(attrs.size());
                return FileVisitResult.CONTINUE;
            }
        });

        long sizeMb = totalSize.get() / (1024 * 1024);
        if (totalSize.get() > MAX_TOTAL_SIZE) {
            throw new IOException(String.format(
                    "Repository total size %dMB exceeds maximum of %dMB after sanitization",
                    sizeMb, MAX_TOTAL_SIZE / (1024 * 1024)));
        }
    }

    private void deleteRecursive(Path path) throws IOException {
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
