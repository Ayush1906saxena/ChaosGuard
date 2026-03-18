"""GameDay Framework — structured chaos experiment management, scheduling, and progressive rollout.

Provides the scaffolding to define, catalog, schedule, and run collections
of chaos experiments as part of recurring GameDay exercises.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import psycopg2

from config import config
from chaos_executor.hypothesis import SteadyStateHypothesis, Comparison

logger = logging.getLogger(__name__)


# ── Data Models ──────────────────────────────────────────────────────

@dataclass
class ExperimentDefinition:
    """A reusable, cataloged chaos experiment definition."""

    name: str
    description: str
    scenario: dict  # Raw scenario dict fed to ScenarioTranslator
    target_services: list[str] = field(default_factory=list)
    hypotheses: list[SteadyStateHypothesis] = field(default_factory=list)
    blast_radius: int = 1  # Max number of services affected simultaneously
    schedule: str = ""  # Cron-style schedule string (e.g. "0 9 * * 1")
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "scenario": self.scenario,
            "target_services": self.target_services,
            "blast_radius": self.blast_radius,
            "schedule": self.schedule,
            "tags": self.tags,
            "created_at": self.created_at,
            "hypotheses": [
                {
                    "name": h.name,
                    "metric": h.metric,
                    "threshold": h.threshold,
                    "comparison": h.comparison.value,
                    "tolerance_pct": h.tolerance_pct,
                }
                for h in self.hypotheses
            ],
        }


@dataclass
class GameDayRun:
    """Record of a single GameDay execution."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    experiment_ids: list[str] = field(default_factory=list)
    experiment_results: list[dict] = field(default_factory=list)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, ABORTED
    started_at: str = ""
    completed_at: str = ""
    overall_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "experiment_ids": self.experiment_ids,
            "experiment_results": self.experiment_results,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "overall_score": self.overall_score,
        }


# ── Experiment Catalog ───────────────────────────────────────────────

