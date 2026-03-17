"""Tier-specific worker entry point.

Accepts WORKER_TIER env var (RECON, HUNTER, or SIEGE) and subscribes only
to the corresponding tier-specific Kafka topic, invoking the relevant
orchestrator method.
"""
import asyncio
import json
import logging
import os
import uuid

from config import config
from orchestrator import Orchestrator
from generators.fix_generator import FixGenerator
from generators.report_generator import ReportGenerator

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

WORKER_TIER = os.getenv("WORKER_TIER", "").upper()
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", f"chaosguard-agents-{WORKER_TIER.lower()}")

TIER_TOPIC_MAP = {
    "RECON": config.TOPIC_SCAN_RECON,
    "HUNTER": config.TOPIC_SCAN_HUNTER,
    "SIEGE": config.TOPIC_SCAN_SIEGE,
}

orchestrator = Orchestrator()
fix_generator = FixGenerator()
report_generator = ReportGenerator()


def _update_scan_db(scan_id: str, status: str, error_message: str | None):
    """Update scan status in PostgreSQL."""
    try:
        import psycopg2
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
    """Persist findings, generated fixes, and report to PostgreSQL."""
    try:
        import psycopg2
        conn = psycopg2.connect(config.POSTGRES_DSN)
        try:
            with conn.cursor() as cur:
                for finding in findings:
                    cur.execute(
                        """
                        INSERT INTO findings (scan_id, vulnerability_type, severity, title,
                                              description, file_path, line_start, code_snippet,
                                              remediation, owasp_category, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            scan_id,
                            finding.get("category", "unknown"),
                            finding.get("severity", "MEDIUM").upper(),
                            str(finding.get("title", "")),
                            finding.get("description", ""),
                            str(finding.get("file_path", "")),
                            finding.get("line", 0),
                            str(finding.get("evidence", "")),
                            finding.get("remediation", ""),
                            finding.get("owasp_category", ""),
                            json.dumps(finding),
                        ),
                    )
                    row = cur.fetchone()
                    finding_db_id = row[0] if row else None

                    # Persist generated fix to generated_fixes table
                    fix = finding.get("fix")
                    if fix and finding_db_id:
                        validation = fix.get("validation", {})
                        confidence = validation.get("confidence", 50) if validation else 50
                        cur.execute(
                            """
                            INSERT INTO generated_fixes (scan_id, finding_id, file_path,
                                original_code, fixed_code, diff_patch, explanation,
                                confidence_score, syntax_valid, compile_valid,
                                tests_pass, sandbox_output, metadata)
                            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                scan_id,
                                finding_db_id,
                                str(finding.get("file_path", "")),
                                str(fix.get("original_code", "")),
                                str(fix.get("fixed_code", "")),
                                fix.get("diff", ""),
                                fix.get("description", ""),
                                confidence,
                                fix.get("syntax_valid"),
                                fix.get("compile_valid"),
                                fix.get("tests_pass"),
                                fix.get("sandbox_output", ""),
                                json.dumps(validation),
                            ),
                        )

                # Delete existing report for this scan, then insert new one
                cur.execute("DELETE FROM reports WHERE scan_id = %s::uuid", (scan_id,))
                cur.execute(
                    "INSERT INTO reports (scan_id, report_data, created_at) VALUES (%s, %s, NOW())",
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
        from datetime import datetime
        producer = Producer({"bootstrap.servers": config.KAFKA_BOOTSTRAP})
        event = {
            "scanId": scan_id,
            "tier": tier,
            "repoUrl": repo_url,
            "status": "COMPLETE",
            "summary": report.get("summary", {}),
            "completedAt": datetime.utcnow().isoformat(),
        }
        producer.produce(
            config.TOPIC_SCAN_COMPLETE,
            key=scan_id,
            value=json.dumps(event).encode("utf-8"),
        )
        producer.flush(timeout=10)
    except Exception as exc:
        logger.error("Failed to publish scan-complete event: %s", exc)


async def _process_tier_event(event: dict):
    """Process a tier-specific event using only the relevant orchestrator method."""
    scan_id = event.get("scan_id", str(uuid.uuid4()))
    repo_url = event.get("repo_url", "")
    tier = event.get("tier", WORKER_TIER)
    repo_metadata = event.get("repo_metadata", event.get("metadata", {}))
    clone_path = event.get("clone_path", "")
    target_url = event.get("target_url", event.get("targetUrl", ""))

    logger.info("[%s worker] Processing scan %s (repo=%s)", WORKER_TIER, scan_id, repo_url)

    try:
        _update_scan_db(scan_id, "ANALYZING", None)

        state = await orchestrator.run(
            scan_id=scan_id,
            tier=tier,
            repo_url=repo_url,
            repo_metadata=repo_metadata,
            recon_findings=[],
            clone_path=clone_path,
            target_url=target_url,
        )

        findings_with_fixes = await fix_generator.generate_fixes(state["findings"], tier, clone_path=clone_path)
        state["findings"] = findings_with_fixes

        report = report_generator.generate(
            scan_id=scan_id,
            tier=tier,
            repo_url=repo_url,
            findings=state["findings"],
            chaos_scenarios=state.get("chaos_scenarios"),
            attack_chains=state.get("attack_chains"),
            pentest_playbook=state.get("pentest_playbook"),
        )

        _save_findings_to_db(scan_id, state["findings"], report)
        _update_scan_db(scan_id, "COMPLETE", None)
        _publish_scan_complete(scan_id, tier, repo_url, report)

        logger.info("[%s worker] Scan %s completed: %d findings", WORKER_TIER, scan_id, len(state["findings"]))

    except Exception as exc:
        logger.error("[%s worker] Scan %s failed: %s", WORKER_TIER, scan_id, exc)
        _update_scan_db(scan_id, "FAILED", str(exc))


def run_worker():
    """Main loop for tier-specific worker."""
    if WORKER_TIER not in TIER_TOPIC_MAP:
        logger.error("Invalid WORKER_TIER=%s. Must be RECON, HUNTER, or SIEGE.", WORKER_TIER)
        return

    topic = TIER_TOPIC_MAP[WORKER_TIER]
    logger.info("Starting %s tier worker, subscribing to %s (group=%s)", WORKER_TIER, topic, KAFKA_GROUP_ID)

    try:
        from confluent_kafka import Consumer, KafkaError
    except ImportError:
        logger.error("confluent_kafka not installed; cannot start worker.")
        return

    consumer = Consumer({
        "bootstrap.servers": config.KAFKA_BOOTSTRAP,
        "group.id": KAFKA_GROUP_ID,
        "auto.offset.reset": "latest",
        "enable.auto.commit": True,
    })
    consumer.subscribe([topic])

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
                logger.info("[%s worker] Received event for scan %s", WORKER_TIER, event.get("scan_id", "unknown"))
                loop.run_until_complete(_process_tier_event(event))
            except Exception as exc:
                logger.error("Failed to process Kafka message: %s", exc)
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")
    finally:
        consumer.close()
        loop.close()


if __name__ == "__main__":
    run_worker()
