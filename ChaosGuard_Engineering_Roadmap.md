# ChaosGuard Engineering Roadmap

**Author perspective:** Senior Staff Engineer, Production Reliability & Security
**Date:** 2026-03-18
**Scope:** Architecture review, chaos engineering maturity, security posture, and prioritized roadmap

---

## 1. Executive Summary

ChaosGuard is an ambitious platform combining AI-powered security scanning with chaos engineering. The architecture — tiered agents (Recon/Hunter/Siege), a 10-phase chaos lifecycle, 8 fault injectors, 5 DAST probes, and LLM-powered fix generation — demonstrates strong design vision.

**Production readiness: ~4/10.**

The core chaos execution engine (`runner.py`, `injectors.py`, `safety.py`) is well-designed with proper lifecycle management, LIFO rollback, and blast radius controls. However, the platform has zero test coverage, no CI/CD, no API authentication, permissive CORS, and validation that runs directly on the host. These gaps must be closed before any external-facing deployment.

**What works well:**
- 10-phase experiment lifecycle with emergency stop, approval workflow, and resilience scoring
- Docker Compose sandboxing with sanitization (strips `privileged`, enforces resource limits, remaps ports)
- Safety controller with blast radius limits, experiment locks, and Redis-backed kill switches
- DAST safety controls (domain allowlist, request caps, destructive payload blocking)

**What needs attention:**
- Zero test files in the entire repository
- No authentication or authorization on any API endpoint
- CORS allows all origins with credentials (`allowCredentials=true` + `*` origins)
- Fix validation runs `subprocess` on the host, not inside a container
- Docker socket mounted into the agents container (container escape vector)
- No CI/CD pipeline, no linting enforcement, no automated quality gates

---

## 2. Chaos Engineering: From Good to Production-Grade

### 2.1 Current State

The chaos executor is the strongest part of the codebase. The 10-phase lifecycle in `runner.py` follows industry patterns:

```
PLANNING → PROVISIONING → BASELINE → PENDING_APPROVAL → STEADY_STATE
    → INJECTING → OBSERVING → ROLLING_BACK → RECOVERING → COMPLETED
```

8 fault types in `injectors.py`:
| Fault | Mechanism | Rollback |
|-------|-----------|----------|
| network_delay | `tc netem` via netshoot sidecar | `tc qdisc del` |
| network_partition | `iptables` DROP rules | `iptables -D` |
| packet_loss | `tc netem loss` | `tc qdisc del` |
| container_kill | `SIGKILL`/`SIGTERM` | `docker start` |
| container_pause | `docker pause` | `docker unpause` |
| cpu_stress | `yes > /dev/null` processes | `kill` stress PIDs |
| memory_stress | `dd` to tmpfs | Remove tmpfs file |
| disk_fill | `dd if=/dev/zero` | Remove fill file |

Safety controls in `safety.py`:
- Max blast radius: 3 containers
- Max duration: 300s
- Max concurrent experiments: 1 per scan
- Approval timeout: 600s
- Auto-rollback on error: enabled
- Emergency stop via Redis key

### 2.2 Recommendations: Steady-State Hypothesis Validation

The current implementation collects baseline metrics and observes during chaos, but doesn't formalize **steady-state hypotheses** — the core concept from Netflix's Principles of Chaos Engineering.

**What to add:**

```python
# Hypotheses should be first-class objects, not implicit
@dataclass
class SteadyStateHypothesis:
    name: str                          # "API responds within 200ms at p99"
    metric: str                        # "http_response_time_p99"
    threshold: float                   # 200.0
    comparison: str                    # "less_than"
    tolerance_pct: float = 10.0        # Allow 10% degradation during chaos

    def evaluate(self, value: float, phase: str) -> bool:
        if phase == "OBSERVING":
            return value < self.threshold * (1 + self.tolerance_pct / 100)
        return value < self.threshold
```

- Define hypotheses **before** experiments start, not after
- Validate hypotheses at BASELINE, STEADY_STATE, OBSERVING, and RECOVERING phases
- Auto-abort if steady-state is violated beyond tolerance during OBSERVING
- Report hypothesis pass/fail as the primary experiment outcome (not just resilience score)

### 2.3 Recommendations: GameDay Framework

Add scheduled, repeatable chaos runs — not just ad-hoc experiments triggered from scans.

**Key components:**
1. **Experiment catalog** — Reusable experiment definitions stored in PostgreSQL (scenario, target services, hypotheses, blast radius)
2. **Scheduling** — Cron-based experiment scheduling ("run network partition on payment-service every Tuesday at 2pm")
3. **Progressive rollout** — Start with single-service faults, automatically escalate to multi-service as confidence grows
4. **Historical tracking** — Resilience score trends over time per service, regression alerts when scores drop

