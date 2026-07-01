"""
MongoUploader - Ghi dữ liệu vào MongoDB
Chiến lược: 1 document master duy nhất (upsert toàn bộ) + index tìm kiếm nhanh
- harvest_snapshot: 1 document chứa toàn bộ JSON master
- biology_rules: mỗi rule là 1 document riêng (upsert by rule_id)
- harvest_state: tracking tiến trình giữa các lần chạy
"""
import logging
from datetime import datetime, timezone
from pymongo import MongoClient, UpdateOne, ASCENDING
from pymongo.errors import BulkWriteError

from config import settings

logger = logging.getLogger(__name__)


class MongoUploader:

    def __init__(self):
        if not settings.MONGODB_URI:
            raise ValueError("MONGODB_URI chưa được cấu hình")

        self.client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=10000)
        self.db = self.client[settings.MONGODB_DB_NAME]

        self.rules_col = self.db[settings.MONGODB_COLLECTION_RULES]
        self.snapshot_col = self.db[settings.MONGODB_COLLECTION_SNAPSHOT]
        self.state_col = self.db[settings.MONGODB_COLLECTION_STATE]

        self._ensure_indexes()

    def _ensure_indexes(self):
        """Tạo index cho tìm kiếm nhanh."""
        try:
            self.rules_col.create_index([("rule_id", ASCENDING)], unique=True)
            self.rules_col.create_index([("categories", ASCENDING)])
            self.rules_col.create_index([("source", ASCENDING)])
            self.rules_col.create_index([("quality_score", ASCENDING)])
            self.state_col.create_index([("state_id", ASCENDING)], unique=True)
        except Exception as e:
            logger.warning(f"Tạo index lỗi (có thể đã tồn tại): {e}")

    # ------------------------------------------------------------------
    # Master snapshot - 1 document duy nhất
    # ------------------------------------------------------------------

    def upsert_snapshot(self, final_json: dict) -> bool:
        """
        Ghi toàn bộ JSON master vào 1 document duy nhất.
        Nếu đã tồn tại thì merge rules (không ghi đè hoàn toàn).
        """
        try:
            existing = self.snapshot_col.find_one({"_id": settings.SNAPSHOT_DOC_ID})

            if existing:
                # Merge: giữ rules cũ + thêm rules mới
                old_rules = {r["rule_id"]: r for r in existing.get("rules", [])}
                for r in final_json.get("rules", []):
                    old_rules[r["rule_id"]] = r  # overwrite nếu trùng

                merged_rules = list(old_rules.values())
                merged_rules.sort(key=lambda r: r.get("quality_score", 0), reverse=True)

                update_doc = {
                    "$set": {
                        "rules": merged_rules,
                        "metadata.total_rules": len(merged_rules),
                        "metadata.last_updated": datetime.now(timezone.utc).isoformat(),
                        "metadata.run_count": existing.get("metadata", {}).get("run_count", 0) + 1,
                    }
                }
                self.snapshot_col.update_one({"_id": settings.SNAPSHOT_DOC_ID}, update_doc)
                logger.info(f"Snapshot merged: {len(merged_rules)} rules tổng cộng")
            else:
                # Lần đầu tạo mới
                doc = dict(final_json)
                doc["_id"] = settings.SNAPSHOT_DOC_ID
                doc["metadata"]["run_count"] = 1
                doc["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()
                self.snapshot_col.insert_one(doc)
                logger.info(f"Snapshot tạo mới: {final_json['metadata']['total_rules']} rules")

            return True

        except Exception as e:
            logger.error(f"Upsert snapshot thất bại: {e}")
            return False

    # ------------------------------------------------------------------
    # Individual rules - mỗi rule 1 document (upsert bulk)
    # ------------------------------------------------------------------

    def upsert_rules(self, final_json: dict) -> int:
        """
        Upsert từng rule vào collection biology_rules.
        Dùng bulk write để nhanh hơn.
        """
        rules = final_json.get("rules", [])
        if not rules:
            return 0

        operations = []
        for rule in rules:
            rule_id = rule.get("rule_id")
            if not rule_id:
                continue
            operations.append(
                UpdateOne(
                    {"rule_id": rule_id},
                    {"$set": rule},
                    upsert=True,
                )
            )

        if not operations:
            return 0

        try:
            result = self.rules_col.bulk_write(operations, ordered=False)
            total = result.upserted_count + result.modified_count
            logger.info(
                f"Bulk upsert: {result.upserted_count} mới, "
                f"{result.modified_count} cập nhật"
            )
            return total
        except BulkWriteError as bwe:
            logger.warning(f"BulkWrite partial error: {bwe.details}")
            return bwe.details.get("nUpserted", 0) + bwe.details.get("nModified", 0)

    # ------------------------------------------------------------------
    # State tracking - tiến trình giữa các lần chạy
    # ------------------------------------------------------------------

    def save_state(self, state: dict):
        """Lưu trạng thái pipeline để tiếp tục lần sau."""
        state["_updated"] = datetime.now(timezone.utc).isoformat()
        self.state_col.update_one(
            {"state_id": "harvest_progress"},
            {"$set": state},
            upsert=True,
        )
        logger.debug("State đã lưu")

    def load_state(self) -> dict:
        """Đọc trạng thái lần chạy trước."""
        doc = self.state_col.find_one({"state_id": "harvest_progress"})
        if doc:
            doc.pop("_id", None)
            return doc
        return {}

    def mark_batch_done(self, batch_id: int):
        """Đánh dấu batch đã xử lý xong."""
        self.state_col.update_one(
            {"state_id": "harvest_progress"},
            {"$addToSet": {"completed_batches": batch_id}},
            upsert=True,
        )

    def get_completed_batches(self) -> set[int]:
        doc = self.state_col.find_one({"state_id": "harvest_progress"})
        if doc:
            return set(doc.get("completed_batches", []))
        return set()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_rule_count(self) -> int:
        return self.rules_col.count_documents({})

    def get_snapshot_rule_count(self) -> int:
        doc = self.snapshot_col.find_one({"_id": settings.SNAPSHOT_DOC_ID})
        if doc:
            return len(doc.get("rules", []))
        return 0

    def close(self):
        self.client.close()
