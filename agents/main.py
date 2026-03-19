import asyncio
import json
import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import psycopg2
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import config
from orchestrator import Orchestrator, ScanState
from generators.report_generator import ReportGenerator
from generators.fix_generator import FixGenerator

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

orchestrator = Orchestrator()
report_generator = ReportGenerator()
fix_generator = FixGenerator()


# ---------------------------------------------------------------------------
# Kafka consumer (background thread)
# ---------------------------------------------------------------------------

def _kafka_consumer_loop():
    """Background thread that consumes index-complete events from Kafka."""
    try:
        from confluent_kafka import Consumer, KafkaError
    except ImportError:
        logger.warning("confluent_kafka not installed; Kafka consumer disabled.")
        return

    consumer_conf = {
        "bootstrap.servers": config.KAFKA_BOOTSTRAP,
        "group.id": "chaosguard-agents",
        "auto.offset.reset": "latest",
        "enable.auto.commit": True,
    }

    consumer = Consumer(consumer_conf)
    consumer.subscribe([config.TOPIC_INDEX_COMPLETE])
    logger.info("Kafka consumer started, subscribed to %s", config.TOPIC_INDEX_COMPLETE)

    loop = asyncio.new_event_loop()

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("Kafka consumer error: %s", msg.error())
                continue

            try:
                event = json.loads(msg.value().decode("utf-8"))
                logger.info("Received index-complete event: %s", event.get("scan_id", "unknown"))
                loop.run_until_complete(_process_scan_event(event))
            except Exception as exc:
                logger.error("Failed to process Kafka message: %s", exc)
    except Exception as exc:
        logger.error("Kafka consumer loop error: %s", exc)
    finally:
        consumer.close()
        loop.close()


async def _process_scan_event(event: dict):
    """Process an index-complete event: run orchestrator, save findings, publish results."""
    scan_id = event.get("scan_id", str(uuid.uuid4()))
    repo_url = event.get("repo_url", "")
    tier = event.get("tier", "RECON")
    repo_metadata = event.get("repo_metadata", event.get("metadata", {}))
    clone_path = event.get("clone_path", "")
    target_url = event.get("target_url", "")

    logger.info("Processing scan %s (tier=%s, repo=%s)", scan_id, tier, repo_url)

    try:
        # Update scan status to running
        _update_scan_db(scan_id, "running", None)

        # Run orchestrator
        state = await orchestrator.run(
            scan_id=scan_id,
            tier=tier,
            repo_url=repo_url,
            repo_metadata=repo_metadata,
            recon_findings=[],
            clone_path=clone_path,
            target_url=target_url,
        )

        # Generate fixes
        findings_with_fixes = await fix_generator.generate_fixes(state["findings"], tier.upper(), clone_path=state.get("clone_path", ""))
        state["findings"] = findings_with_fixes

        # Generate report
        report = report_generator.generate(
            scan_id=scan_id,
            tier=tier.upper(),
            repo_url=repo_url,
            findings=state["findings"],
            chaos_scenarios=state.get("chaos_scenarios"),
            attack_chains=state.get("attack_chains"),
            pentest_playbook=state.get("pentest_playbook"),
        )

        # Save findings to PostgreSQL
        _save_findings_to_db(scan_id, state["findings"], report)

        # Update scan status to complete
        _update_scan_db(scan_id, "completed", None)

        # Publish scan-complete event to Kafka
        _publish_scan_complete(scan_id, tier, repo_url, report)

        logger.info("Scan %s completed: %d findings", scan_id, len(state["findings"]))

    except Exception as exc:
        logger.error("Scan %s failed: %s", scan_id, exc)
        _update_scan_db(scan_id, "failed", str(exc))


def _update_scan_db(scan_id: str, status: str, error_message: str | None):
    """Update scan status in PostgreSQL."""
    try:
        conn = psycopg2.connect(config.POSTGRES_DSN)
        try:
            with conn.cursor() as cur:
                if error_message:
                    cur.execute(
                        "UPDATE scans SET status = %s, error_message = %s, updated_at = NOW() WHERE id = %s::uuid",
                        (status, error_message[:2000], scan_id),
                    )
                else:
                    cur.execute(
                        "UPDATE scans SET status = %s, updated_at = NOW() WHERE id = %s::uuid",
                        (status, scan_id),
                    )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Failed to update scan status: %s", exc)