### 2.4 Recommendations: Real Observability Integration

The current probe system (`probes.py`) does HTTP health checks. Production chaos engineering requires deep observability.

**Integration targets (priority order):**
1. **Prometheus/VictoriaMetrics** — Scrape application metrics before/during/after. Compare error rates, latency percentiles, saturation signals
2. **OpenTelemetry** — Correlate chaos experiments with distributed traces. Identify exactly which spans degrade during fault injection
3. **Grafana annotations** — Automatically annotate dashboards when chaos experiments start/stop. Critical for post-mortems
4. **PagerDuty/Opsgenie** — Validate that alerting actually fires during chaos. If you inject 100% packet loss and no alert triggers, that's a finding

**Metrics to capture:**
- Error rate delta (before vs. during)
- Latency p50/p95/p99 delta
- Recovery time (time from rollback to baseline restoration)
- Cascade depth (how many downstream services were affected)

### 2.5 Recommendations: Chaos Maturity Model

Implement progressive chaos maturity levels that guide users from safe experimentation to production chaos:

| Level | Name | Scope | Approval | Environment |
|-------|------|-------|----------|-------------|
| 0 | **Analysis Only** | Current state — generate scenarios, no execution | N/A | N/A |
| 1 | **Sandbox Chaos** | Execute in Docker Compose sandbox | Auto-approve | Isolated sandbox |
| 2 | **Staging Chaos** | Execute against staging environment | Manual approval | Staging |
| 3 | **Production Chaos** | Execute against production with guardrails | Multi-person approval | Production |
| 4 | **Continuous Chaos** | Automated, scheduled production chaos | Policy-based | Production |

Each level should unlock only after the previous level's experiments pass consistently.

---

## 3. Critical Security & Production Gaps

### 3.1 Zero Test Coverage (Severity: CRITICAL)

There are **no test files** anywhere in the repository. No `*_test.py`, no `*.spec.ts`, no `*Test.java`. For a security tool, this is the single most important gap.

**Impact:** Every refactor is a gamble. Every PR merge is untested. The safety-critical chaos executor code (`safety.py`, `injectors.py`) has no verification beyond manual testing.

**Minimum test plan:**

| Component | Test Type | Priority | Estimated Effort |
|-----------|-----------|----------|-----------------|
| `safety.py` | Unit tests for blast radius, duration, approval logic | P0 | 1 day |
| `injectors.py` | Unit tests for inject/rollback symmetry | P0 | 1 day |
| `runner.py` | Integration test for full lifecycle (mock Docker) | P0 | 2 days |
| `sandbox.py` | Unit tests for sanitization logic | P0 | 1 day |
| `sandbox_validator.py` | Unit tests for each language validator | P1 | 1 day |
| DAST probes | Unit tests with mock HTTP responses | P1 | 2 days |
| Gateway controllers | Spring Boot `@WebMvcTest` integration tests | P1 | 2 days |
| Frontend components | Jest + React Testing Library | P2 | 3 days |

### 3.2 No API Authentication (Severity: CRITICAL)

The Spring Boot gateway has **no Spring Security dependency, no auth filter, no token validation**. Every endpoint is publicly accessible.

**CORS in `CorsConfig.java`:**
```java
config.setAllowCredentials(true);
config.setAllowedOriginPatterns(List.of("*"));  // All origins + credentials
```

This is a textbook misconfiguration. `allowCredentials=true` with wildcard origins means any website can make authenticated cross-origin requests. Browsers will enforce the spec (rejecting `Access-Control-Allow-Origin: *` with credentials), but `setAllowedOriginPatterns("*")` bypasses this by reflecting the `Origin` header — effectively allowing any origin.

**Recommendations:**
1. Add Spring Security with JWT or OAuth2
2. Restrict CORS origins to the frontend domain only
3. Add rate limiting (Spring Cloud Gateway or bucket4j)
4. Add API key authentication for the MCP server integration
5. Implement RBAC — separate read-only scan viewers from chaos experiment operators

### 3.3 Docker Socket Privilege Escalation (Severity: HIGH)

In `docker-compose.yml`, the agents service mounts the Docker socket:

```yaml
agents:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
```

This is necessary for the chaos executor to manage containers, but it grants the agents container **root-equivalent access to the host**. A vulnerability in any agent code could be exploited to escape the container.

**Mitigations (implement in order):**
1. **Docker socket proxy** — Use [tecnativa/docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) to expose only the specific Docker API endpoints needed (containers, exec, networks). Block image pull, volume create, and privileged container creation
2. **Read-only where possible** — For probes that only inspect containers, mount as `ro`
3. **Rootless Docker** — Run the Docker daemon in rootless mode to limit the blast radius of socket access
4. **Dedicated chaos user** — Run the agents process as a non-root user inside the container

