"""
T0: SEARCH - Anti-Ban Mode
- Dùng curl_cffi giả lập TLS Chrome
- Chỉ xử lý 1 keyword mỗi lần gọi
- Delay 8-15s giữa các engines
"""
import os
import json
import logging
import random
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup

from config import settings
from stealth import get_stealth_headers, human_delay

logger = logging.getLogger(__name__)

# Import curl_cffi (thư viện chống ban tốt nhất cho pure Python)
try:
    from curl_cffi import requests as cffi_requests
    HAS_CFFI = True
    logger.info("✅ curl_cffi loaded (TLS fingerprint spoofing enabled)")
except ImportError:
    import httpx
    HAS_CFFI = False
    logger.warning("⚠️  curl_cffi not found, fallback to httpx (easier to get banned)")


class T0Search:
    def __init__(self):
        self.engines_config = self._load_engines_config()
        self.blackbook = self._load_blackbook()
        self.session_start = None

    def _load_engines_config(self) -> dict:
        path = settings.ENGINES_FILE
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"engines": [], "banned_domains": [], "priority_sources": []}

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
        """Tạo session mới với headers ngụy trang cho MỖI request"""
        headers = get_stealth_headers()
        
        if HAS_CFFI:
            # curl_cffi: Giả lập TLS fingerprint của Chrome 120
            session = cffi_requests.Session(impersonate="chrome120")
            session.headers.update(headers)
            return session
        else:
            # Fallback httpx
            session = httpx.Client(headers=headers, timeout=20.0, follow_redirects=True)
            return session

    def get_keyword_state(self, keyword: str) -> dict:
        normalized = self._normalize_keyword(keyword)
        state_path = os.path.join(settings.KEYWORD_STATE_DIR, f"{normalized}.json")
        
        default_state = {
            "keyword": keyword,
            "normalized": normalized,
            "total_links_found": 0,
            "links_scraped": 0,
            "scraped_urls": [],
            "found_urls": [],
            "last_run": None,
            "run_count": 0,
            "is_exhausted": False
        }
        
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default_state
        return default_state

    def save_keyword_state(self, state: dict):
        normalized = state["normalized"]
        state_path = os.path.join(settings.KEYWORD_STATE_DIR, f"{normalized}.json")
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def _normalize_keyword(self, kw: str) -> str:
        import re
        kw = kw.lower()
        kw = re.sub(r'[^a-z0-9\s]', '', kw)
        kw = re.sub(r'\s+', '_', kw.strip())
        return kw[:50]

    def _is_time_remaining(self) -> bool:
        if self.session_start is None:
            return True
        elapsed = (datetime.now(timezone.utc) - datetime.fromtimestamp(self.session_start, timezone.utc)).total_seconds()
        return elapsed < (settings.WORK_MINUTES * 60 - 30)

    def _get_next_keyword(self, keywords: list[str]) -> tuple[str, dict] | None:
        """Lấy keyword tiếp theo chưa exhausted"""
        keyword_states = [(kw, self.get_keyword_state(kw)) for kw in keywords]
        
        def sort_key(item):
            kw, state = item
            exhausted = state.get("is_exhausted", False)
            last_run = state.get("last_run") or "0000"
            return (0 if not exhausted else 1, last_run)
        
        keyword_states.sort(key=sort_key)
        
        for kw, state in keyword_states:
            if not state.get("is_exhausted", False):
                return (kw, state)
        
        # Reset all
        logger.warning("⚠️  Tất cả keywords exhausted, reset tất cả")
        for kw, state in keyword_states:
            state["is_exhausted"] = False
            self.save_keyword_state(state)
        return (keyword_states[0][0], keyword_states[0][1])

    def search_startpage(self, session, keyword: str) -> list[dict]:
        """Search Startpage với session đã ngụy trang"""
        links = []
        try:
            if HAS_CFFI:
                resp = session.post(
                    "https://www.startpage.com/sp/search",
                    data={"query": keyword, "cat": "web"},
                    timeout=20
                )
            else:
                resp = session.post(
                    "https://www.startpage.com/sp/search",
                    data={"query": keyword, "cat": "web"},
                    timeout=20
                )
            
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", class_="w-gl__result-url"):
                href = a.get("href", "")
                if href.startswith("http"):
                    links.append({"url": href, "title": a.get_text(strip=True)[:100], "engine": "startpage"})
        except Exception as e:
            logger.warning(f"   Startpage failed: {e}")
        return links

    def search_brave(self, session, keyword: str) -> list[dict]:
        """Search Brave"""
        links = []
        try:
            encoded = quote_plus(keyword)
            url = f"https://search.brave.com/search?q={encoded}"
            resp = session.get(url, timeout=20)
            soup = BeautifulSoup(resp.text, "lxml")
            
            for div in soup.find_all("div", class_="snippet"):
                a = div.find("a")
                if a and a.get("href", "").startswith("http") and "brave.com" not in a["href"]:
                    links.append({"url": a["href"], "title": a.get_text(strip=True)[:100], "engine": "brave"})
        except Exception as e:
            logger.warning(f"   Brave failed: {e}")
        return links

    def search_duckduckgo(self, session, keyword: str) -> list[dict]:
        """Search DuckDuckGo HTML"""
        links = []
        try:
            encoded = quote_plus(keyword)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            resp = session.get(url, timeout=20)
            soup = BeautifulSoup(resp.text, "lxml")
            
            for a in soup.find_all("a", class_="result__a"):
                href = a.get("href", "")
                if href.startswith("http") and "duckduckgo.com" not in href:
                    links.append({"url": href, "title": a.get_text(strip=True)[:100], "engine": "duckduckgo"})
        except Exception as e:
            logger.warning(f"   DuckDuckGo failed: {e}")
        return links

    def search_single_keyword(self, keyword: str) -> list[dict]:
        """
        Search 1 keyword duy nhất qua cascade engines
        Dừng khi đủ 20 links
        Delay 8-15s giữa các engines
        """
        all_links = []
        seen_urls = set()
        banned_domains = self.engines_config.get("banned_domains", [])
        priority_sources = self.engines_config.get("priority_sources", [])
        
        search_fns = [
            ("Startpage", self.search_startpage),
            ("Brave", self.search_brave),
            ("DuckDuckGo", self.search_duckduckgo),
        ]
        
        for engine_name, search_fn in search_fns:
            if len(all_links) >= settings.LINKS_PER_SEARCH:
                break
            
            # TẠO SESSION MỚI CHO MỖI ENGINE (đổi UA, đổi TLS fingerprint)
            session = self._create_session()
            
            logger.info(f"   🔍 Thử {engine_name}...")
            try:
                engine_links = search_fn(session, keyword)
                
                for link in engine_links:
                    url = link["url"]
                    domain = urlparse(url).netloc.lower()
                    
                    if any(b in domain for b in banned_domains):
                        continue
                    if self.blackbook.get(domain, {}).get("status") == "banned":
                        continue
                    if url in seen_urls:
                        continue
                    
                    seen_urls.add(url)
                    link["is_priority_source"] = any(p in domain for p in priority_sources)
                    link["domain"] = domain
                    link["keyword"] = keyword
                    link["searched_at"] = datetime.now(timezone.utc).isoformat()
                    all_links.append(link)
                
                logger.info(f"   ✅ {engine_name}: +{len(engine_links)} links (tổng: {len(all_links)})")
            finally:
                session.close()
            
            # DELAY DÀI giữa các engines
            if len(all_links) < settings.LINKS_PER_SEARCH:
                human_delay(
                    min_sec=settings.MIN_REQUEST_DELAY,
                    max_sec=settings.MAX_REQUEST_DELAY
                )
        
        return all_links[:settings.LINKS_PER_SEARCH]

    def filter_new_links(self, links: list[dict], state: dict) -> list[dict]:
        """Lọc bỏ links đã từng thấy"""
        seen = set(state.get("found_urls", []))
        return [l for l in links if l["url"] not in seen]


