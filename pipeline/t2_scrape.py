"""
T2: SCRAPE CONTENT - Cào nội dung từ links
"""
import requests
import time
import logging
from bs4 import BeautifulSoup
from config import settings

logger = logging.getLogger(__name__)


class T2Scrape:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    def scrape_html_simple(self, url: str) -> dict | None:
        """Cào HTML thuần (Wikipedia, academic sites, blogs)"""
        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "lxml")
            
            # Xóa script, style, nav, footer
            for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            
            # Tìm nội dung chính
            content = None
            
            # Thử các selector phổ biến
            for selector in ["article", "main", ".content", "#content", 
                           ".post-content", ".article-body", ".entry-content"]:
                element = soup.select_one(selector)
                if element:
                    content = element.get_text(separator="\n", strip=True)
                    break
            
            # Fallback: lấy body
            if not content or len(content) < 200:
                content = soup.body.get_text(separator="\n", strip=True) if soup.body else ""
            
            # Lấy title
            title = soup.title.get_text(strip=True) if soup.title else url
            
            return {
                "url": url,
                "title": title,
                "content": content,
                "content_length": len(content),
                "scraped_at": time.time()
            }
            
        except Exception as e:
            logger.error(f"Lỗi cào '{url}': {e}")
            return None

    def scrape_reddit(self, url: str) -> dict | None:
        """Cào Reddit (cần xử lý đặc biệt)"""
        try:
            # Thêm .json vào URL để lấy JSON
            json_url = url.rstrip("/") + ".json"
            resp = self.session.get(json_url, timeout=20)
            resp.raise_for_status()
            
            data = resp.json()
            
            # Extract content
            post = data[0]["data"]["children"][0]["data"]
            title = post["title"]
            content = post.get("selftext", "")
            
            # Lấy comments
            comments = []
            if len(data) > 1:
                for child in data[1]["data"]["children"][:5]:  # Top 5 comments
                    if child["kind"] == "t1":
                        comments.append(child["data"]["body"])
            
            full_content = f"{title}\n\n{content}\n\n--- Comments ---\n" + "\n".join(comments)
            
            return {
                "url": url,
                "title": title,
                "content": full_content,
                "content_length": len(full_content),
                "scraped_at": time.time()
            }
            
        except Exception as e:
            logger.error(f"Lỗi cào Reddit '{url}': {e}")
            return None

    def scrape_pdf(self, url: str) -> dict | None:
        """Cào PDF (cần thư viện PyPDF2)"""
        try:
            import PyPDF2
            import io
            
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            
            pdf_file = io.BytesIO(resp.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            content = ""
            for page in pdf_reader.pages[:10]:  # Chỉ đọc 10 trang đầu
                content += page.extract_text() + "\n"
            
            return {
                "url": url,
                "title": url.split("/")[-1],
                "content": content,
                "content_length": len(content),
                "scraped_at": time.time()
            }
            
        except Exception as e:
            logger.error(f"Lỗi cào PDF '{url}': {e}")
            return None

    def scrape_link(self, link: dict) -> dict | None:
        """Cào nội dung từ 1 link"""
        scraper_type = link.get("scraper_type", "html_simple")
        url = link["url"]
        
        if scraper_type == "pdf":
            return self.scrape_pdf(url)
        elif scraper_type == "reddit":
            return self.scrape_reddit(url)
        else:
            return self.scrape_html_simple(url)

    def validate_content(self, content_data: dict) -> bool:
        """Validate nội dung có đủ chất lượng không"""
        content = content_data.get("content", "")
        
        # Check độ dài
        if len(content) < settings.MIN_CONTENT_LENGTH:
            return False
        
        # Check từ khóa sinh học
        content_lower = content.lower()
        keyword_count = sum(1 for kw in settings.BIOLOGY_KEYWORDS if kw in content_lower)
        
        if keyword_count < settings.MIN_BIOLOGY_KEYWORDS:
            return False
        
        return True

    def scrape_links(self, links: list[dict]) -> list[dict]:
        """Cào nội dung từ tất cả links"""
        logger.info("=" * 80)
        logger.info("📥 T2: SCRAPE CONTENT")
        logger.info("=" * 80)
        
        scraped = []
        failed = 0
        
        for i, link in enumerate(links, 1):
            logger.info(f"\n[{i}/{len(links)}] {link['url'][:70]}")
            
            content_data = self.scrape_link(link)
            
            if content_data:
                # Validate
                if self.validate_content(content_data):
                    content_data.update({
                        "keyword": link.get("keyword"),
                        "label": link.get("label"),
                        "priority": link.get("priority")
                    })
                    scraped.append(content_data)
                    logger.info(f"   ✅ OK: {content_data['content_length']} chars")
                else:
                    logger.warning(f"   ⚠️  Nội dung không đủ chất lượng")
                    failed += 1
            else:
                logger.error(f"   ❌ Fail")
                failed += 1
            
            time.sleep(settings.DELAY_BETWEEN_REQUESTS)
        
        logger.info(f"\n📊 TỔNG: {len(scraped)} thành công, {failed} thất bại")
        
        return scraped
