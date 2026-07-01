"""
T2: SCRAPE - Anti-Ban Mode
- curl_cffi cho HTTP
- Delay 8-20s mỗi link
- Playwright chỉ dùng khi HTTP thất bại
"""
import os
import json
import time
import logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from config import settings
from stealth import get_stealth_headers, human_delay
from skills import extract_spa_json_data

logger = logging.getLogger(__name__)

try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
except ImportError:
    import httpx
    HAS_CFFI = False


class T2Scrape:
    def __init__(self):
        self.blackbook = self._load_blackbook()
        self._playwright = None
        self._browser = None
        self._context = None

    def _load_blackbook(self) -> dict:
        path = settings.BLACKBOOK_FILE
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_blackbook(self):
        with open(settings.BLACKBOOK_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.blackbook, f, indent=2, ensure_ascii=False)

    def _create_session(self):
        """Tạo session mới với headers ngụy trang"""
        headers = get_stealth_headers()
        if HAS_CFFI:
            return cffi_requests.Session(impersonate="chrome120", headers=headers)
        else:
            return httpx.Client(headers=headers, timeout=15.0, follow_redirects=True)

    def _init_playwright(self):
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
                user_agent=get_stealth_headers()["User-Agent"]
            )
        except Exception as e:
            logger.warning(f"Playwright init failed: {e}")
            self._context = None

    def _close_playwright(self):
        if self._context: self._context.close()
        if self._browser: self._browser.close()
        if self._playwright: self._playwright.stop()
        self._context = None

    def is_valid_content(self, text: str) -> bool:
        if not text or len(text) < 150:
            return False
        traps = [
            "enable javascript and cookies", "just a moment",
            "checking the site connection", "verify you are human",
            "access denied", "403 forbidden", "cloudflare", "captcha"
        ]
        return not any(t in text.lower() for t in traps)

    def _scrape_http(self, url: str) -> tuple[str | None, str]:
        """Skill 1: HTTP với curl_cffi/httpx"""
        session = self._create_session()
        try:
            resp = session.get(url, timeout=15.0)
            html_text = resp.text
            
            # Sub-skill: SPA JSON
            spa_text = extract_spa_json_data(html_text)
            if spa_text and self.is_valid_content(spa_text):
                return spa_text[:8000], "SPA_JSON"
            
            # Sub-skill: HTML parsing
            soup = BeautifulSoup(html_text, 'lxml')
            for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            
            selectors = [
                "article", "main", ".content", "#content",
                ".post-content", ".article-body", ".entry-content",
                ".mw-parser-output", "[itemprop='articleBody']"
            ]
            
            content = None
            for sel in selectors:
                el = soup.select_one(sel)
                if el:
                    ps = el.find_all(['p', 'li', 'h2', 'h3', 'blockquote'])
                    if ps:
                        content = "\n".join([p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 20])
                    if content and len(content) > 200:
                        break
            
            if not content or len(content) < 200:
                if soup.body:
                    ps = soup.body.find_all('p')
                    content = "\n".join([p.get_text(strip=True) for p in ps if len(p.get_text(strip=True)) > 30])
            
            if content and self.is_valid_content(content):
                return content[:8000], "HTTP_SOUP"
            
            return None, None
        except Exception as e:
            logger.debug(f"HTTP failed: {e}")
            return None, None
        finally:
            session.close()

    def _scrape_playwright(self, url: str) -> str | None:
        """Skill 2: Playwright (chỉ khi HTTP fail)"""
        self._init_playwright()
        if not self._context:
            return None
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)
            text = page.locator("body").inner_text()
            if self.is_valid_content(text):
                return text[:8000]
            return None
        except Exception as e:
            logger.debug(f"Playwright failed: {e}")
            return None
        finally:
            page.close()

    def _scrape_reddit(self, url: str) -> dict | None:
        session = self._create_session()
        try:
            json_url = url.rstrip("/") + ".json"
            resp = session.get(json_url, timeout=15.0)
            data = resp.json()
            post = data[0]["data"]["children"][0]["data"]
            title = post["title"]
            content = post.get("selftext", "")
            comments = []
            if len(data) > 1:
                for child in data[1]["data"]["children"][:10]:
                    if child["kind"] == "t1":
                        body = child["data"].get("body", "")
                        if body and len(body) > 50:
                            comments.append(body)
            full = f"{title}\n\n{content}\n\n--- COMMENTS ---\n" + "\n---\n".join(comments)
            return {"url": url, "title": title, "content": full, "content_length": len(full), "scraped_at": time.time(), "skill_used": "REDDIT_JSON"}
        except:
            return None
        finally:
            session.close()

    def process_link(self, link: dict) -> dict | None:
        """Xử lý 1 link - CHẬM"""
        url = link["url"]
        domain = link.get("domain", urlparse(url).netloc)
        scraper_type = link.get("scraper_type", "html_simple")
        
        if domain not in self.blackbook:
            self.blackbook[domain] = {"failures": 0, "status": "active", "skill": "HTTP"}
        
        # Reddit special
        if scraper_type == "reddit":
            result = self._scrape_reddit(url)
            if result:
                self.blackbook[domain]["failures"] = 0
                return result
            self.blackbook[domain]["failures"] += 1
            return None
        
        # Normal flow
        current_skill = self.blackbook[domain].get("skill", "HTTP")
        skill_chain = ["HTTP", "PLAYWRIGHT"]
        start_idx = skill_chain.index(current_skill) if current_skill in skill_chain else 0
        
        data, skill_used = None, None
        
        for skill in skill_chain[start_idx:]:
            if skill == "HTTP":
                data, spec = self._scrape_http(url)
                if data:
                    skill_used = spec
                    break
            elif skill == "PLAYWRIGHT":
                logger.info(f"         [PLAYWRIGHT] Rút búa tạ...")
                data = self._scrape_playwright(url)
                if data:
                    skill_used = "PLAYWRIGHT"
                    break
        
        if data:
            self.blackbook[domain]["skill"] = skill_used if skill_used != "SPA_JSON" else "HTTP"
            self.blackbook[domain]["failures"] = 0
            title = link.get("title", "")
            if not title or len(title) < 10:
                title = data.split("\n")[0][:100]
            return {
                "url": url, "title": title, "content": data,
                "content_length": len(data), "scraped_at": time.time(),
                "skill_used": skill_used
            }
        else:
            self.blackbook[domain]["failures"] = self.blackbook[domain].get("failures", 0) + 1
            if self.blackbook[domain]["failures"] >= 3:
                self.blackbook[domain]["status"] = "banned"
                logger.warning(f"         🚫 Banned domain: {domain}")
            return None

    def validate_content(self, content_data: dict) -> bool:
        content = content_data.get("content", "")
        if len(content) < settings.MIN_CONTENT_LENGTH:
            return False
        content_lower = content.lower()
        count = sum(1 for kw in settings.BIOLOGY_KEYWORDS if kw in content_lower)
        return count >= settings.MIN_BIOLOGY_KEYWORDS

    def scrape_links(self, links: list[dict]) -> list[dict]:
        """Cào từng link 1 - RẤT CHẬM"""
        logger.info("=" * 80)
        logger.info("📥 T2: SCRAPE (Anti-Ban Mode)")
        logger.info("=" * 80)
        
        scraped = []
        
        for i, link in enumerate(links, 1):
            logger.info(f"\n   [{i}/{len(links)}] {link['url'][:60]}...")
            
            content_data = self.process_link(link)
            
            if content_data:
                if self.validate_content(content_data):
                    content_data.update({
                        "keyword": link.get("keyword"),
                        "label": link.get("label"),
                        "priority": link.get("priority"),
                        "domain": link.get("domain")
                    })
                    scraped.append(content_data)
                    logger.info(f"         ✅ {content_data['content_length']} chars [{content_data['skill_used']}]")
                else:
                    logger.warning(f"         ⚠️ Không đủ chất lượng")
            else:
                logger.error(f"         ❌ Fail")
            
            # Lưu blackbook mỗi 3 links
            if i % 3 == 0:
                self._save_blackbook()
            
            # DELAY DÀI giữa các links (trừ link cuối cùng)
            if i < len(links):
                human_delay(
                    min_sec=settings.MIN_REQUEST_DELAY,
                    max_sec=settings.MAX_REQUEST_DELAY
                )
        
        self._save_blackbook()
        self._close_playwright()
        
        logger.info(f"\n📊 TỔNG: {len(scraped)} thành công")
        return scraped


def run_t2(links: list[dict]) -> list[dict]:
    scraper = T2Scrape()
    return scraper.scrape_links(links)
