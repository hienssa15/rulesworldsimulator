import json
import re
import logging
from .gemini_rotator import GeminiRotator

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a xenobiology data extractor. Read the following article about fictional/speculative biology and extract structured survival rules.

ARTICLE:
{article_text}

Extract the following fields. If information is not found, use null.
Output ONLY valid JSON, no markdown, no explanation:

{{
  "rule_type": "short label like silicon_based_life or ammonia_breather",
  "parameters": {{
    "body_composition": "what the organism is made of",
    "breathes": ["list of gases"],
    "temperature_range": {{"min": number, "max": number, "unit": "celsius"}},
    "pressure_range": {{"min": number, "max": number, "unit": "atm"}},
    "gravity_tolerance": {{"min": number, "max": number, "unit": "g"}},
    "solvent": "bodily fluid/solvent",
    "energy_source": ["list of energy sources"],
    "weaknesses": ["list of things that harm this organism"],
    "habitat": "typical environment description",
    "reproduction": "how they reproduce",
    "diet": "what they consume"
  }},
  "narrative_potential": {{
    "conflict_types": ["potential conflicts from this biology"],
    "story_hooks": ["story situations this enables"],
    "humor_potential": ["funny situations from this biology"]
  }},
  "confidence": 0.0 to 1.0 how confident you are in extraction quality
}}
"""


class LoreExtractor:

    def __init__(self):
        self.rotator = GeminiRotator()

    def extract_from_article(self, article):
        article_text = self._prepare_text(article)

        if len(article_text) < 50:
            logger.debug(f"Article too short, skipping: {article.get('title')}")
            return None

        if len(article_text) > 8000:
            article_text = article_text[:8000]

        prompt = EXTRACTION_PROMPT.format(article_text=article_text)

        try:
            is_heavy = article.get("source") == "project_rho"
            raw_response = self.rotator.call(prompt, use_heavy=is_heavy)

            result = self._parse_json_response(raw_response)

            if result:
                result["source"] = article.get("source", "unknown")
                result["source_title"] = article.get("title", "unknown")
                result["source_url"] = article.get("url", "")
                result["quality_score"] = result.get("confidence", 0.5)

            return result

        except Exception as e:
            logger.error(
                f"Extraction failed for '{article.get('title')}': {e}"
            )
            return None

    def _prepare_text(self, article):
        if article.get("type") == "table":
            content = article.get("content", {})
            text = "TABLE DATA:\n"
            for row in content.get("rows", [])[:20]:
                text += str(row) + "\n"
            return text

        wikitext = article.get("wikitext", "")
        text = re.sub(r"\{\{.*?\}\}", "", wikitext, flags=re.DOTALL)
        text = re.sub(r"\[\[.*?\|(.*?)\]\]", r"\1", text)
        text = re.sub(r"\[\[(.*?)\]\]", r"\1", text)
        text = re.sub(r"''+", "", text)
        text = re.sub(r"==+.*?==+", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)

        infobox = article.get("infobox", {})
        if infobox:
            text = f"INFOBOX: {infobox}\n\n" + text

        return text.strip()

    def _parse_json_response(self, raw_text):
        try:
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from Gemini response")
            return None
