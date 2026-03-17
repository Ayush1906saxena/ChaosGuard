import logging
import traceback
from enum import Enum
from typing import Any, Optional

import psycopg2

from config import config

logger = logging.getLogger(__name__)


class ErrorAction(str, Enum):
    RETRY = "retry"
    SKIP = "skip"
    FAIL_SCAN = "fail_scan"
    DEGRADE = "degrade"


# Maps exception type names to the action we should take
ERROR_MAP: dict[str, ErrorAction] = {
    "ConnectError": ErrorAction.RETRY,
    "ReadTimeout": ErrorAction.RETRY,
    "TimeoutException": ErrorAction.RETRY,
    "HTTPStatusError": ErrorAction.RETRY,
    "ConnectionRefusedError": ErrorAction.RETRY,

    "JSONDecodeError": ErrorAction.SKIP,
    "ValidationError": ErrorAction.SKIP,
    "KeyError": ErrorAction.SKIP,
    "IndexError": ErrorAction.SKIP,

    "MemoryError": ErrorAction.FAIL_SCAN,
    "SystemExit": ErrorAction.FAIL_SCAN,
    "PermissionError": ErrorAction.FAIL_SCAN,

    "ChromaDBError": ErrorAction.DEGRADE,
    "KafkaException": ErrorAction.DEGRADE,
    "OperationalError": ErrorAction.DEGRADE,
}


def _resolve_action(error: Exception) -> ErrorAction:
    """Determine the action for a given exception."""
    type_name = type(error).__name__
    if type_name in ERROR_MAP:
        return ERROR_MAP[type_name]
    # Walk the MRO for base-class matches
    for cls in type(error).__mro__:
        if cls.__name__ in ERROR_MAP:
            return ERROR_MAP[cls.__name__]
    return ErrorAction.SKIP


async def handle_error(
    error: Exception,
    scan_id: Optional[str] = None,
    context: str = "",
    update_status: bool = True,
) -> ErrorAction:
    """Central error handler: logs the error and optionally updates scan status.

    Args:
        error: The exception that occurred.
        scan_id: Associated scan UUID (if any).
        context: Human-readable description of where the error happened.
        update_status: Whether to update the scan row in Postgres.

    Returns:
        The ErrorAction indicating how the caller should proceed.
    """
    action = _resolve_action(error)
    tb = traceback.format_exception(type(error), error, error.__traceback__)

    logger.error(
        "Error in %s | action=%s | scan_id=%s | %s\n%s",
        context,
        action.value,
        scan_id or "N/A",
        str(error),
        "".join(tb),
    )

    if update_status and scan_id and action == ErrorAction.FAIL_SCAN:
        await _update_scan_status(scan_id, "failed", str(error))
    elif update_status and scan_id and action == ErrorAction.DEGRADE:
        await _update_scan_status(scan_id, "degraded", str(error))

    return action


async def _update_scan_status(
    scan_id: str,
    status: str,
    error_message: str,
) -> None:
    """Write scan failure/degradation status to Postgres."""
    try:
        conn = psycopg2.connect(config.POSTGRES_DSN)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE scans
                    SET status = %s, error_message = %s, updated_at = NOW()
                    WHERE scan_id = %s
                    """,
                    (status, error_message[:2000], scan_id),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as db_err:
        logger.error("Failed to update scan status in DB: %s", str(db_err))
