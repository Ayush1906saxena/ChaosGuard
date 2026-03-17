"""Client for querying false positive feedback patterns from PostgreSQL.

Used by agents to inject known false positive patterns into prompts,
reducing repeated false positive findings.
"""
import logging

import psycopg2
import psycopg2.extras

from config import config

logger = logging.getLogger(__name__)


def get_fp_patterns_for_subcategory(subcategory: str) -> str:
    """Query PostgreSQL for false positive patterns matching the subcategory.

    Returns formatted text suitable for injection into agent system prompts.
    """
    try:
        conn = psycopg2.connect(config.POSTGRES_DSN)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT ff.code_fingerprint, f.title, f.evidence, ff.user_comment
                    FROM finding_feedback ff
                    JOIN findings f ON f.id = ff.finding_id
                    WHERE ff.label = 'FALSE_POSITIVE'
                      AND f.subcategory = %s
                    ORDER BY ff.created_at DESC
                    LIMIT 5
                    """,
                    (subcategory,),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        if not rows:
            return ""

        parts = ["=== KNOWN FALSE POSITIVE PATTERNS ==="]
        parts.append("The following patterns were previously marked as false positives by users.")
        parts.append("Avoid reporting similar patterns unless you have strong new evidence.\n")
        for row in rows:
            parts.append(f"- Title: {row['title']}")
            if row.get("evidence"):
                parts.append(f"  Evidence: {row['evidence'][:200]}")
            if row.get("user_comment"):
                parts.append(f"  User note: {row['user_comment']}")
            parts.append("")
        parts.append("=== END FALSE POSITIVE PATTERNS ===")
        return "\n".join(parts)
    except Exception as exc:
        logger.debug("Could not fetch FP patterns (table may not exist yet): %s", exc)
        return ""


def get_suppression_fingerprints() -> set[str]:
    """Get all code fingerprints that have 3+ false positive marks."""
    try:
        conn = psycopg2.connect(config.POSTGRES_DSN)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT code_fingerprint
                    FROM finding_feedback
                    WHERE label = 'FALSE_POSITIVE'
                    GROUP BY code_fingerprint
                    HAVING COUNT(*) >= 3
                    """
                )
                return {row[0] for row in cur.fetchall()}
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("Could not fetch suppression fingerprints: %s", exc)
        return set()
