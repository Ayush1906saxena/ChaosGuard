package com.chaosguard.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import io.swagger.v3.oas.models.tags.Tag;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI chaosGuardOpenAPI() {
        final String securitySchemeName = "bearerAuth";

        return new OpenAPI()
                .info(new Info()
                        .title("ChaosGuard API")
                        .description("AI-powered security scanning and chaos engineering platform. "
                                + "ChaosGuard provides automated vulnerability detection, attack chain analysis, "
                                + "fix recommendations, and chaos experiment execution.")
                        .version("1.0.0")
                        .contact(new Contact()
                                .name("ChaosGuard Team")
                                .url("https://github.com/chaosguard"))
                        .license(new License()
                                .name("MIT License")
                                .url("https://opensource.org/licenses/MIT")))
                .components(new Components()
                        .addSecuritySchemes(securitySchemeName, new SecurityScheme()
                                .name(securitySchemeName)
                                .type(SecurityScheme.Type.HTTP)
                                .scheme("bearer")
                                .bearerFormat("JWT")
                                .description("Enter your JWT token obtained from the /api/auth/login endpoint")))
                .addSecurityItem(new SecurityRequirement().addList(securitySchemeName))
                .tags(List.of(
                        new Tag().name("Authentication")
                                .description("User registration, login, and JWT token management"),
                        new Tag().name("Scans")
                                .description("Security scan lifecycle — create, monitor, and retrieve scan results"),
                        new Tag().name("Findings")
                                .description("Vulnerability findings discovered during security scans"),
                        new Tag().name("Fixes")
                                .description("AI-generated fix recommendations for identified vulnerabilities"),
                        new Tag().name("Attack Chains")
                                .description("Multi-step attack chain analysis linking related vulnerabilities"),
                        new Tag().name("Chaos")
                                .description("Chaos engineering experiments — fault injection and resilience testing"),
                        new Tag().name("GitHub")
                                .description("GitHub integration — repository import, webhooks, and PR automation"),
                        new Tag().name("Health")
                                .description("Service health checks and readiness probes")
                ));
    }
}