def _save_findings_to_db(scan_id: str, findings: list[dict], report: dict):
    """Persist findings and report to PostgreSQL."""
    try:
        conn = psycopg2.connect(config.POSTGRES_DSN)
        try:
            with conn.cursor() as cur:
                # Save individual findings
                saved = 0
                for finding in findings:
                    try:
                        line_val = finding.get("line", finding.get("line_start"))
                        if isinstance(line_val, list):
                            line_val = line_val[0] if line_val else None
                        if isinstance(line_val, str):
                            line_val = int(line_val) if line_val.isdigit() else None
                        severity = finding.get("severity", "MEDIUM")
                        if isinstance(severity, str):
                            severity = severity.upper()
                        if severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
                            severity = "MEDIUM"
                        cur.execute(
                            """
                            INSERT INTO findings (scan_id, vulnerability_type, severity, title,
                                                  description, file_path, line_start, code_snippet,
                                                  remediation, owasp_category, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                scan_id,
                                finding.get("category", finding.get("vulnerability_type", "unknown"))[:200],
                                severity,
                                finding.get("title", "")[:500],
                                finding.get("description", ""),
                                finding.get("file_path", "")[:500],
                                line_val,
                                finding.get("evidence", finding.get("code_snippet", "")),
                                finding.get("remediation", ""),
                                finding.get("owasp_category", "")[:100],
                                json.dumps(finding),
                            ),
                        )
                        saved += 1
                    except Exception as exc:
                        logger.warning("Failed to save finding: %s", exc)
                        conn.rollback()
                logger.info("Saved %d/%d findings for scan %s", saved, len(findings), scan_id)

                # Save full report
                cur.execute(
                    """
                    INSERT INTO reports (scan_id, report_data, created_at)
                    VALUES (%s, %s, NOW())
                    """,
                    (scan_id, json.dumps(report)),
                )

            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Failed to save findings to database: %s", exc)


def _publish_scan_complete(scan_id: str, tier: str, repo_url: str, report: dict):
    """Publish scan-complete event to Kafka."""
    try:
        from confluent_kafka import Producer

        producer = Producer({"bootstrap.servers": config.KAFKA_BOOTSTRAP})
        event = {
            "scan_id": scan_id,
            "tier": tier,
            "repo_url": repo_url,
            "status": "completed",
            "total_findings": report.get("summary", {}).get("total_findings", 0),
            "by_severity": report.get("summary", {}).get("by_severity", {}),
            "completed_at": datetime.utcnow().isoformat(),
        }
        producer.produce(
            config.TOPIC_SCAN_COMPLETE,
            key=scan_id,
            value=json.dumps(event).encode("utf-8"),
        )
        producer.flush(timeout=10)
        logger.info("Published scan-complete event for %s", scan_id)
    except Exception as exc:
        logger.error("Failed to publish scan-complete event: %s", exc)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the Kafka consumer thread on startup (only when WORKER_TIER is unset)."""
    worker_tier = os.getenv("WORKER_TIER", "")
    if not worker_tier:
        kafka_thread = threading.Thread(target=_kafka_consumer_loop, daemon=True)
        kafka_thread.start()
        logger.info("ChaosGuard Agents service started (with Kafka consumer)")
    else:
        logger.info("ChaosGuard Agents service started (WORKER_TIER=%s, Kafka consumer disabled)", worker_tier)
    yield
    logger.info("ChaosGuard Agents service shutting down")


app = FastAPI(
    title="ChaosGuard AI - Agents Service",
    description="Multi-tier security analysis agents powered by local LLMs",
    version="1.0.0",
    lifespan=lifespan,
)


class AnalyzeRequest(BaseModel):
    scan_id: str | None = None
    repo_url: str
    tier: str = "RECON"
    repo_metadata: dict = {}
    clone_path: str = ""
    target_url: str = ""


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="chaosguard-agents",
        version="1.0.0",
    )


