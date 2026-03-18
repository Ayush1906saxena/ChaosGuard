package com.chaosguard.config;

import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;

/**
 * Resilience4j circuit breaker configuration for external service calls.
 * <p>
 * Three circuit breakers are defined:
 * <ul>
 *   <li><b>githubApi</b> — protects GitHub API calls (50% failure threshold)</li>
 *   <li><b>kafkaProducer</b> — protects Kafka produce operations</li>
 *   <li><b>agentService</b> — protects calls to AI agent services</li>
 * </ul>
 * <p>
 * Usage in service classes:
 * <pre>
 * {@literal @}CircuitBreaker(name = "githubApi", fallbackMethod = "githubFallback")
 * public ResponseEntity&lt;?&gt; callGitHub() { ... }
 * </pre>
 */
@Configuration
public class Resilience4jConfig {

    @Bean
    public CircuitBreakerRegistry circuitBreakerRegistry() {
        // GitHub API — opens at 50% failure rate
        CircuitBreakerConfig githubConfig = CircuitBreakerConfig.custom()
                .failureRateThreshold(50)
                .waitDurationInOpenState(Duration.ofSeconds(30))
                .slidingWindowType(CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
                .slidingWindowSize(10)
                .minimumNumberOfCalls(5)
                .permittedNumberOfCallsInHalfOpenState(3)
                .automaticTransitionFromOpenToHalfOpenEnabled(true)
                .build();

        // Kafka producer — opens at 60% failure rate, longer recovery
        CircuitBreakerConfig kafkaConfig = CircuitBreakerConfig.custom()
                .failureRateThreshold(60)
                .waitDurationInOpenState(Duration.ofSeconds(60))
                .slidingWindowType(CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
                .slidingWindowSize(20)
                .minimumNumberOfCalls(5)
                .permittedNumberOfCallsInHalfOpenState(3)
                .automaticTransitionFromOpenToHalfOpenEnabled(true)
                .build();

        // Agent service — opens at 50% failure rate
        CircuitBreakerConfig agentConfig = CircuitBreakerConfig.custom()
                .failureRateThreshold(50)
                .waitDurationInOpenState(Duration.ofSeconds(45))
                .slidingWindowType(CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
                .slidingWindowSize(10)
                .minimumNumberOfCalls(3)
                .permittedNumberOfCallsInHalfOpenState(2)
                .automaticTransitionFromOpenToHalfOpenEnabled(true)
                .build();

        return CircuitBreakerRegistry.of(
                java.util.Map.of(
                        "default", CircuitBreakerConfig.ofDefaults(),
                        "githubApi", githubConfig,
                        "kafkaProducer", kafkaConfig,
                        "agentService", agentConfig
                )
        );
    }
}
