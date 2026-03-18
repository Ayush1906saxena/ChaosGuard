# ChaosGuard — FAANG-Grade Technology Upgrade Plan

**Goal:** Transform ChaosGuard into a showcase-worthy portfolio project for Google, Meta, and Apple applications.

---

## Workstream 1: Observability Stack (Prometheus + Grafana + Tempo) ✅ DONE

**Why:** No FAANG engineer takes a distributed system seriously without observability.

### New files (7)

| File | Purpose |
|------|---------|
| `observability/prometheus/prometheus.yml` | Scrape config — pulls metrics from gateway :8080 and agents :8082 every 15s |
| `observability/grafana/provisioning/datasources/datasources.yml` | Auto-connects Grafana to Prometheus + Tempo on startup |
| `observability/grafana/provisioning/dashboards/dashboard.yml` | Tells Grafana where to find dashboard JSON files |
| `observability/grafana/dashboards/chaosguard-overview.json` | Dashboard: API request rate, latency p50/p95/p99, error rates, JVM heap, active threads |
| `observability/grafana/dashboards/chaos-experiments.json` | Dashboard: resilience score timeline, fault injection events, recovery curves |
| `observability/tempo/tempo.yml` | Trace ingestion config (OTLP gRPC on 4317) |

### Modified files (3)

| File | Changes |
|------|---------|
| `docker-compose.yml` | Add 3 services: `prometheus` (port 9090), `grafana` (port 3001, admin/admin), `tempo` (port 4317) |
| `gateway/pom.xml` | Add `micrometer-tracing-bridge-otel`, `opentelemetry-exporter-otlp` for distributed tracing |
| `gateway/src/main/resources/application.yml` | Add tracing sampling probability, OTLP exporter endpoint pointing to Tempo |

### Result
Open http://localhost:3001 → pre-loaded Grafana dashboards with live metrics from all services.

---

## Workstream 2: Kubernetes Helm Charts ✅ DONE

**Why:** Shows production deployment thinking. Every FAANG role expects Kubernetes fluency.

### New files (15)

| File | Purpose |
|------|---------|
| `helm/chaosguard/Chart.yaml` | Chart metadata — name, version, appVersion |
| `helm/chaosguard/values.yaml` | All tunables: image tags, replica counts, resource requests/limits, env vars |
| `helm/chaosguard/templates/_helpers.tpl` | Standard Helm template helpers (fullname, labels, selectors) |
| `helm/chaosguard/templates/namespace.yaml` | `chaosguard` namespace |
| `helm/chaosguard/templates/configmap.yaml` | Shared config: Kafka, Redis, Postgres, Ollama URLs |
| `helm/chaosguard/templates/secret.yaml` | JWT secret, DB credentials (base64 placeholders) |
| `helm/chaosguard/templates/gateway-deployment.yaml` | Spring Boot: 2 replicas, liveness/readiness probes, 512Mi-1Gi RAM |
| `helm/chaosguard/templates/gateway-service.yaml` | ClusterIP service on port 8080 |
| `helm/chaosguard/templates/agents-deployment.yaml` | Agent workers with CPU/memory resource limits |
| `helm/chaosguard/templates/agents-service.yaml` | ClusterIP service on port 8082 |
| `helm/chaosguard/templates/frontend-deployment.yaml` | Next.js with 2 replicas |
| `helm/chaosguard/templates/frontend-service.yaml` | ClusterIP service on port 3000 |
| `helm/chaosguard/templates/ingress.yaml` | NGINX ingress: `/` → frontend, `/api` → gateway, TLS |
| `helm/chaosguard/templates/hpa.yaml` | HorizontalPodAutoscaler: agents scale 2→8 at 70% CPU |
| `helm/chaosguard/templates/networkpolicy.yaml` | Only allow traffic between known services |

### Result
`helm template helm/chaosguard/` renders valid Kubernetes manifests ready for any cluster.

---

## Workstream 3: Frontend Modernization ✅ DONE

**Why:** The UI is the first thing anyone sees. It needs to feel like a product, not a project.

### New dependencies

