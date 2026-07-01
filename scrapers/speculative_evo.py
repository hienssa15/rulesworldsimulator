"""
SpeculativeEvoScraper - Fandom MediaWiki API
Cào bài viết sinh vật giả tưởng từ Speculative Evolution wiki
"""
import requests
import time
import re
import logging

from config import settings

logger = logging.getLogger(__name__)


class SpeculativeEvoScraper:

    def __init__(self):
        self.api_url = settings.SPEC_EVO_API
        self.delay = settings.REQUEST_DELAY_SECONDS
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "WorldLoreHarvester/2.0 (research bot; contact via github)"
        })

    def get_category_members(self, category_name: str, limit: int | None = None) -> list[str]:
        if limit is None:
            limit = settings.MAX_ARTICLES_PER_CATEGORY

        all_titles = []
        continue_token = None

        while len(all_titles) < limit:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": f"Category:{category_name}",
                "cmlimit": min(500, limit - len(all_titles)),
                "format": "json",
                "cmprop": "title",
            }

            if continue_token:
                params["cmcontinue"] = continue_token

            try:
                resp = self.session.get(self.api_url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                members = data.get("query", {}).get("categorymembers", [])
                titles = [m["title"] for m in members if not m["title"].startswith("Category:")]
                all_titles.extend(titles)

                continue_token = data.get("continue", {}).get("cmcontinue")
                if not continue_token:
                    break

                time.sleep(self.delay)

            except Exception as e:
                logger.error(f"SpecEvo - Lỗi category '{category_name}': {e}")
                break

        return all_titles

    def get_page_content(self, title: str) -> dict | None:
        params = {
            "action": "parse",
            "page": title,
            "prop": "wikitext|categories",
            "format": "json",
        }

        try:
            resp = self.session.get(self.api_url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                return None

            parse_data = data.get("parse", {})
            wikitext = parse_data.get("wikitext", {}).get("*", "")

            if len(wikitext) < 100:
                return None

            infobox = self._parse_infobox(wikitext)

            return {
                "title": title,
                "source": "speculative_evo",
                "wikitext": wikitext,
                "infobox": infobox,
                "categories": [cat["*"] for cat in parse_data.get("categories", [])],
                "url": f"https://speculativeevolution.fandom.com/wiki/{title.replace(' ', '_')}",
            }

        except Exception as e:
            logger.error(f"SpecEvo - Lỗi trang '{title}': {e}")
            return None

    def _parse_infobox(self, wikitext: str) -> dict:
        infobox = {}
        # Lấy nội dung trong template đầu tiên (thường là infobox)
        template_match = re.search(r"\{\{([^}]+)\}\}", wikitext, re.DOTALL)
        if template_match:
            content = template_match.group(1)
            for line in content.split("\n"):
                if "=" in line and line.strip().startswith("|"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key = parts[0].strip().lstrip("|").strip()
                        val = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", parts[1]).strip()
                        val = re.sub(r"\{\{.*?\}\}", "", val).strip()
                        if key and val:
                            infobox[key] = val
        return infobox

    def scrape_all(self) -> list[dict]:
        articles = []
        seen_titles: set[str] = set()

        for category in settings.SPEC_EVO_CATEGORIES:
            titles = self.get_category_members(category)

            for title in titles:
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                if len(articles) >= settings.MAX_ARTICLES_TOTAL:
                    return articles

                article = self.get_page_content(title)
                if article:
                    articles.append(article)

                time.sleep(self.delay)

        logger.info(f"SpeculativeEvo tổng cộng: {len(articles)} bài")
        return articles

    # ------------------------------------------------------------------
    # PHẦN 2: Incremental — chỉ lấy bài mới/sửa đổi sau since_iso
    # ------------------------------------------------------------------

    def get_touched_timestamps(self, titles: list[str]) -> dict:
        """Trả về {title: touched_iso} bằng prop=info, gộp 50 title/call."""
        result = {}
        for i in range(0, len(titles), 50):
            chunk = titles[i:i + 50]
            params = {
                "action": "query",
                "prop": "info",
                "titles": "|".join(chunk),
                "format": "json",
            }
            try:
                resp = self.session.get(self.api_url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    title = page.get("title")
                    touched = page.get("touched")
                    if title and touched:
                        result[title] = touched
            except Exception as e:
                logger.error(f"SpecEvo - Lỗi lấy touched timestamp: {e}")
            time.sleep(self.delay)
        return result

    def scrape_recent(self, since_iso: str) -> list[dict]:
        """
        Chỉ cào bài viết được sửa đổi sau thời điểm since_iso (ISO 8601, UTC).
        Dùng cho Phần 2 - monthly refresh.
        """
        articles = []
        seen_titles: set[str] = set()

        for category in settings.SPEC_EVO_CATEGORIES:
            titles = self.get_category_members(category)
            new_titles = [t for t in titles if t not in seen_titles]
            seen_titles.update(new_titles)

            if not new_titles:
                continue

            touched_map = self.get_touched_timestamps(new_titles)
            changed_titles = [
                t for t in new_titles
                if touched_map.get(t, "") > since_iso
            ]
            logger.info(
                f"SpecEvo - '{category}': {len(changed_titles)}/{len(new_titles)} "
                f"bài thay đổi sau {since_iso}"
            )

            for title in changed_titles:
                article = self.get_page_content(title)
                if article:
                    articles.append(article)
                time.sleep(self.delay)

        logger.info(f"SpeculativeEvo (recent) tổng cộng: {len(articles)} bài mới/sửa")
        return articles