@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    """Manually trigger a scan analysis."""
    scan_id = request.scan_id or str(uuid.uuid4())
    tier = request.tier.upper()

    if tier not in ("RECON", "HUNTER", "SIEGE", "LIVE"):
        raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}. Must be RECON, HUNTER, SIEGE, or LIVE.")

    logger.info("Manual analysis triggered: scan_id=%s, tier=%s, repo=%s", scan_id, tier, request.repo_url)

    try:
        state = await orchestrator.run(
            scan_id=scan_id,
            tier=tier,
            repo_url=request.repo_url,
            repo_metadata=request.repo_metadata,
            recon_findings=[],
            clone_path=request.clone_path,
            target_url=request.target_url,
        )

        # Generate fixes
        findings_with_fixes = await fix_generator.generate_fixes(state["findings"], tier, clone_path=state.get("clone_path", ""))
        state["findings"] = findings_with_fixes

        # Generate report
        report = report_generator.generate(
            scan_id=scan_id,
            tier=tier,
            repo_url=request.repo_url,
            findings=state["findings"],
            chaos_scenarios=state.get("chaos_scenarios"),
            attack_chains=state.get("attack_chains"),
            pentest_playbook=state.get("pentest_playbook"),
        )

        return report

    except Exception as exc:
        logger.error("Analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(exc)}")


# ---------------------------------------------------------------------------
# Chaos Execution API
# ---------------------------------------------------------------------------

class ChaosExecuteRequest(BaseModel):
    scan_id: str
    scenario: dict
    clone_path: str
    auto_approve: bool = False


class ChaosApprovalRequest(BaseModel):
    experiment_id: str
    action: str  # "approve" or "reject"


class ChaosAbortRequest(BaseModel):
    scan_id: str


@app.post("/chaos/execute")
async def execute_chaos(request: ChaosExecuteRequest):
    """Execute a chaos experiment against a sandboxed Docker Compose application."""
    from chaos_executor.runner import ExperimentRunner

    runner = ExperimentRunner()

    # Run in background so the HTTP call returns immediately
    async def _run():
        return await runner.run_experiment(
            scan_id=request.scan_id,
            scenario=request.scenario,
            clone_path=request.clone_path,
            auto_approve=request.auto_approve,
        )

    task = asyncio.create_task(_run())

    # Return the experiment ID immediately — client polls for status
    # Wait briefly for the planning phase to get the experiment ID
    await asyncio.sleep(1)
    return {
        "status": "started",
        "message": "Chaos experiment initiated. Poll /chaos/status for updates.",
        "scan_id": request.scan_id,
    }


@app.post("/chaos/approve")
async def approve_chaos(request: ChaosApprovalRequest):
    """Approve or reject a pending chaos experiment."""
    from chaos_executor.safety import SafetyController

    safety = SafetyController()
    if request.action == "approve":
        safety.approve(request.experiment_id)
        return {"status": "approved", "experiment_id": request.experiment_id}
    elif request.action == "reject":
        safety.reject(request.experiment_id)
        return {"status": "rejected", "experiment_id": request.experiment_id}
    else:
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")


@app.post("/chaos/abort")
async def abort_chaos(request: ChaosAbortRequest):
    """Emergency stop — immediately rolls back all faults and tears down sandbox."""
    from chaos_executor.safety import SafetyController

    safety = SafetyController()
    safety.trigger_emergency_stop(request.scan_id)
    return {"status": "abort_triggered", "scan_id": request.scan_id}


@app.get("/chaos/experiments/{scan_id}")
async def get_chaos_experiments(scan_id: str):
    """Get all chaos experiments for a scan."""
    try:
        conn = psycopg2.connect(config.POSTGRES_DSN)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, scenario_id, status, experiment_plan,
                              resilience_score, recovery_time_s, verdict,
                              recommendations, faults_injected,
                              baseline_metrics, chaos_metrics, recovery_metrics,
                              health_timeline, started_at, completed_at
                       FROM chaos_experiments WHERE scan_id = %s::uuid
                       ORDER BY created_at DESC""",
                    (scan_id,),
                )
                rows = cur.fetchall()
                experiments = []
                for row in rows:
                    experiments.append({
                        "id": str(row[0]),
                        "scenarioId": row[1],
                        "status": row[2],
                        "experimentPlan": row[3],
                        "resilienceScore": row[4],
                        "recoveryTimeS": row[5],
                        "verdict": row[6],
                        "recommendations": row[7],
                        "faultsInjected": row[8],
                        "baselineMetrics": row[9],
                        "chaosMetrics": row[10],
                        "recoveryMetrics": row[11],
                        "healthTimeline": row[12],
                        "startedAt": str(row[13]) if row[13] else None,
                        "completedAt": str(row[14]) if row[14] else None,
                    })
                return {"experiments": experiments}
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("AGENTS_PORT", "8001")),
        reload=False,
        log_level="info",
    )