| Package | Purpose |
|---------|---------|
| `framer-motion` | Page transitions, component entrance animations |
| `@tanstack/react-query` | Data fetching with caching, background refetch, stale-while-revalidate |
| `recharts` | Charts for metrics page (line, bar, pie, area) |
| `sonner` | Lightweight, beautiful toast notifications |

### New files (7)

| File | Purpose |
|------|---------|
| `frontend/src/lib/query-client.ts` | TanStack Query client config: 30s stale time, 3 retries with backoff |
| `frontend/src/components/QueryProvider.tsx` | React Query provider wrapping the app |
| `frontend/src/components/Toaster.tsx` | Sonner toast provider (dark theme, bottom-right position) |
| `frontend/src/components/Skeleton.tsx` | Reusable skeletons: SkeletonCard, SkeletonTable, SkeletonText with shimmer |
| `frontend/src/components/Breadcrumbs.tsx` | Auto-generates breadcrumbs from URL pathname (Dashboard > Scan > Report) |
| `frontend/src/components/PageTransition.tsx` | Framer Motion AnimatePresence wrapper for route transitions |
| `frontend/src/components/ErrorBoundary.tsx` | Global error boundary with retry button and error details |

### Modified files (6)

| File | Changes |
|------|---------|
| `frontend/package.json` | Add 4 new dependencies |
| `frontend/src/app/layout.tsx` | Wrap children with QueryProvider, Toaster, ErrorBoundary |
| `frontend/src/app/page.tsx` | Add Framer Motion entrance animations, skeleton loading states |
| `frontend/src/app/metrics/page.tsx` | **COMPLETE REWRITE** — Real dashboard with Recharts: scan duration line chart, severity distribution pie chart, agent performance bar chart, resilience score gauge |
| `frontend/src/app/scan/[id]/layout.tsx` | Add Breadcrumbs component at the top |
| `frontend/src/lib/api.ts` | Add React Query hook wrappers (useScans, useScan, useFindings) alongside existing functions |

### Result
Smooth page transitions, skeleton loading, real metrics charts, toast notifications, breadcrumb navigation.

---

## Workstream 4: API Documentation (Swagger UI) ✅ DONE

**Why:** Auto-generated interactive API docs show professionalism. Every production API has this.

### New files (1)

| File | Purpose |
|------|---------|
| `gateway/src/main/java/com/chaosguard/config/OpenApiConfig.java` | OpenAPI 3.0 config: title "ChaosGuard API", JWT Bearer security scheme, tag descriptions for each controller |

### Modified files (2)

| File | Changes |
|------|---------|
| `gateway/pom.xml` | Add `springdoc-openapi-starter-webmvc-ui` 2.5.0 |
| `gateway/src/main/java/com/chaosguard/config/SecurityConfig.java` | Permit `/swagger-ui/**` and `/v3/api-docs/**` unauthenticated |

### Result
Interactive Swagger UI at http://localhost:8080/swagger-ui.html with JWT auth support.

---

## Workstream 5: Spring Boot Production Enhancements ✅ DONE

**Why:** Shows understanding of resilience patterns and production-grade Java.

### New files (2)

| File | Purpose |
|------|---------|
| `gateway/src/main/java/com/chaosguard/config/Resilience4jConfig.java` | Circuit breaker configs: GitHub API (50% failure rate → open), Kafka producer, agent service calls |
| `gateway/src/main/resources/logback-spring.xml` | Structured JSON logging with traceId/spanId correlation IDs for log→trace linking |

### Modified files (2)

| File | Changes |
|------|---------|
| `gateway/pom.xml` | Add `spring-cloud-starter-circuitbreaker-resilience4j`, `logstash-logback-encoder` |
| `gateway/src/main/resources/application.yml` | Add resilience4j circuit breaker config (failure threshold, wait duration, sliding window size) |

### Result
Circuit breakers on all external calls, structured JSON logs with distributed trace correlation.

---

## Workstream 6: Professional README ✅ DONE

**Why:** The README is the landing page. It must sell the project in 30 seconds.

### Modified files (1)

