"""
OrionsArmScraper - MediaWiki API
Cào bài viết xenobiology từ Orion's Arm encyclopedia
"""
import requests
import time
import logging

from config import settings

logger = logging.getLogger(__name__)


class OrionsArmScraper:

    def __init__(self):
        self.api_url = settings.ORIONS_ARM_API
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
                logger.error(f"OrionsArm - Lỗi category '{category_name}': {e}")
                break

        logger.info(f"OrionsArm - '{category_name}': {len(all_titles)} bài")
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
                logger.debug(f"OrionsArm - Bỏ qua '{title}': {data['error']}")
                return None

            parse_data = data.get("parse", {})
            wikitext = parse_data.get("wikitext", {}).get("*", "")

            if len(wikitext) < 100:
                return None

            return {
                "title": title,
                "source": "orions_arm",
                "wikitext": wikitext,
                "categories": [cat["*"] for cat in parse_data.get("categories", [])],
                "url": f"https://orionsarm.com/wiki/{title.replace(' ', '_')}",
            }

        except Exception as e:
            logger.error(f"OrionsArm - Lỗi trang '{title}': {e}")
            return None

    def scrape_all(self) -> list[dict]:
        articles = []
        seen_titles: set[str] = set()

        for category in settings.ORIONS_ARM_CATEGORIES:
            titles = self.get_category_members(category)

            for title in titles:
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                if len(articles) >= settings.MAX_ARTICLES_TOTAL:
                    logger.info("Đạt giới hạn MAX_ARTICLES_TOTAL, dừng scrape")
                    return articles

                article = self.get_page_content(title)
                if article:
                    articles.append(article)

                time.sleep(self.delay)

        logger.info(f"OrionsArm tổng cộng: {len(articles)} bài")
        return articles
