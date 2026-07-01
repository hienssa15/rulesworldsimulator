"""
ProjectRhoScraper - HTML scraping
Cào bảng dữ liệu và đoạn văn từ Project Rho
"""
import requests
import time
import logging

from bs4 import BeautifulSoup
from config import settings

logger = logging.getLogger(__name__)

BIOLOGY_KEYWORDS = [
    "silicon", "carbon", "ammonia", "methane",
    "biology", "organism", "metabolism", "respiration",
    "temperature", "gravity", "atmosphere", "biochemistry",
    "xenobiology", "exotic", "alien life", "solvent",
    "protein", "dna", "rna", "cell", "membrane",
    "oxygen", "nitrogen", "hydrogen", "sulfur",
]


class ProjectRhoScraper:

    def __init__(self):
        self.base_url = settings.PROJECT_RHO_BASE
        self.delay = settings.REQUEST_DELAY_SECONDS
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "WorldLoreHarvester/2.0 (research bot; contact via github)"
        })

    def scrape_page(self, page_name: str) -> list[dict]:
        url = self.base_url + page_name

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            logger.error(f"ProjectRho - Lỗi tải '{page_name}': {e}")
            return []

        articles = []

        # --- Bảng dữ liệu ---
        for i, table in enumerate(soup.find_all("table")):
            table_data = self._parse_table(table)
            if table_data and self._is_biology_related(str(table_data)):
                articles.append({
                    "title": f"{page_name}_table_{i}",
                    "source": "project_rho",
                    "type": "table",
                    "content": table_data,
                    "url": f"{url}#table_{i}",
                })

        # --- Đoạn văn bản ---
        seen_texts: set[str] = set()
        for p in soup.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if len(text) > 120 and self._has_biology_keywords(text):
                key = text[:80]
                if key not in seen_texts:
                    seen_texts.add(key)
                    articles.append({
                        "title": f"{page_name}_text",
                        "source": "project_rho",
                        "type": "text",
                        "content": text,
                        "url": url,
                    })

        logger.info(f"ProjectRho - '{page_name}': {len(articles)} mục")
        return articles

    def _parse_table(self, table) -> dict | None:
        rows = table.find_all("tr")
        if len(rows) < 2:
            return None

        headers = [cell.get_text(strip=True) for cell in rows[0].find_all(["th", "td"])]
        if not headers:
            return None

        data_rows = []
        for row in rows[1:]:
            cells = row.find_all("td")
            row_data = [cell.get_text(strip=True) for cell in cells]
            if row_data:
                if len(row_data) == len(headers):
                    data_rows.append(dict(zip(headers, row_data)))
                else:
                    # Pad hoặc cắt ngắn để khớp headers
                    padded = row_data[:len(headers)] + [""] * max(0, len(headers) - len(row_data))
                    data_rows.append(dict(zip(headers, padded)))

        if not data_rows:
            return None

        return {"headers": headers, "rows": data_rows}

    def _is_biology_related(self, text: str) -> bool:
        tl = text.lower()
        return any(kw in tl for kw in BIOLOGY_KEYWORDS)

    def _has_biology_keywords(self, text: str) -> bool:
        return self._is_biology_related(text)

    def scrape_all(self) -> list[dict]:
        all_articles = []

        for page in settings.PROJECT_RHO_PAGES:
            articles = self.scrape_page(page)
            all_articles.extend(articles)
            time.sleep(self.delay)

        logger.info(f"ProjectRho tổng cộng: {len(all_articles)} mục")
        return all_articles
