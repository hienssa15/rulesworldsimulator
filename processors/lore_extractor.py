"""
LoreExtractor - Trích xuất quy luật sinh học từ bài viết
- Dùng gemini-2.5-flash cho tất cả nguồn (không dùng model heavy)
- Prompt tối ưu để JSON response ổn định hơn
- Parse JSON robust với nhiều fallback
"""
import json
import re
import logging

from .gemini_rotator import GeminiRotator

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a xenobiology data extractor. Read the article below and extract structured biology survival rules.

ARTICLE TITLE: {title}
SOURCE: {source}

ARTICLE TEXT:
{article_text}

Extract ALL available fields. Use null for missing info.
Output ONLY a single valid JSON object. No markdown, no code fences, no explanation.

{{
  "rule_type": "short_snake_case_label",
  "parameters": {{
    "body_composition": "string or null",
    "breathes": ["gas1", "gas2"] or null,
    "temperature_range": {{"min": number, "max": number, "unit": "celsius"}} or null,
    "pressure_range": {{"min": number, "max": number, "unit": "atm"}} or null,
    "gravity_tolerance": {{"min": number, "max": number, "unit": "g"}} or null,
    "solvent": "string or null",
    "energy_source": ["source1"] or null,
    "weaknesses": ["weakness1"] or null,
    "habitat": "string or null",
    "reproduction": "string or null",
    "diet": "string or null"
  }},
  "narrative_potential": {{
    "conflict_types": ["conflict1"],
    "story_hooks": ["hook1"],
    "humor_potential": ["funny1"]
  }},
  "confidence": 0.7
}}"""


class LoreExtractor:

    def __init__(self):
        self.rotator = GeminiRotator()

    def extract_from_article(self, article: dict) -> dict | None:
        article_text = self._prepare_text(article)

        if len(article_text) < 80:
            logger.debug(f"Quá ngắn, bỏ qua: {article.get('title')}")
            return None

        # Cắt ngắn để tránh vượt context window free tier
        if len(article_text) > 6000:
            article_text = article_text[:6000] + "\n[... truncated ...]"

        prompt = EXTRACTION_PROMPT.format(
            title=article.get("title", "unknown"),
            source=article.get("source", "unknown"),
            article_text=article_text,
        )

        try:
            raw_response = self.rotator.call(prompt, max_output_tokens=1500)
            result = self._parse_json_response(raw_response)

            if result is None:
                logger.warning(f"Parse JSON thất bại: {article.get('title')}")
                return None

            # Bổ sung metadata nguồn
            result["source"] = article.get("source", "unknown")
            result["source_title"] = article.get("title", "unknown")
            result["source_url"] = article.get("url", "")
            result["quality_score"] = float(result.get("confidence", 0.5))

            return result

        except Exception as e:
            logger.error(f"Extraction thất bại '{article.get('title')}': {e}")
            return None

    def _prepare_text(self, article: dict) -> str:
        """Chuẩn bị text từ nhiều loại article khác nhau."""
        # Project Rho table
        if article.get("type") == "table":
            content = article.get("content", {})
            rows = content.get("rows", [])[:25]
            headers = content.get("headers", [])
            text = "TABLE: " + " | ".join(headers) + "\n"
            for row in rows:
                if isinstance(row, dict):
                    text += " | ".join(str(v) for v in row.values()) + "\n"
                else:
                    text += str(row) + "\n"
            return text.strip()

        # Project Rho plain text
        if article.get("type") == "text":
            return str(article.get("content", "")).strip()

        # MediaWiki (Orion's Arm + Speculative Evo)
        wikitext = article.get("wikitext", "")

        # Strip wiki markup
        text = re.sub(r"\{\{[^}]*\}\}", " ", wikitext, flags=re.DOTALL)
        text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
        text = re.sub(r"={2,}.*?={2,}", " ", text)
        text = re.sub(r"''+", "", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)

        # Prepend infobox nếu có
        infobox = article.get("infobox", {})
        if infobox:
            info_str = " | ".join(f"{k}: {v}" for k, v in infobox.items())
            text = f"INFOBOX: {info_str}\n\n" + text

        return text.strip()

    def _parse_json_response(self, raw_text: str) -> dict | None:
        """Parse JSON từ response Gemini với nhiều fallback."""
        # Thử trực tiếp
        try:
            return json.loads(raw_text.strip())
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences
        cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Tìm JSON object đầu tiên bằng regex
        match = re.search(r"\{[\s\S]*\}", raw_text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Tìm JSON từ dòng đầu tiên có dấu {
        lines = raw_text.split("\n")
        for i, line in enumerate(lines):
            if "{" in line:
                fragment = "\n".join(lines[i:])
                match2 = re.search(r"\{[\s\S]*\}", fragment)
                if match2:
                    try:
                        return json.loads(match2.group())
                    except json.JSONDecodeError:
                        break

        logger.debug(f"Raw response không parse được:\n{raw_text[:300]}")
        return None
