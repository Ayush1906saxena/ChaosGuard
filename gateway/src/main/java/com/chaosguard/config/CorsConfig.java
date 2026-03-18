package com.chaosguard.config;

/**
 * CORS is now configured via {@link SecurityConfig#corsConfigurationSource()}.
 * This class is intentionally left empty to avoid bean conflicts with
 * Spring Security's CORS integration.
 *
 * Allowed origins are controlled by the environment variable CORS_ALLOWED_ORIGINS
 * (defaults to http://localhost:3000).
 */
public class CorsConfig {
    // Intentionally empty — CORS handled by SecurityConfig
}
