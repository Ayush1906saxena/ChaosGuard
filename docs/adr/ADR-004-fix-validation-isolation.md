# ADR-004: Fix Validation Isolation Strategy

**Date:** 2026-03-18

**Status:** Accepted

## Context

The current `sandbox_validator.py` applies generated fixes to a temporary copy
of the repository and runs language-specific compilation and test commands via
`subprocess.run()` directly on the host machine. This presents several risks:

- **Arbitrary code execution** — malicious or buggy build scripts
  (`setup.py`, `pom.xml` plugins, `package.json` scripts) run with the same
  privileges as the ChaosGuard process.
- **Host contamination** — builds may install packages globally, modify caches,
  or leave orphan processes.
- **No resource isolation** — a runaway build can consume all available CPU and
  memory on the host.

## Decision

All fix validation will run inside **ephemeral Docker containers** with strict
isolation:

- **Network disabled:** `--network none` prevents exfiltration and dependency
  fetching during validation (dependencies must already be present in the
  mounted workspace).
- **Read-only root filesystem:** `--read-only` with a writable workspace mount
  prevents writes outside the project directory.
- **Resource limits:** `--memory 1g` and `--cpus 1.0` cap resource usage per
  validation step.
- **Hard timeout:** `--stop-timeout 120` ensures containers are killed if they
  hang.
- **Language-specific base images:**
  - Python: `python:3.11-slim`
  - Java: `maven:3.9-eclipse-temurin-21`
  - JavaScript/TypeScript: `node:20-slim`

Each validation step (syntax check, compilation, test execution) runs in a fresh
container. The workspace directory is bind-mounted as the only writable path.

If Docker is not available on the host, the validator falls back to the original
`subprocess.run()` approach with a logged warning.

## Consequences

- **Slower validation** due to container startup overhead (~1-2 seconds per
  step). This is acceptable given that validation is not on the interactive
  critical path.
- **Docker must be available** in the validation environment. CI runners and
  production hosts must have the Docker daemon accessible.
- **First-run image pull latency** — base images must be pulled on first use.
  Pre-pulling images during deployment is recommended.
- **Dependency installation** cannot happen during validation (network is
  disabled). Projects that require `pip install` or `npm install` before
  compilation must have dependencies pre-installed in the workspace copy.
