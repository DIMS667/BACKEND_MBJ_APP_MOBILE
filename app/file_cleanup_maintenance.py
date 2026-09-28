"""Run pending private-file deletion jobs from a scheduled maintenance task.

Usage after applying migrations::

    python -m app.file_cleanup_maintenance

The API also drains jobs after commits and on later requests. This command
ensures retries continue when there is no API traffic.
"""

import asyncio
import logging

from app.core.storage_cleanup import process_pending_file_deletions
from app.database import AsyncSessionLocal, engine


logger = logging.getLogger(__name__)


async def main() -> None:
    try:
        # A bounded run avoids an endless loop when permissions keep a job
        # from being deleted. Failed jobs remain in the table for the next run.
        for _ in range(100):
            async with AsyncSessionLocal() as db:
                try:
                    removed = await process_pending_file_deletions(db)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.exception("Private-file cleanup failed")
                    raise
            if removed == 0:
                break
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
