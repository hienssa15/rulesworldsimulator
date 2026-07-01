"""
ProjectRhoScraper - HTML scraping
Cào bảng dữ liệu và đoạn văn từ Project Rho
"""
import hashlib
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

    # ------------------------------------------------------------------
    # PHẦN 2: Incremental — Project Rho không có API nên dùng content-hash
    # để phát hiện trang nào đã thay đổi kể từ lần cào trước.
    # ------------------------------------------------------------------

    def _page_hash(self, page_name: str) -> str | None:
        url = self.base_url + page_name
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return hashlib.md5(resp.text.encode("utf-8")).hexdigest()
        except Exception as e:
            logger.error(f"ProjectRho - Lỗi hash '{page_name}': {e}")
            return None

    def scrape_recent(self, previous_hashes: dict) -> tuple[list[dict], dict]:
        """
        So sánh hash nội dung trang với lần cào trước (previous_hashes).
        Trang nào hash thay đổi (hoặc chưa từng cào) thì cào lại toàn bộ trang đó.
        Trả về (articles_mới, new_hashes) để lưu lại cho lần sau.
        """
        all_articles = []
        new_hashes = dict(previous_hashes)

        for page in settings.PROJECT_RHO_PAGES:
            current_hash = self._page_hash(page)
            if current_hash is None:
                continue

            if previous_hashes.get(page) == current_hash:
                logger.info(f"ProjectRho - '{page}': không đổi, bỏ qua")
                time.sleep(self.delay)
                continue

            logger.info(f"ProjectRho - '{page}': nội dung thay đổi, cào lại")
            articles = self.scrape_page(page)
            all_articles.extend(articles)
            new_hashes[page] = current_hash
            time.sleep(self.delay)

        logger.info(f"ProjectRho (recent) tổng cộng: {len(all_articles)} mục thay đổi")
        return all_articles, new_hashes