class ExperimentCatalog:
    """Stores and retrieves experiment definitions from PostgreSQL."""

    def __init__(self):
        self._dsn = config.POSTGRES_DSN

    def _get_conn(self):
        return psycopg2.connect(self._dsn)

    def save(self, definition: ExperimentDefinition) -> None:
        """Save or update an experiment definition."""
        try:
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO chaos_experiment_catalog
                            (id, name, description, scenario, target_services,
                             hypotheses, blast_radius, schedule, tags, created_at)
                        VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            scenario = EXCLUDED.scenario,
                            target_services = EXCLUDED.target_services,
                            hypotheses = EXCLUDED.hypotheses,
                            blast_radius = EXCLUDED.blast_radius,
                            schedule = EXCLUDED.schedule,
                            tags = EXCLUDED.tags
                        """,
                        (
                            definition.id,
                            definition.name,
                            definition.description,
                            json.dumps(definition.scenario),
                            json.dumps(definition.target_services),
                            json.dumps([
                                {
                                    "name": h.name,
                                    "metric": h.metric,
                                    "threshold": h.threshold,
                                    "comparison": h.comparison.value,
                                    "tolerance_pct": h.tolerance_pct,
                                }
                                for h in definition.hypotheses
                            ]),
                            definition.blast_radius,
                            definition.schedule,
                            json.dumps(definition.tags),
                            definition.created_at,
                        ),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[catalog] Failed to save experiment definition: %s", exc)

    def get(self, definition_id: str) -> Optional[ExperimentDefinition]:
        """Retrieve an experiment definition by ID."""
        try:
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, name, description, scenario, target_services, "
                        "hypotheses, blast_radius, schedule, tags, created_at "
                        "FROM chaos_experiment_catalog WHERE id = %s::uuid",
                        (definition_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    return self._row_to_definition(row)
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[catalog] Failed to get experiment definition: %s", exc)
            return None

    def list_all(self, tag: Optional[str] = None) -> list[ExperimentDefinition]:
        """List all experiment definitions, optionally filtered by tag."""
        try:
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    if tag:
                        cur.execute(
                            "SELECT id, name, description, scenario, target_services, "
                            "hypotheses, blast_radius, schedule, tags, created_at "
                            "FROM chaos_experiment_catalog WHERE tags::jsonb ? %s "
                            "ORDER BY created_at DESC",
                            (tag,),
                        )
                    else:
                        cur.execute(
                            "SELECT id, name, description, scenario, target_services, "
                            "hypotheses, blast_radius, schedule, tags, created_at "
                            "FROM chaos_experiment_catalog ORDER BY created_at DESC"
                        )
                    rows = cur.fetchall()
                    return [self._row_to_definition(r) for r in rows]
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[catalog] Failed to list experiment definitions: %s", exc)
            return []

    def delete(self, definition_id: str) -> bool:
        """Delete an experiment definition by ID."""
        try:
            conn = self._get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM chaos_experiment_catalog WHERE id = %s::uuid",
                        (definition_id,),
                    )
                    deleted = cur.rowcount > 0
                conn.commit()
                return deleted
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[catalog] Failed to delete experiment definition: %s", exc)
            return False

    @staticmethod
    def _row_to_definition(row: tuple) -> ExperimentDefinition:
        """Convert a database row to an ExperimentDefinition."""
        (def_id, name, description, scenario, target_services,
         hypotheses_json, blast_radius, schedule, tags, created_at) = row

        scenario_data = json.loads(scenario) if isinstance(scenario, str) else scenario
        targets = json.loads(target_services) if isinstance(target_services, str) else target_services
        tags_data = json.loads(tags) if isinstance(tags, str) else tags

        hypotheses_data = json.loads(hypotheses_json) if isinstance(hypotheses_json, str) else hypotheses_json
        hypotheses = []
        for h in (hypotheses_data or []):
            hypotheses.append(SteadyStateHypothesis(
                name=h["name"],
                metric=h["metric"],
                threshold=h["threshold"],
                comparison=Comparison(h.get("comparison", "less_than")),
                tolerance_pct=h.get("tolerance_pct", 10.0),
            ))

        return ExperimentDefinition(
            id=str(def_id),
            name=name,
            description=description or "",
            scenario=scenario_data,
            target_services=targets or [],
            hypotheses=hypotheses,
            blast_radius=blast_radius or 1,
            schedule=schedule or "",
            tags=tags_data or [],
            created_at=str(created_at) if created_at else "",
        )


# ── GameDay Scheduler ────────────────────────────────────────────────

class GameDayScheduler:
    """Manages cron-style scheduling for GameDay experiments."""

    def __init__(self, catalog: Optional[ExperimentCatalog] = None):
        self.catalog = catalog or ExperimentCatalog()

    def is_due(self, schedule: str, now: Optional[datetime] = None) -> bool:
        """Check if a cron-style schedule is due at the given time.

        Supports simplified cron format: "minute hour day_of_month month day_of_week"
        where * means any value.
        """
        if not schedule or not schedule.strip():
            return False

        now = now or datetime.utcnow()
        parts = schedule.strip().split()
        if len(parts) != 5:
            logger.warning("[scheduler] Invalid cron format: '%s'", schedule)
            return False

        fields = [
            (parts[0], now.minute, 0, 59),
            (parts[1], now.hour, 0, 23),
            (parts[2], now.day, 1, 31),
            (parts[3], now.month, 1, 12),
            (parts[4], now.weekday(), 0, 6),  # Monday=0
        ]

        for cron_val, current_val, min_val, max_val in fields:
            if cron_val == "*":
                continue
            try:
                if "/" in cron_val:
                    # Step values like */5
                    _, step = cron_val.split("/")
                    if current_val % int(step) != 0:
                        return False
                elif "," in cron_val:
                    # List values like 1,3,5
                    values = [int(v) for v in cron_val.split(",")]
                    if current_val not in values:
                        return False
                elif "-" in cron_val:
                    # Range values like 1-5
                    low, high = cron_val.split("-")
                    if not (int(low) <= current_val <= int(high)):
                        return False
                else:
                    if int(cron_val) != current_val:
                        return False
            except (ValueError, TypeError):
                logger.warning("[scheduler] Failed to parse cron field: '%s'", cron_val)
                return False

        return True

    def get_due_experiments(self, now: Optional[datetime] = None) -> list[ExperimentDefinition]:
        """Return all cataloged experiments whose schedule is currently due."""
        all_defs = self.catalog.list_all()
        return [d for d in all_defs if self.is_due(d.schedule, now)]

    def next_run_estimate(self, schedule: str, from_time: Optional[datetime] = None) -> Optional[datetime]:
        """Estimate the next run time by checking minute-by-minute for up to 7 days."""
        if not schedule:
            return None
        start = from_time or datetime.utcnow()
        check = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
        limit = start + timedelta(days=7)
        while check < limit:
            if self.is_due(schedule, check):
                return check
            check += timedelta(minutes=1)
        return None


# ── Progressive Rollout ──────────────────────────────────────────────

class ProgressiveRollout:
    """Manages escalation from single-service to multi-service fault injection.

    Progressive rollout starts with the narrowest blast radius and only
    escalates if the system remains healthy at each stage.
    """

    def __init__(self, target_services: list[str], max_blast_radius: int = 3):
        self.target_services = target_services
        self.max_blast_radius = min(max_blast_radius, len(target_services))
        self._current_stage: int = 0
        self._stage_results: list[dict] = []

    @property
    def current_stage(self) -> int:
        return self._current_stage

    @property
    def total_stages(self) -> int:
        return self.max_blast_radius

    def get_current_targets(self) -> list[str]:
        """Return the services targeted in the current stage."""
        count = min(self._current_stage + 1, len(self.target_services))
        return self.target_services[:count]

    def advance(self, stage_passed: bool, metrics: Optional[dict] = None) -> bool:
        """Record the result of the current stage and advance if passed.

        Returns True if there are more stages to run, False if rollout is complete.
        """
        self._stage_results.append({
            "stage": self._current_stage,
            "targets": self.get_current_targets(),
            "passed": stage_passed,
            "metrics": metrics or {},
            "timestamp": time.time(),
        })

        if not stage_passed:
            logger.info(
                "[rollout] Stage %d failed — halting progressive rollout",
                self._current_stage,
            )
            return False

        self._current_stage += 1
        if self._current_stage >= self.max_blast_radius:
            logger.info("[rollout] All %d stages completed successfully", self.max_blast_radius)
            return False

        logger.info(
            "[rollout] Stage %d passed — escalating to %d services",
            self._current_stage - 1,
            self._current_stage + 1,
        )
        return True

    def summary(self) -> dict:
        """Return a summary of the progressive rollout."""
        completed = len(self._stage_results)
        all_passed = all(r["passed"] for r in self._stage_results)
        return {
            "total_stages": self.total_stages,
            "completed_stages": completed,
            "all_passed": all_passed,
            "stages": self._stage_results,
        }


# ── GameDay Orchestrator ─────────────────────────────────────────────

class GameDay:
    """Manages a collection of chaos experiments as a structured GameDay exercise."""

    def __init__(self, name: str, experiments: Optional[list[ExperimentDefinition]] = None):
        self.name = name
        self.experiments = experiments or []
        self._run: Optional[GameDayRun] = None
        self._catalog = ExperimentCatalog()

    def add_experiment(self, definition: ExperimentDefinition) -> None:
        """Add an experiment to this GameDay."""
        self.experiments.append(definition)

    def create_experiment(
        self,
        name: str,
        description: str,
        scenario: dict,
        target_services: Optional[list[str]] = None,
        blast_radius: int = 1,
        schedule: str = "",
        tags: Optional[list[str]] = None,
    ) -> ExperimentDefinition:
        """Create a new experiment definition and add it to this GameDay."""
        definition = ExperimentDefinition(
            name=name,
            description=description,
            scenario=scenario,
            target_services=target_services or [],
            blast_radius=blast_radius,
            schedule=schedule,
            tags=tags or [],
        )
        self.experiments.append(definition)
        self._catalog.save(definition)
        return definition

    def schedule_gameday(self, schedule: str) -> None:
        """Apply a cron schedule to all experiments in this GameDay."""
        for exp in self.experiments:
            exp.schedule = schedule
            self._catalog.save(exp)
        logger.info("[gameday] Scheduled %d experiments with cron: %s", len(self.experiments), schedule)

    async def run_gameday(
        self,
        runner,  # ExperimentRunner instance — avoids circular import
        scan_id: str,
        clone_path: str,
        auto_approve: bool = True,
    ) -> GameDayRun:
        """Execute all experiments in sequence, collecting results."""
        self._run = GameDayRun(
            name=self.name,
            experiment_ids=[e.id for e in self.experiments],
            status="RUNNING",
            started_at=datetime.utcnow().isoformat(),
        )

        for definition in self.experiments:
            logger.info("[gameday] Running experiment: %s", definition.name)
            try:
                result = await runner.run_experiment(
                    scan_id=scan_id,
                    scenario=definition.scenario,
                    clone_path=clone_path,
                    auto_approve=auto_approve,
                )
                self._run.experiment_results.append({
                    "definition_id": definition.id,
                    "name": definition.name,
                    "status": result.status,
                    "resilience_score": result.resilience_score,
                    "verdict": result.verdict,
                })
            except Exception as exc:
                logger.error("[gameday] Experiment '%s' failed: %s", definition.name, exc)
                self._run.experiment_results.append({
                    "definition_id": definition.id,
                    "name": definition.name,
                    "status": "ERROR",
                    "error": str(exc),
                })

        # Compute overall score
        scores = [
            r["resilience_score"]
            for r in self._run.experiment_results
            if "resilience_score" in r
        ]
        self._run.overall_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        self._run.status = "COMPLETED"
        self._run.completed_at = datetime.utcnow().isoformat()

        self._persist_run(self._run)
        return self._run

    def get_history(self, limit: int = 20) -> list[dict]:
        """Retrieve past GameDay runs from PostgreSQL."""
        try:
            conn = psycopg2.connect(config.POSTGRES_DSN)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, name, experiment_ids, experiment_results, status, "
                        "started_at, completed_at, overall_score "
                        "FROM chaos_gameday_runs ORDER BY started_at DESC LIMIT %s",
                        (limit,),
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "id": str(r[0]),
                            "name": r[1],
                            "experiment_ids": json.loads(r[2]) if isinstance(r[2], str) else r[2],
                            "experiment_results": json.loads(r[3]) if isinstance(r[3], str) else r[3],
                            "status": r[4],
                            "started_at": str(r[5]),
                            "completed_at": str(r[6]),
                            "overall_score": r[7],
                        }
                        for r in rows
                    ]
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[gameday] Failed to get history: %s", exc)
            return []

    def get_resilience_trends(self, days: int = 30) -> list[dict]:
        """Get resilience score trends over time from completed GameDay runs."""
        try:
            conn = psycopg2.connect(config.POSTGRES_DSN)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DATE(started_at) as day, AVG(overall_score) as avg_score, "
                        "COUNT(*) as run_count "
                        "FROM chaos_gameday_runs "
                        "WHERE status = 'COMPLETED' AND started_at > NOW() - INTERVAL '%s days' "
                        "GROUP BY DATE(started_at) ORDER BY day",
                        (days,),
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "date": str(r[0]),
                            "avg_resilience_score": round(float(r[1]), 1),
                            "run_count": r[2],
                        }
                        for r in rows
                    ]
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[gameday] Failed to get resilience trends: %s", exc)
            return []

    def _persist_run(self, run: GameDayRun) -> None:
        """Persist a GameDay run to PostgreSQL."""
        try:
            conn = psycopg2.connect(config.POSTGRES_DSN)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO chaos_gameday_runs
                            (id, name, experiment_ids, experiment_results, status,
                             started_at, completed_at, overall_score)
                        VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            experiment_results = EXCLUDED.experiment_results,
                            status = EXCLUDED.status,
                            completed_at = EXCLUDED.completed_at,
                            overall_score = EXCLUDED.overall_score
                        """,
                        (
                            run.id,
                            run.name,
                            json.dumps(run.experiment_ids),
                            json.dumps(run.experiment_results),
                            run.status,
                            run.started_at or None,
                            run.completed_at or None,
                            run.overall_score,
                        ),
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.error("[gameday] Failed to persist run: %s", exc)
