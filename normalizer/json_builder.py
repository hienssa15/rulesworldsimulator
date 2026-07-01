"""
JsonBuilder - Chuẩn hóa và đóng gói rules thành 1 JSON master
- Không lưu trùng rule vào nhiều category
- Dedup thông minh hơn (so sánh rule_type + body_composition)
- Metadata đầy đủ cho từng lần harvest
"""
import hashlib
import logging
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)


class JsonBuilder:

    def __init__(self):
        self.min_quality = settings.MIN_QUALITY_SCORE
        self.max_rules = settings.MAX_FINAL_RULES

    def build(self, extracted_rules: list[dict], run_id: str = "") -> dict:
        """
        Xây dựng JSON master từ danh sách rules đã extract.
        Mỗi rule chỉ xuất hiện 1 lần, tag category là trường riêng.
        """
        # Lọc quality
        valid_rules = [
            r for r in extracted_rules
            if r and isinstance(r, dict) and r.get("quality_score", 0) >= self.min_quality
        ]
        logger.info(
            f"Quality filter: {len(extracted_rules)} → {len(valid_rules)} "
            f"(threshold={self.min_quality})"
        )

        # Dedup
        unique_rules = self._deduplicate(valid_rules)
        logger.info(f"Dedup: {len(valid_rules)} → {len(unique_rules)}")

        # Gán tags category (không tạo list riêng biệt)
        tagged_rules = [self._assign_tags(r) for r in unique_rules]

        # Thống kê
        sources = {}
        for r in tagged_rules:
            src = r.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1

        final = {
            "metadata": {
                "run_id": run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
                "harvested_at": datetime.now(timezone.utc).isoformat(),
                "total_rules": len(tagged_rules),
                "min_quality_score": self.min_quality,
                "sources": sources,
                "version": "2.0",
            },
            "rules": tagged_rules,
        }

        return final

    def _deduplicate(self, rules: list[dict]) -> list[dict]:
        seen: set[str] = set()
        unique = []

        for rule in rules:
            rule_type = (rule.get("rule_type") or "unknown").strip().lower()
            params = rule.get("parameters") or {}
            body = str(params.get("body_composition") or "").lower()
            breathes = str(sorted(params.get("breathes") or [])).lower()
            solvent = str(params.get("solvent") or "").lower()

            # Hash đủ mô tả để phân biệt
            hash_input = f"{rule_type}|{body}|{breathes}|{solvent}"
            rule_hash = hashlib.md5(hash_input.encode()).hexdigest()

            if rule_hash not in seen:
                seen.add(rule_hash)
                rule["rule_id"] = f"rule_{rule_hash[:10]}"
                unique.append(rule)

        # Sắp xếp theo quality giảm dần, lấy tối đa max_rules
        unique.sort(key=lambda r: r.get("quality_score", 0), reverse=True)
        return unique[:self.max_rules]

    def _assign_tags(self, rule: dict) -> dict:
        """Gán danh sách category tags vào trường 'categories' của rule."""
        params = rule.get("parameters") or {}
        tags = []

        if params.get("body_composition"):
            tags.append("body_composition")
        if params.get("breathes"):
            tags.append("respiration")
        if params.get("habitat") or params.get("temperature_range"):
            tags.append("habitat")
        if params.get("energy_source"):
            tags.append("energy")
        if params.get("weaknesses"):
            tags.append("weakness")
        if params.get("solvent"):
            tags.append("solvent")
        if params.get("reproduction"):
            tags.append("reproduction")

        rule["categories"] = tags
        return rule