### 3.4 Fix Validation Runs on Host (Severity: HIGH)

`agents/generators/sandbox_validator.py` runs `subprocess.run()` with commands like `javac`, `mvn compile`, `npm test`, and `python -m pytest` directly on the host (or within the agents container). While it copies files to a temp directory, there is **no container-level isolation**.

If a malicious repository contains a `pom.xml` with a build plugin that executes arbitrary code, `mvn compile` will run it with the privileges of the agents process.

**Recommendations:**
1. Run all validation inside a short-lived Docker container with no network access and strict resource limits
2. Use `--network none` and `--read-only` flags
3. Mount the temp directory as the only writable volume
4. Set a hard timeout at the Docker level, not just `subprocess.timeout`

### 3.5 No CI/CD Pipeline (Severity: HIGH)

No `.github/workflows/`, no `Jenkinsfile`, no `.gitlab-ci.yml`. Code merges directly to master with no automated checks.

**Minimum CI pipeline:**
```yaml
# .github/workflows/ci.yml
jobs:
  python-agents:
    - ruff check agents/          # Linting
    - mypy agents/                # Type checking
    - pytest agents/tests/ -v     # Unit tests

  java-gateway:
    - mvn verify -B               # Compile + test
    - mvn spotbugs:check          # Static analysis

  frontend:
    - npm run lint                # ESLint
    - npm run build               # TypeScript compilation
    - npm test                    # Jest

  docker:
    - docker compose build        # Verify all images build
    - docker compose up -d && health-check  # Smoke test
```

### 3.6 No Restart Policies (Severity: MEDIUM)

The `docker-compose.yml` services use the default restart policy (`no`). In production, infrastructure services (postgres, redis, kafka) should use `restart: unless-stopped` and application services should use `restart: on-failure` with `max_retries`.

---

## 4. Architecture Improvements

### 4.1 DAST Agent Enhancement

The current DAST implementation has 5 probes (SQLi, IDOR, auth bypass, race conditions, route extraction). This is a solid foundation but covers only a fraction of the OWASP Top 10.

**Missing probe types to add:**
| Probe | OWASP Category | Effort |
|-------|---------------|--------|
| XSS (reflected + stored) | A03:2021 Injection | 2 days |
| SSRF detection | A10:2021 SSRF | 1 day |
| Path traversal | A01:2021 Broken Access Control | 1 day |
| Open redirect | A01:2021 Broken Access Control | 0.5 days |
| CORS misconfiguration | A05:2021 Security Misconfiguration | 0.5 days |
| Header security audit | A05:2021 Security Misconfiguration | 0.5 days |
| Deserialization testing | A08:2021 Software Integrity | 2 days |

**Architecture improvement:** The DAST probes currently make direct HTTP calls. Add a proxy layer (mitmproxy or similar) that captures all request/response pairs for:
- Replay testing
- Evidence collection for reports
- Automatic response diffing between authenticated/unauthenticated requests

### 4.2 Language Support Expansion

The indexer's Tree-sitter integration currently covers 4 languages. The code scanning agents (tier1-tier3) work at the text/LLM level, but deeper AST-aware analysis requires parser support.

**Priority languages to add:**
1. **Go** — Extremely common in cloud-native targets
2. **Rust** — Growing adoption in security-sensitive systems
3. **C/C++** — Memory safety analysis is high-value
4. **Ruby** — Common in web applications (Rails)
5. **PHP** — Still powers ~75% of the web

### 4.3 Feedback Loop: Chaos Results → Agent Tuning

Currently, chaos experiment results and security scan findings are terminal — they produce reports but don't feed back into the system.

**Implement a learning loop:**
1. **False positive tracking** — When users dismiss a finding, record it. Use accumulated false positives to tune LLM prompts and detection thresholds
2. **Chaos resilience regression** — If a service's resilience score drops between runs, automatically flag it and cross-reference with recent code changes (git log)
3. **Fix validation feedback** — Track which LLM-generated fixes pass validation vs. fail. Use this to improve fix generation prompts over time
4. **DAST finding correlation** — Cross-reference DAST findings with static analysis findings. Confirmed findings (static + dynamic) get severity boost; unconfirmed ones get deprioritized

### 4.4 Resilience Score Improvements

The current resilience scoring in `runner.py` uses a weighted formula:
- Availability weight: 0.4
- Recovery time weight: 0.3
- Graceful degradation weight: 0.3

**Enhance with:**
- **Per-service scoring** — Not just aggregate. Which specific service is the weakest link?
- **Blast radius measurement** — How many downstream services were affected by a single fault?
- **Recovery curve analysis** — Is recovery linear, exponential, or does it plateau? A system that recovers 90% in 5s but takes 60s for the last 10% has a different profile than one that recovers linearly
- **Comparison baselines** — Compare current run against historical runs. "Resilience improved 15% since last month"

