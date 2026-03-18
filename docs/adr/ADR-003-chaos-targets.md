# ADR-003: Chaos Execution Target Environments

**Date:** 2026-03-18

**Status:** Proposed

## Context

ChaosGuard currently executes chaos experiments exclusively in Docker Compose
sandboxes. While this provides a safe, repeatable environment for local
development and CI, production resilience testing requires injecting faults into
real staging and production infrastructure.

Target environments under consideration:

- **Docker Compose** — current approach, good for local and CI.
- **Kubernetes** — dominant orchestrator for production workloads.
- **Cloud-native fault injection** — AWS Fault Injection Simulator (FIS), GCP
  fault injection, Azure Chaos Studio.

## Decision

We will adopt a phased rollout:

- **Phase 1 (current):** Docker Compose sandboxes. Chaos agents use
  `docker exec`, `tc`, `iptables`, and `stress-ng` inside containers.
- **Phase 2:** Kubernetes support via integration with
  [chaos-mesh](https://chaos-mesh.org/) or
  [Litmus](https://litmuschaos.io/). ChaosGuard will generate
  `ChaosExperiment` CRDs and monitor their status through the Kubernetes API.
- **Phase 3:** Cloud-native fault injection. ChaosGuard will orchestrate
  experiments through provider-specific APIs (AWS FIS experiments, GCP fault
  injection policies) with a unified abstraction layer.

Each phase builds on the previous one — the experiment definition format remains
the same, and only the execution backend changes.

## Consequences

- **Kubernetes support** requires cluster access credentials and appropriate
  RBAC roles. ChaosGuard will need a ServiceAccount with permissions to create
  and watch CRDs in target namespaces.
- **Cloud-native support** requires provider-specific implementations behind a
  common interface. Each provider adapter must handle authentication, experiment
  creation, status polling, and cleanup.
- The experiment schema must be extended with a `target_environment` field that
  selects the execution backend.
- Blast radius controls become critical in Phase 2 and Phase 3 — experiments
  must declare affected namespaces/services and enforce approval gates.
