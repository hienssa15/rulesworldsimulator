"""
T5: UPLOAD MONGODB - Upload rules vào MongoDB
"""
import logging
from datetime import datetime, timezone
from config import settings

logger = logging.getLogger(__name__)


class T5Upload:
    def __init__(self):
        # MongoDB connection (optional)
        self.mongo = None
        self.db = None
        
        if settings.MONGODB_URI:
            try:
                from pymongo import MongoClient
                self.mongo = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
                self.mongo.admin.command('ping')
                self.db = self.mongo[settings.MONGODB_DB_NAME]
                logger.info("✅ MongoDB connected")
            except Exception as e:
                logger.warning(f"⚠️  MongoDB connection failed: {e}")
                self.mongo = None
                self.db = None

    def upload_rules(self, contents: list[dict], run_id: str):
        """Upload rules vào MongoDB collection biology_rules"""
        logger.info("=" * 80)
        logger.info("📤 T5: UPLOAD MONGODB")
        logger.info("=" * 80)
        
        if self.db is None:
            logger.warning("⚠️  Không có MongoDB, skip upload")
            return
        
        try:
            uploaded = 0
            for content in contents:
                # Check if already exists
                exists = self.db[settings.MONGODB_COLLECTION_RULES].find_one({
                    "content_hash": content.get("content_hash")
                })
                
                if exists:
                    logger.debug(f"   ⚠️  Already exists: {content['rule_id']}")
                    continue
                
                # Insert new rule
                self.db[settings.MONGODB_COLLECTION_RULES].insert_one({
                    **content,
                    "status": "raw",  # Chưa qua LLM extract
                    "run_id": run_id,
                    "uploaded_at": datetime.now(timezone.utc).isoformat()
                })
                uploaded += 1
            
            logger.info(f"✅ Uploaded {uploaded} new rules")
            
        except Exception as e:
            logger.warning(f"⚠️  Upload failed: {e}")

    def save_run_log(self, run_id: str, stats: dict):
        """Lưu log của run"""
        if self.db is None:
            return
        
        try:
            self.db[settings.MONGODB_COLLECTION_RUNS].insert_one({
                "run_id": run_id,
                "started_at": stats.get("started_at"),
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "keywords_used": stats.get("keywords_used", []),
                "links_found": stats.get("links_found", 0),
                "links_scraped": stats.get("links_scraped", 0),
                "contents_validated": stats.get("contents_validated", 0),
                "duplicates_removed": stats.get("duplicates_removed", 0),
                "rules_uploaded": stats.get("rules_uploaded", 0),
                "duration_seconds": stats.get("duration_seconds", 0),
                "status": "success"
            })
            
            logger.info(f"✅ Saved run log: {run_id}")
            
        except Exception as e:
            logger.warning(f"⚠️  Save run log failed: {e}")


def run_t5(contents: list[dict], run_id: str, stats: dict):
    """Entry point cho T5"""
    uploader = T5Upload()
    uploader.upload_rules(contents, run_id)
    uploader.save_run_log(run_id, stats)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [T5] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Test
    run_t5([], "test_run", {"started_at": "2024-01-01T00:00:00Z"})
    print("\n✅ T5 completed")