| File | Changes |
|------|---------|
| `README.md` | Complete rewrite with: shields.io tech badges, Mermaid architecture diagram, feature highlights, quick start (3 commands), observability section, K8s deployment section, API docs link, contributing guide, license |

---

## Workstream 7: MCP Server Setup (Context7 + Playwright + GitHub) ✅ DONE

**Why:** These tools accelerate development and add E2E testing capability.

### Setup (Claude Code MCP config)

| MCP Server | Package | Purpose |
|------------|---------|---------|
| **Context7** | `@upstash/context7-mcp` | Fetches latest docs for Framer Motion, React Query, Recharts, Helm, Resilience4j |
| **Playwright** | `@executeautomation/playwright-mcp-server` | Browser automation for E2E tests and README screenshots |
| **GitHub** | `@modelcontextprotocol/server-github` | Create issues, PRs, manage releases, add repo topics/description |

---

## Workstream 8: Persistent Auth (PostgreSQL-backed) ✅ DONE

**Why:** Current auth is in-memory — restarting the gateway loses all registered users. No FAANG reviewer would accept this.

### Modified files (3)

| File | Changes |
|------|---------|
| `gateway/src/main/java/com/chaosguard/controller/AuthController.java` | Replace `ConcurrentHashMap` with JPA `UserRepository`; add password strength validation |
| `gateway/src/main/java/com/chaosguard/model/User.java` | New JPA entity: id, username (unique), encoded password, roles, createdAt |
| `gateway/src/main/java/com/chaosguard/repository/UserRepository.java` | Spring Data JPA interface with `findByUsername()` |

### New files (1)

| File | Purpose |
|------|---------|
| `gateway/src/main/resources/db/migration/V3__create_users_table.sql` | Flyway migration: users table with unique username constraint |

### Result
Users persist across gateway restarts. Default admin user seeded via migration.

---

## Workstream 9: Fix PR Creation for Scanned Repos ✅ DONE

**Why:** Users need the ability to create real PRs with AI-generated fixes directly in the repos they scan. This is optional — the user chooses whether to create a PR or not.

### Modified files (2)

| File | Changes |
|------|---------|
| `gateway/src/main/java/com/chaosguard/service/GitHubService.java` | Create fix branch, commit fix code, open PR targeting default branch — for the scanned repo |
| `gateway/src/main/java/com/chaosguard/controller/GitHubController.java` | Single-finding issue creation (not bulk); return PR/issue URL in response |

### Modified frontend files (2)

| File | Changes |
|------|---------|
| `frontend/src/app/scan/[id]/fixes/page.tsx` | Show success toast with clickable PR/issue URL; proper loading/error feedback |
| `frontend/src/lib/api.ts` | Update response types to match backend |

### Result
Users can select fixes and create a PR in the scanned repo with one click. Issue creation works per-finding with immediate URL feedback.

---

## Completed Changes (Post-Plan)

- ✅ Removed default credentials hint from login page
- ✅ Added signup page (`/signup`) with registration form + confirm password
- ✅ Added `register()` function in `auth.ts` calling `/api/auth/register`
- ✅ Fixed ChromaDB client/server version mismatch (`chromadb==0.5.23` pinned)
- ✅ Fixed indexer publishing false "index-complete" on ChromaDB failure
- ✅ Fixed 1700+ duplicate findings from `package-lock.json`
- ✅ Fixed client-side crash on Report page (SeverityBadge/TierBadge null safety)
- ✅ Hardened `normalizeFinding` — validates severity/tier/confidence values

---

## Known Limitations / Future Work

| Issue | Impact | Fix |
|-------|--------|-----|
| Auth is in-memory (ConcurrentHashMap) | Users lost on gateway restart | Workstream 8 |
| Chaos experiments need Docker Desktop running | Can't run on CI without DinD | Add K8s chaos support via LitmusChaos |
| Ollama must be running locally with 3 models pulled | Scans fail silently without it | Add health check + user-facing error on dashboard |
| GitHub token needs write access to scanned repo | 403 on repos you don't own | Token must have access to target repo |
| Tree-sitter "signal only works in main thread" warnings | Noisy logs, no functional impact | Move tree-sitter to subprocess |
