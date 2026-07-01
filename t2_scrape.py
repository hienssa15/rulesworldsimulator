"""
T2: SCRAPE CONTENT - Multi-skill pattern từ Tinnhanh
Skills: FAST_HTTPX -> SPA_JSON -> PLAYWRIGHT_DOM
"""
import os
import json
import time
import logging
import httpx
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from config import settings
from skills import extract_spa_json_data

logger = logging.getLogger(__name__)


class T2Scrape:
    def __init__(self):
        self.session = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=15.0,
            follow_redirects=True
        )
        
        # Load blackbook
        self.blackbook = self._load_blackbook()
        
        # Playwright context (lazy init)
        self._playwright = None
        self._browser = None
        self._context = None

    def _load_blackbook(self) -> dict:
        """Load blackbook"""
        path = settings.BLACKBOOK_FILE
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_blackbook(self):
        """Save blackbook"""
        with open(settings.BLACKBOOK_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.blackbook, f, indent=2, ensure_ascii=False)

    def _init_playwright(self):
        """Lazy init Playwright"""
        if self._context is not None:
            return
            
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            self._context = self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            logger.info("✅ Playwright initialized")
        except Exception as e:
            logger.warning(f"⚠️  Playwright init failed: {e}")
            self._context = None

    def _close_playwright(self):
        """Close Playwright"""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._context = None
        self._browser = None
        self._playwright = None

    def is_valid_content(self, text: str) -> bool:
        """Check nội dung có hợp lệ không"""
        if not text or len(text) < 150:
            return False
        
        # Traps/anti-bot pages
        traps = [
            "enable javascript and cookies",
            "just a moment",
            "checking the site connection",
            "verify you are human",
            "access denied",
            "403 forbidden",
            "cloudflare",
            "captcha"
        ]
        
        text_lower = text.lower()
        return not any(t in text_lower for t in traps)

    def execute_fast_httpx(self, url: str) -> tuple[str | None, str]:
        """
        Skill 1: FAST_HTTPX
        Thử HTTPX + BeautifulSoup + SPA_JSON extraction
        """
        try:
            resp = self.session.get(url, timeout=12.0)
            html_text = resp.text
            
            # Sub-skill: SPA JSON extraction (Next.js, Nuxt.js)
            spa_text = extract_spa_json_data(html_text)
            if spa_text and self.is_valid_content(spa_text):
                return spa_text[:8000], "SPA_JSON"
            
            # Sub-skill: Classic HTML parsing
            soup = BeautifulSoup(html_text, 'lxml')
            
            # Remove noise
            for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "form"]):
                tag.decompose()
            
            # Try content selectors
            content_selectors = [
                "article",
                "main", 
                ".content",
                "#content",
                ".post-content",
                ".article-body",
                ".entry-content",
                ".article__body",
                "[itemprop='articleBody']",
                ".mw-parser-output",  # Wikipedia
            ]
            
            content = None
            for selector in content_selectors:
                element = soup.select_one(selector)
                if element:
                    # Get paragraphs
                    paragraphs = element.find_all(['p', 'li', 'h2', 'h3', 'h4', 'blockquote'])
                    if paragraphs:
                        content = "\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
                    else:
                        content = element.get_text(separator="\n", strip=True)
                    if content and len(content) > 200:
                        break
            
            # Fallback: body text
            if not content or len(content) < 200:
                if soup.body:
                    paragraphs = soup.body.find_all('p')
                    content = "\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30])
            
            if content and self.is_valid_content(content):
                return content[:8000], "HTTPX_SOUP"
            
            return None, None
            
        except Exception as e:
            logger.debug(f"FAST_HTTPX failed: {e}")
            return None, None

    def execute_playwright_dom(self, url: str) -> str | None:
        """
        Skill 2: PLAYWRIGHT_DOM
        Dùng cho SPA/Javascript-heavy sites
        """
        self._init_playwright()
        
        if self._context is None:
            return None
            
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
            
            # Wait for content to load
            page.wait_for_timeout(2000)
            
            # Get main content
            text = page.locator("body").inner_text()
            
            if self.is_valid_content(text):
                return text[:8000]
            
            return None
        except Exception as e:
            logger.debug(f"PLAYWRIGHT_DOM failed: {e}")
            return None
        finally:
            page.close()

    def scrape_reddit(self, url: str) -> dict | None:
        """Scrape Reddit bằng JSON API"""
        try:
            json_url = url.rstrip("/") + ".json"
            resp = self.session.get(json_url, timeout=15.0)
            resp.raise_for_status()
            
            data = resp.json()
            
            # Post content
            post = data[0]["data"]["children"][0]["data"]
            title = post["title"]
            content = post.get("selftext", "")
            
            # Top comments
            comments = []
            if len(data) > 1:
                for child in data[1]["data"]["children"][:10]:
                    if child["kind"] == "t1":
                        comment_body = child["data"].get("body", "")
                        if comment_body and len(comment_body) > 50:
                            comments.append(comment_body)
            
            full_content = f"{title}\n\n{content}\n\n--- COMMENTS ---\n" + "\n---\n".join(comments)
            
            return {
                "url": url,
                "title": title,
                "content": full_content,
                "content_length": len(full_content),
                "scraped_at": time.time(),
                "skill_used": "REDDIT_JSON"
            }
            
        except Exception as e:
            logger.debug(f"Reddit scrape failed: {e}")
            return None

    def scrape_pdf(self, url: str) -> dict | None:
        """Scrape PDF"""
        try:
            import pdfplumber
            import io
            
            resp = self.session.get(url, timeout=30.0)
            resp.raise_for_status()
            
            pdf_file = io.BytesIO(resp.content)
            
            content = ""
            with pdfplumber.open(pdf_file) as pdf:
                for i, page in enumerate(pdf.pages[:15]):  # Max 15 pages
                    text = page.extract_text()
                    if text:
                        content += text + "\n\n"
            
            if content and len(content) > 200:
                return {
                    "url": url,
                    "title": url.split("/")[-1].replace(".pdf", ""),
                    "content": content.strip(),
                    "content_length": len(content),
                    "scraped_at": time.time(),
                    "skill_used": "PDF_EXTRACT"
                }
            
            return None
            
        except ImportError:
            logger.warning("pdfplumber not installed, skipping PDF")
            return None
        except Exception as e:
            logger.debug(f"PDF scrape failed: {e}")
            return None

    def process_link(self, link: dict) -> dict | None:
        """
        Xử lý 1 link với skill chain
        Chain: FAST_HTTPX -> PLAYWRIGHT_DOM
        """
        url = link["url"]
        domain = link.get("domain", urlparse(url).netloc)
        scraper_type = link.get("scraper_type", "html_simple")
        
        # Init domain in blackbook
        if domain not in self.blackbook:
            self.blackbook[domain] = {
                "failures": 0,
                "status": "active",
                "skill": "FAST_HTTPX"
            }
        
        # Get current skill for domain
        current_skill = self.blackbook[domain].get("skill", "FAST_HTTPX")
        
        # Special cases
        if scraper_type == "reddit":
            result = self.scrape_reddit(url)
            if result:
                self.blackbook[domain]["failures"] = 0
                return result
            else:
                self.blackbook[domain]["failures"] = self.blackbook[domain].get("failures", 0) + 1
                return None
        
        if scraper_type == "pdf":
            result = self.scrape_pdf(url)
            if result:
                self.blackbook[domain]["failures"] = 0
                return result
            else:
                self.blackbook[domain]["failures"] = self.blackbook[domain].get("failures", 0) + 1
                return None
        
        # Skill chain
        skill_chain = ["FAST_HTTPX", "PLAYWRIGHT_DOM"]
        start_index = skill_chain.index(current_skill) if current_skill in skill_chain else 0
        
        data = None
        successful_skill = None
        
        for skill in skill_chain[start_index:]:
            if skill == "FAST_HTTPX":
                data, spec_skill = self.execute_fast_httpx(url)
                if data:
                    successful_skill = spec_skill
                    break
            elif skill == "PLAYWRIGHT_DOM":
                logger.info(f"         [PLAYWRIGHT] Rút búa tạ...")
                data = self.execute_playwright_dom(url)
                if data:
                    successful_skill = skill
                    break
        
        if data:
            # Update blackbook
            self.blackbook[domain]["skill"] = successful_skill if successful_skill != "SPA_JSON" else "FAST_HTTPX"
            self.blackbook[domain]["failures"] = 0
            
            # Get title
            title = link.get("title", "")
            if not title or len(title) < 10:
                # Extract title from content
                lines = data.split("\n")
                title = lines[0][:100] if lines else url
            
            return {
                "url": url,
                "title": title,
                "content": data,
                "content_length": len(data),
                "scraped_at": time.time(),
                "skill_used": successful_skill
            }
        else:
            # Update failure count
            self.blackbook[domain]["failures"] = self.blackbook[domain].get("failures", 0) + 1
            if self.blackbook[domain]["failures"] >= 3:
                self.blackbook[domain]["status"] = "banned"
                logger.warning(f"         🚫 Domain banned: {domain}")
            return None

    def validate_content(self, content_data: dict) -> bool:
        """Validate nội dung có đủ chất lượng không"""
        content = content_data.get("content", "")
        
        # Check độ dài tối thiểu
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
        logger.info("📥 T2: SCRAPE CONTENT (Multi-Skill)")
        logger.info("=" * 80)
        
        scraped = []
        failed = 0
        
        for i, link in enumerate(links, 1):
            logger.info(f"\n[{i}/{len(links)}] {link['url'][:60]}...")
            
            # Show current skill
            domain = link.get("domain", "")
            current_skill = self.blackbook.get(domain, {}).get("skill", "FAST_HTTPX")
            logger.info(f"      👉 Vũ khí: {current_skill}")
            
            content_data = self.process_link(link)
            
            if content_data:
                if self.validate_content(content_data):
                    content_data.update({
                        "keyword": link.get("keyword"),
                        "label": link.get("label"),
                        "priority": link.get("priority"),
                        "domain": domain
                    })
                    scraped.append(content_data)
                    logger.info(f"         ✅ OK: {content_data['content_length']} chars [{content_data['skill_used']}]")
                else:
                    logger.warning(f"         ⚠️  Nội dung không đủ chất lượng")
                    failed += 1
            else:
                logger.error(f"         ❌ Fail")
                failed += 1
            
            # Save blackbook periodically
            if i % 5 == 0:
                self._save_blackbook()
            
            time.sleep(settings.DELAY_BETWEEN_REQUESTS)
        
        # Final save blackbook
        self._save_blackbook()
        
        # Close Playwright
        self._close_playwright()
        
        logger.info(f"\n📊 TỔNG: {len(scraped)} thành công, {failed} thất bại")
        
        return scraped


def run_t2(links: list[dict]) -> list[dict]:
    """Entry point cho T2"""
    scraper = T2Scrape()
    return scraper.scrape_links(links)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [T2] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Test
    test_links = [
        {"url": "https://en.wikipedia.org/wiki/Astrobiology", "domain": "en.wikipedia.org", 
         "scraper_type": "html_simple", "keyword": "astrobiology", "label": "wiki_article", "priority": 1}
    ]
    
    results = run_t2(test_links)
    print(f"\n✅ Scraped {len(results)} links")