def run_t0_single_keyword(keywords: list[str]) -> tuple[str, list[dict], dict] | None:
    """
    T0 Entry Point: Chỉ search 1 keyword
    Trả về: (keyword, new_links, state) hoặc None nếu hết giờ/hết keyword
    """
    searcher = T0Search()
    
    if searcher.session_start is None:
        searcher.session_start = datetime.now(timezone.utc).timestamp()
    
    if not searcher._is_time_remaining():
        return None
    
    result = searcher._get_next_keyword(keywords)
    if result is None:
        return None
    
    keyword, state = result
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🔑 KEYWORD: {keyword}")
    logger.info(f"   Lịch sử: Tìm {state.get('total_links_found',0)} / Cào {state.get('links_scraped',0)}")
    logger.info(f"{'='*60}")
    
    # Search
    links = searcher.search_single_keyword(keyword)
    state["total_links_found"] = state.get("total_links_found", 0) + len(links)
    
    # Filter mới
    new_links = searcher.filter_new_links(links, state)
    
    # Cập nhật found_urls
    for link in new_links:
        if link["url"] not in state.get("found_urls", []):
            state.setdefault("found_urls", []).append(link["url"])
    
    # Check exhausted
    if not new_links and state.get("total_links_found", 0) > 50:
        state["is_exhausted"] = True
        logger.warning(f"   ⚠️ Keyword EXHAUSTED")
    
    state["run_count"] = state.get("run_count", 0) + 1
    searcher.save_keyword_state(state)
    searcher._save_blackbook()
    
    logger.info(f"   📊 Tìm: {len(links)}, Mới: {len(new_links)}")
    
    if not new_links:
        return None
    
    return (keyword, new_links, state)
