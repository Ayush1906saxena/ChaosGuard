# ADR-002: Observability Stack for Chaos Experiments

**Date:** 2026-03-18

**Status:** Accepted

## Context

ChaosGuard's current chaos probes are limited to HTTP health checks that verify
whether a service responds with a 2xx status code. This provides only a binary
alive/dead signal and misses critical behavioral changes such as:

- Latency degradation under fault injection.
- Error rate spikes that recover before the next probe interval.
- Resource exhaustion (CPU, memory, file descriptors) on the target.
- Cascading failures across dependent services.

Without real metrics captured before, during, and after chaos experiments, it is
impossible to measure resilience quantitatively or detect regressions over time.

## Decision

We will adopt a vendor-neutral observability stack:

- **OpenTelemetry Collector** as the unified ingestion layer for metrics, traces,
  and logs. Target applications export telemetry via OTLP; the collector routes
  data to the appropriate backends.
- **Prometheus** for metrics storage and querying. The collector writes to
  Prometheus via remote-write. ChaosGuard queries Prometheus to compute
  resilience scores.
- **Grafana** for visualization. Pre-built dashboards display experiment
  timelines, SLI compliance, and comparative before/after views.
- **Automatic dashboard annotations** — when a chaos experiment starts or stops,
  ChaosGuard pushes an annotation to Grafana so that metric graphs clearly show
  the fault injection window.

## Consequences

- **Additional infrastructure** is required: Prometheus, Grafana, and the
  OpenTelemetry Collector must be deployed alongside ChaosGuard (Docker Compose
  profiles will be provided for local development).
- **Target applications must be instrumented** or fronted by sidecar proxies
  (e.g., Envoy) that emit OTLP telemetry. Uninstrumented targets will fall back
  to the existing HTTP health-check probes.
- The ChaosGuard backend must integrate with the Prometheus query API to
  calculate pre/post metrics deltas for resilience scoring.
- Grafana dashboard JSON models will be version-controlled in `infra/grafana/`.
