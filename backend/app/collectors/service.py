import logging
import os
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from app.collectors.base import BaseCollector
from app.collectors.goofish import GoofishCollector
from app.collectors.chotot import ChoTotCollector
from app.collectors.facebook_marketplace import FacebookMarketplaceCollector
from app.collectors.facebook_group import FacebookGroupCollector
from app.collectors.models import CollectorHealth
from app.taxonomy.models import DimSource

logger = logging.getLogger(__name__)

COLLECTOR_REGISTRY: Dict[str, type] = {
    "GOOFISH": GoofishCollector,
    "CHOTOT": ChoTotCollector,
    "FACEBOOK_MARKETPLACE": FacebookMarketplaceCollector,
    "FACEBOOK_GROUPS": FacebookGroupCollector,
}

def get_collector(source_code: str) -> BaseCollector:
    cls = COLLECTOR_REGISTRY.get(source_code.upper())
    if not cls:
        raise ValueError(f"Unknown collector source code: {source_code}")
    return cls()

def run_collector_job(source_code: str, query: str = "", **kwargs):
    """Entry point called by scheduler or API trigger."""
    db: Session = SessionLocal()
    try:
        collector = get_collector(source_code)
        logger.info(f"🚀 Starting background collector run: {source_code} (query='{query}', kwargs={kwargs})")
        result = collector.run(db, query=query, **kwargs)
        logger.info(f"🏁 Finished collector run: {source_code} - Result: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Collector job failed for {source_code}: {e}", exc_info=True)
        return {"status": "ERROR", "error": str(e)}
    finally:
        db.close()

def schedule_market_collectors():
    """
    Registers periodic collector jobs into APScheduler.
    Uses replace_existing=True to prevent duplicate jobs when container restarts.
    Configurable via environment variables.
    """
    from scheduler import scheduler

    # Configurable intervals (in minutes) with defaults
    intervals = {
        "GOOFISH": int(os.getenv("COLLECTOR_INTERVAL_GOOFISH", "10")),
        "CHOTOT": int(os.getenv("COLLECTOR_INTERVAL_CHOTOT", "30")),
        "FACEBOOK_MARKETPLACE": int(os.getenv("COLLECTOR_INTERVAL_FB_MARKETPLACE", "60")),
        "FACEBOOK_GROUPS": int(os.getenv("COLLECTOR_INTERVAL_FB_GROUPS", "90")),
    }

    # Query terms or targets
    default_queries = {
        "GOOFISH": "iPhone 16",
        "CHOTOT": "iphone 16",
        "FACEBOOK_MARKETPLACE": "rtx 4060",
        "FACEBOOK_GROUPS": os.getenv("COLLECTOR_QUERY_FB_GROUPS", "ram"),
    }

    for code, interval in intervals.items():
        job_id = f"collector_{code.lower()}"
        existing = scheduler.get_job(job_id)
        if existing:
            logger.info(f"Job {job_id} already scheduled, next run: {existing.next_run_time}")
            continue

        scheduler.add_job(
            run_collector_job,
            trigger="interval",
            minutes=interval,
            args=[code, default_queries.get(code, "")],
            id=job_id,
            max_instances=1,
            replace_existing=True,
            coalesce=True
        )
        logger.info(f"✅ Scheduled market collector {code} every {interval} minutes")

def get_all_collector_health(db: Session) -> List[Dict[str, Any]]:
    """Returns status of all collectors for monitoring and health API."""
    health_records = db.query(CollectorHealth).all()
    health_map = {h.source_code: h for h in health_records}

    results = []
    for code, cls in COLLECTOR_REGISTRY.items():
        h = health_map.get(code)
        results.append({
            "source": code,
            "status": h.status if h else "IDLE",
            "last_start": h.last_start if h else None,
            "last_success": h.last_success if h else None,
            "last_error": h.last_error if h else None,
            "items_scanned": h.items_scanned if h else 0,
            "items_new": h.items_new if h else 0,
            "auth_status": h.auth_status if h else "OK",
            "default_interval_minutes": cls.default_interval_minutes,
            "default_currency": cls.default_currency,
        })
    return results
