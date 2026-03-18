# ADR-005: Multi-Tenancy Model

**Date:** 2026-03-18

**Status:** Proposed

## Context

ChaosGuard is currently a single-tenant application. All experiments, scan
results, and configuration exist in a single global namespace. Enterprise
customers require workspace isolation so that:

- Teams can run independent experiments without interference.
- Scan results and generated fixes are scoped to a workspace.
- Access control can be applied per workspace.
- Audit logs are attributable to a workspace and user.

Isolation models considered:

- **Separate clusters per tenant** — strongest isolation, highest operational
  cost.
- **Shared cluster, separate databases** — moderate isolation, moderate cost.
- **Shared database, separate schemas** — lightweight isolation, lowest cost,
  sufficient for most compliance requirements.

## Decision

We will start with **workspace-level isolation using a shared database with
separate schemas**:

- **PostgreSQL:** Each workspace gets its own schema. A `workspace_id` context
  is set on every database session to enforce row-level security as a defense
  in depth measure.
- **Kafka:** Topic names are prefixed with the workspace identifier
  (`ws-{id}.scan-results`, `ws-{id}.chaos-events`). Consumer groups are
  similarly prefixed.
- **Redis:** All keys are namespaced with the workspace identifier
  (`ws:{id}:cache:*`, `ws:{id}:session:*`).
- **Strict isolation** (separate clusters) is deferred to a future phase for
  customers with regulatory requirements that mandate physical separation.

## Consequences

- **Workspace context must propagate** through all API calls, background jobs,
  and event consumers. A middleware layer will extract the workspace from the
  JWT claims (see ADR-001) and set it on the request context.
- **Data migration is required** for existing single-tenant deployments. A
  migration script will move all existing data into a `default` workspace
  schema.
- **RBAC must be workspace-scoped** — roles and permissions are defined per
  workspace. A user can have different roles in different workspaces.
- **Cross-workspace operations** (e.g., global admin dashboards) require a
  superuser role that bypasses workspace scoping.