---

## 5. Prioritized Roadmap

### P0 — Do Before Any External Deployment (Weeks 1-3)

| Item | Effort | Impact | Owner Suggestion |
|------|--------|--------|-----------------|
| Add unit tests for safety.py, injectors.py, runner.py | 4 days | Prevents regressions in safety-critical code | Backend |
| Add Spring Security with JWT auth to gateway | 3 days | Blocks unauthorized access to all endpoints | Backend |
| Fix CORS to allowlist frontend origin only | 0.5 days | Closes cross-origin credential leak | Backend |
| Set up GitHub Actions CI (lint + test + build) | 2 days | Automated quality gate on every PR | DevOps |
| Add Docker socket proxy for agents container | 1 day | Limits container escape blast radius | DevOps |
| Move fix validation into isolated containers | 2 days | Prevents malicious build script execution | Backend |

### P1 — Production Hardening (Weeks 4-8)

| Item | Effort | Impact | Owner Suggestion |
|------|--------|--------|-----------------|
| Steady-state hypothesis validation | 3 days | Core chaos engineering best practice | Backend |
| Prometheus/Grafana observability integration | 4 days | Real metrics instead of HTTP-only probes | Backend + DevOps |
| Add restart policies and health-based dependencies | 0.5 days | Service resilience in deployment | DevOps |
| Rate limiting on gateway APIs | 1 day | DoS protection | Backend |
| RBAC (viewer vs. operator vs. admin roles) | 3 days | Principle of least privilege | Backend |
| Frontend and gateway integration tests | 4 days | End-to-end confidence | Full-stack |
| Add XSS and SSRF DAST probes | 3 days | Better OWASP coverage | Backend |

### P2 — Platform Maturity (Weeks 9-16)

| Item | Effort | Impact | Owner Suggestion |
|------|--------|--------|-----------------|
| GameDay framework (experiment catalog + scheduling) | 2 weeks | Repeatable, scheduled chaos | Backend |
| Chaos maturity model (levels 0-4 with gating) | 1 week | Safe progression to production chaos | Backend |
| OpenTelemetry trace correlation | 1 week | Deep observability during chaos | Backend + DevOps |
| False positive feedback loop | 1 week | Improved finding accuracy over time | ML/Backend |
| Additional language support (Go, Rust, C) | 2 weeks | Broader target coverage | Backend |
| Per-service resilience scoring + trends | 3 days | Granular resilience visibility | Backend |

### P3 — Differentiation (Weeks 17+)

| Item | Effort | Impact | Owner Suggestion |
|------|--------|--------|-----------------|
| Production chaos support (staging → prod progression) | 3 weeks | Real production resilience validation |
| PagerDuty/Opsgenie integration for alert validation | 1 week | Verify alerting fires during chaos |
| Chaos + DAST combined scenarios | 2 weeks | "Does the auth bypass get worse under load?" |
| Custom fault plugin system | 2 weeks | User-defined fault types |
| Multi-cluster / Kubernetes-native support | 4 weeks | Beyond Docker Compose targets |
| Compliance report generation (SOC2, ISO 27001) | 2 weeks | Enterprise sales enablement |

---

## 6. Quick Wins (< 1 Day Each)

These are low-effort, high-signal improvements:

1. **Add `restart: unless-stopped`** to postgres, redis, kafka, chromadb in `docker-compose.yml`
2. **Add `.dockerignore`** files to prevent copying `node_modules`, `.git`, `__pycache__` into images
3. **Pin image tags** — `chromadb/chroma:latest` should be `chromadb/chroma:0.4.x`
4. **Add `ruff.toml`** to enforce Python linting rules across agents/
5. **Add health check endpoint** to the agents service (currently relies on Kafka consumer liveness)
6. **Restrict CORS origins** in `CorsConfig.java` to `http://localhost:3000` (takes 1 line change)
7. **Add `.env.example`** documentation for all required environment variables (partially exists)
8. **Set `max_concurrent_experiments`** as a configurable environment variable instead of hardcoded in `safety.py`

---

## 7. Architecture Decision Records (Suggested)

Document these decisions as ADRs before implementation:

1. **ADR-001:** Authentication mechanism — JWT vs. OAuth2 vs. API keys
2. **ADR-002:** Observability stack — Prometheus+Grafana vs. Datadog vs. OpenTelemetry Collector
3. **ADR-003:** Chaos execution target — Docker Compose only vs. Kubernetes support
4. **ADR-004:** Fix validation isolation — Docker containers vs. Firecracker microVMs vs. gVisor
5. **ADR-005:** Multi-tenancy model — Single-tenant vs. workspace isolation

---

*This document should be revisited quarterly. The P0 items are non-negotiable for any deployment beyond localhost development.*
