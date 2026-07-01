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
]


class ProjectRhoScraper:

    def __init__(self):
        self.base_url = settings.PROJECT_RHO_BASE
        self.delay = settings.REQUEST_DELAY_SECONDS

    def scrape_page(self, page_name):
        url = self.base_url + page_name

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            articles = []

            tables = soup.find_all("table")
            for i, table in enumerate(tables):
                table_data = self._parse_table(table)
                if table_data and self._is_biology_related(table_data):
                    articles.append({
                        "title": f"{page_name}_table_{i}",
                        "source": "project_rho",
                        "type": "table",
                        "content": table_data,
                        "url": f"{url}#table_{i}",
                    })

            paragraphs = soup.find_all("p")
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 100 and self._has_biology_keywords(text):
                    articles.append({
                        "title": f"{page_name}_text",
                        "source": "project_rho",
                        "type": "text",
                        "content": text,
                        "url": url,
                    })

            return articles

        except Exception as e:
            logger.error(f"ProjectRho - Error scraping {page_name}: {e}")
            return []

    def _parse_table(self, table):
        rows = table.find_all("tr")
        if not rows:
            return None

        headers = []
        first_row = rows[0].find_all(["th", "td"])
        headers = [cell.get_text(strip=True) for cell in first_row]

        data_rows = []
        for row in rows[1:]:
            cells = row.find_all("td")
            if cells:
                row_data = [cell.get_text(strip=True) for cell in cells]
                if len(row_data) == len(headers):
                    data_rows.append(dict(zip(headers, row_data)))

        return {"headers": headers, "rows": data_rows}

    def _is_biology_related(self, table_data):
        text = str(table_data).lower()
        return any(kw in text for kw in BIOLOGY_KEYWORDS)

    def _has_biology_keywords(self, text):
        text_lower = text.lower()
        return any(kw in text_lower for kw in BIOLOGY_KEYWORDS)

    def scrape_all(self):
        all_articles = []

        for page in settings.PROJECT_RHO_PAGES:
            articles = self.scrape_page(page)
            all_articles.extend(articles)
            time.sleep(self.delay)

        logger.info(f"Project Rho total: {len(all_articles)} items scraped")
        return all_articles
