import logging
from pymongo import MongoClient
from config import settings

logger = logging.getLogger(__name__)


class MongoUploader:

    def __init__(self):
        self.client = MongoClient(settings.MONGODB_URI)
        self.db = self.client[settings.MONGODB_DB_NAME]
        self.collection = self.db[settings.MONGODB_COLLECTION_RULES]

    def upload_rules(self, final_json):
        rules_by_category = final_json.get("rules", {})

        total_inserted = 0

        for category, rules in rules_by_category.items():
            if not rules:
                continue

            for rule in rules:
                rule["_category"] = category

                existing = self.collection.find_one({
                    "rule_id": rule.get("rule_id")
                })

                if existing:
                    self.collection.update_one(
                        {"rule_id": rule["rule_id"]},
                        {"$set": rule}
                    )
                    logger.debug(f"Updated rule: {rule['rule_id']}")
                else:
                    self.collection.insert_one(rule)
                    logger.debug(f"Inserted rule: {rule['rule_id']}")

                total_inserted += 1

        logger.info(
            f"MongoDB upload complete: {total_inserted} rules "
            f"in {len(rules_by_category)} categories"
        )

        return total_inserted

    def get_rule_count(self):
        return self.collection.count_documents({})

    def close(self):
        self.client.close()
