package com.chaosguard.controller;

import com.chaosguard.model.AuthRequest;
import com.chaosguard.model.AuthResponse;
import com.chaosguard.security.JwtTokenProvider;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@Slf4j
public class AuthController {

    private final JwtTokenProvider tokenProvider;
    private final PasswordEncoder passwordEncoder;

    /**
     * In-memory user store. Each entry maps username -> {encodedPassword, roles}.
     * Seeded with a default admin user on first access.
     */
    private final Map<String, UserRecord> userStore = new ConcurrentHashMap<>();

    private record UserRecord(String encodedPassword, List<String> roles) {}

    private void ensureDefaultUser() {
        userStore.computeIfAbsent("admin", k ->
                new UserRecord(passwordEncoder.encode("admin"), List.of("ADMIN", "USER")));
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody AuthRequest request) {
        ensureDefaultUser();

        if (request.getUsername() == null || request.getUsername().isBlank()
                || request.getPassword() == null || request.getPassword().isBlank()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "Username and password are required"));
        }

        UserRecord user = userStore.get(request.getUsername());
        if (user == null || !passwordEncoder.matches(request.getPassword(), user.encodedPassword())) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "Invalid username or password"));
        }

        String token = tokenProvider.generateToken(request.getUsername(), user.roles());
        log.info("User '{}' logged in successfully", request.getUsername());

        return ResponseEntity.ok(new AuthResponse(token, request.getUsername(), user.roles()));
    }

    @PostMapping("/register")
    public ResponseEntity<?> register(@RequestBody AuthRequest request) {
        ensureDefaultUser();

        if (request.getUsername() == null || request.getUsername().isBlank()
                || request.getPassword() == null || request.getPassword().isBlank()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "Username and password are required"));
        }

        if (request.getUsername().length() < 3 || request.getUsername().length() > 50) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "Username must be between 3 and 50 characters"));
        }

        if (request.getPassword().length() < 6) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "Password must be at least 6 characters"));
        }

        if (userStore.containsKey(request.getUsername())) {
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(Map.of("error", "Username already exists"));
        }

        String encodedPassword = passwordEncoder.encode(request.getPassword());
        List<String> roles = List.of("USER");
        userStore.put(request.getUsername(), new UserRecord(encodedPassword, roles));

        String token = tokenProvider.generateToken(request.getUsername(), roles);
        log.info("User '{}' registered successfully", request.getUsername());

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(new AuthResponse(token, request.getUsername(), roles));
    }
}
