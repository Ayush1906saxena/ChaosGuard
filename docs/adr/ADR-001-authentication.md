# ADR-001: Authentication Mechanism

**Date:** 2026-03-18

**Status:** Accepted

## Context

ChaosGuard currently has no authentication layer. All API endpoints and the MCP
server are open to any caller on the network. As adoption grows beyond local
development, we need an authentication mechanism that satisfies three use cases:

1. **Interactive users** accessing the web UI and API.
2. **MCP server and CI/CD pipelines** calling the API programmatically.
3. **Future multi-tenant deployments** where workspaces must be isolated.

Options considered:

- **JWT (JSON Web Tokens)** — Stateless, widely supported, good for API-first
  applications.
- **OAuth2 / OpenID Connect** — Full-featured but adds significant complexity
  and external provider dependencies.
- **API keys** — Simple, ideal for machine-to-machine communication, but lack
  expiry semantics without additional infrastructure.

## Decision

We will use a layered approach:

- **JWT with refresh tokens** for interactive and API authentication. Access
  tokens are short-lived (15 minutes). Refresh tokens are long-lived (7 days)
  and stored server-side for revocation support.
- **API keys** for MCP server integration and CI/CD pipelines. Keys are scoped
  to specific workspaces and permissions, stored as salted hashes.
- **OAuth2 is deferred** until multi-tenant support is implemented (see
  ADR-005). At that point we will evaluate OpenID Connect providers for SSO.

## Consequences

- A **token rotation strategy** must be implemented — refresh tokens are rotated
  on every use (rotation invalidates the previous token).
- **Secure key management** is required — API keys must be hashed at rest and
  never logged.
- A **session invalidation mechanism** is needed — a server-side deny-list for
  revoked JWTs that is checked on every request until the token's natural
  expiry.
- The authentication middleware must be added to all API routes and the MCP
  server transport layer.
