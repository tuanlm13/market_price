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

def run_facebook_groups_periodic_job(source_code: str = "FACEBOOK_GROUPS", query: str = "ram, pocket 3"):
    """
    Quét định kỳ các hội nhóm Facebook cho danh sách từ khóa theo dõi.
    Hỗ trợ quét đa từ khóa (ví dụ: 'ram, pocket 3') mỗi chu kỳ.
    """
    queries = [q.strip() for q in query.split(",") if q.strip()]
    if not queries:
        queries = ["ram", "pocket 3"]
    for q in queries:
        try:
            logger.info(f"🔄 Periodic Facebook Group collector run for query: '{q}'")
            run_collector_job(source_code, query=q)
        except Exception as e:
            logger.error(f"❌ Error in periodic Facebook Group scan for '{q}': {e}")


def schedule_market_collectors():
    """
    Registers periodic collector jobs into APScheduler.
    Cấu hình mặc định quét Facebook Groups & Marketplace mỗi 5 phút một lần.
    Xóa cấu hình cũ trong JobStore để cập nhật ngay chu kỳ mới.
    """
    from scheduler import scheduler

    # Chu kỳ quét (phút) - Facebook Groups & Marketplace cấu hình 5 phút / lần
    intervals = {
        "GOOFISH": int(os.getenv("COLLECTOR_INTERVAL_GOOFISH", "10")),
        "CHOTOT": int(os.getenv("COLLECTOR_INTERVAL_CHOTOT", "30")),
        "FACEBOOK_MARKETPLACE": int(os.getenv("COLLECTOR_INTERVAL_FB_MARKETPLACE", "5")),
        "FACEBOOK_GROUPS": int(os.getenv("COLLECTOR_INTERVAL_FB_GROUPS", "5")),
    }

    # Từ khóa quét định kỳ (mặc định quét cả ram và pocket 3)
    default_queries = {
        "GOOFISH": "iPhone 16",
        "CHOTOT": "iphone 16",
        "FACEBOOK_MARKETPLACE": "rtx 4060",
        "FACEBOOK_GROUPS": os.getenv("COLLECTOR_QUERY_FB_GROUPS", "ram, pocket 3"),
    }

    for code, interval in intervals.items():
        job_id = f"collector_{code.lower()}"
        existing = scheduler.get_job(job_id)
        if existing:
            try:
                scheduler.remove_job(job_id)
                logger.info(f"Cập nhật lại job {job_id} sang chu kỳ mới ({interval} phút)")
            except Exception as ex:
                logger.warning(f"Không thể gỡ bỏ job cũ {job_id}: {ex}")

        target_func = run_facebook_groups_periodic_job if code == "FACEBOOK_GROUPS" else run_collector_job
        scheduler.add_job(
            target_func,
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
