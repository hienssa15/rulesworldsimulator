"""
Test So Sánh Các Search Engine
=================================
Mục tiêu: Tìm search engine tốt nhất để cào link
Phương pháp: KHÔNG dùng API, chỉ dùng skill cào (requests + Playwright)
Từ khóa test: "silicon-based life alternative biochemistry"
"""
import requests
import time
import json
import re
import hashlib
import logging
from datetime import datetime
from urllib.parse import urlparse, quote_plus
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("search_test")

# ============================================================
# CẤU HÌNH TEST
# ============================================================
TEST_KEYWORD = "silicon-based life alternative biochemistry"
MAX_RESULTS_PER_ENGINE = 20
REQUEST_TIMEOUT = 20
DELAY_BETWEEN_TESTS = 3

# User-Agent rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def get_session():
    """Tạo session với headers giống browser thật"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENTS[0],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return session


def normalize_url(url):
    """Chuẩn hóa URL để so sánh trùng"""
    parsed = urlparse(url)
    # Bỏ www, query params, fragment
    domain = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{domain}{path}"


def url_hash(url):
    """Hash URL để check trùng"""
    normalized = normalize_url(url)
    return hashlib.md5(normalized.encode()).hexdigest()


def classify_domain(url):
    """Phân loại domain để đánh giá chất lượng"""
    domain = urlparse(url).netloc.lower()
    
    high_quality = ["wikipedia.org", "nature.com", "sciencedirect.com", 
                    "arxiv.org", "ncbi.nlm.nih.gov", "researchgate.net",
                    "orionsarm.com", "projectrho.com"]
    medium_quality = ["medium.com", "reddit.com", "quora.com", "youtube.com"]
    
    for hq in high_quality:
        if hq in domain:
            return "HIGH"
    for mq in medium_quality:
        if mq in domain:
            return "MEDIUM"
    return "STANDARD"


# ============================================================
# TEST 1: BRAVE SEARCH (requests thuần)
# ============================================================
def test_brave_requests(keyword):
    """Test Brave Search bằng requests thuần"""
    logger.info("🦁 BRAVE SEARCH (requests)...")
    session = get_session()
    
    # Brave Search URL
    url = f"https://search.brave.com/search?q={quote_plus(keyword)}"
    
    start = time.time()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        
        logger.info(f"   Status: {resp.status_code}")
        logger.info(f"   Content-Type: {resp.headers.get('content-type')}")
        logger.info(f"   Size: {len(resp.text)} chars")
        logger.info(f"   Time: {elapsed:.2f}s")
        
        if resp.status_code != 200:
            logger.warning(f"   ❌ Fail: status {resp.status_code}")
            return {"success": False, "links": [], "elapsed": elapsed, "method": "requests"}
        
        # Check nếu bị Cloudflare block
        if "Just a moment" in resp.text or "challenge-platform" in resp.text:
            logger.warning("   ❌ Bị Cloudflare block")
            return {"success": False, "links": [], "elapsed": elapsed, "method": "requests", "blocked": True}
        
        # Parse HTML
        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        
        # Brave thường dùng snippet hoặc a.snippet-url
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "brave.com" not in href:
                if any(x in href for x in [".com", ".org", ".net", ".edu"]):
                    links.append(href)
        
        # Dedup
        seen = set()
        unique_links = []
        for link in links:
            h = url_hash(link)
            if h not in seen:
                seen.add(h)
                unique_links.append(link)
                if len(unique_links) >= MAX_RESULTS_PER_ENGINE:
                    break
        
        logger.info(f"   ✅ Tìm được {len(unique_links)} links")
        return {
            "success": True,
            "links": unique_links,
            "elapsed": elapsed,
            "method": "requests",
            "status": resp.status_code,
        }
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"   ❌ Lỗi: {e}")
        return {"success": False, "links": [], "elapsed": elapsed, "method": "requests", "error": str(e)}


# ============================================================
# TEST 2: BRAVE SEARCH (Playwright + Radar)
# ============================================================
def test_brave_playwright(keyword):
    """Test Brave Search bằng Playwright + Radar"""
    logger.info("🦁 BRAVE SEARCH (Playwright + Radar)...")
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("   ⚠️ Playwright chưa cài, bỏ qua")
        return {"success": False, "links": [], "method": "playwright", "error": "not installed"}
    
    found_apis = []
    found_links = []
    
    def intercept_response(response):
        """Radar: đón bắt JSON response"""
        ct = response.headers.get("content-type", "")
        if "application/json" in ct:
            url = response.url
            if not any(x in url for x in ["google", "analytics", "ads", "tracking", "brave.com/api"]):
                found_apis.append(url)
    
    start = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.5"})
            
            # Kích hoạt Radar
            page.on("response", intercept_response)
            
            url = f"https://search.brave.com/search?q={quote_plus(keyword)}"
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Bóc links từ DOM
            all_links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            
            for link in all_links:
                if link.startswith("http") and "brave.com" not in link:
                    if any(x in link for x in [".com", ".org", ".net", ".edu"]):
                        found_links.append(link)
            
            browser.close()
        
        elapsed = time.time() - start
        
        # Dedup
        seen = set()
        unique_links = []
        for link in found_links:
            h = url_hash(link)
            if h not in seen:
                seen.add(h)
                unique_links.append(link)
                if len(unique_links) >= MAX_RESULTS_PER_ENGINE:
                    break
        
        logger.info(f"   Status: OK")
        logger.info(f"   Time: {elapsed:.2f}s")
        logger.info(f"   APIs bắt được: {len(found_apis)}")
        if found_apis:
            logger.info(f"   API samples: {found_apis[:3]}")
        logger.info(f"   ✅ Tìm được {len(unique_links)} links")
        
        return {
            "success": True,
            "links": unique_links,
            "elapsed": elapsed,
            "method": "playwright",
            "apis_found": found_apis,
        }
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"   ❌ Lỗi: {e}")
        return {"success": False, "links": [], "elapsed": elapsed, "method": "playwright", "error": str(e)}


# ============================================================
# TEST 3: YAHOO SEARCH (requests thuần)
# ============================================================
def test_yahoo_requests(keyword):
    """Test Yahoo Search bằng requests thuần"""
    logger.info("🟣 YAHOO SEARCH (requests)...")
    session = get_session()
    
    url = f"https://search.yahoo.com/search?p={quote_plus(keyword)}&n={MAX_RESULTS_PER_ENGINE}"
    
    start = time.time()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        
        logger.info(f"   Status: {resp.status_code}")
        logger.info(f"   Size: {len(resp.text)} chars")
        logger.info(f"   Time: {elapsed:.2f}s")
        
        if resp.status_code != 200:
            return {"success": False, "links": [], "elapsed": elapsed, "method": "requests"}
        
        # Check block
        if "captcha" in resp.text.lower() or "robot" in resp.text.lower():
            logger.warning("   ❌ Bị captcha/robot check")
            return {"success": False, "links": [], "elapsed": elapsed, "method": "requests", "blocked": True}
        
        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        
        # Yahoo thường dùng <a class="... ac-algo..." href="...">
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Yahoo hay redirect qua click.yahoo.com
            if "click.yahoo.com" in href:
                # Extract real URL từ RU parameter
                match = re.search(r"RU=(https?[^&/]+)", href)
                if match:
                    from urllib.parse import unquote
                    real_url = unquote(match.group(1))
                    links.append(real_url)
            elif href.startswith("http") and "yahoo.com" not in href:
                links.append(href)
        
        # Dedup
        seen = set()
        unique_links = []
        for link in links:
            h = url_hash(link)
            if h not in seen:
                seen.add(h)
                unique_links.append(link)
                if len(unique_links) >= MAX_RESULTS_PER_ENGINE:
                    break
        
        logger.info(f"   ✅ Tìm được {len(unique_links)} links")
        return {
            "success": True,
            "links": unique_links,
            "elapsed": elapsed,
            "method": "requests",
            "status": resp.status_code,
        }
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"   ❌ Lỗi: {e}")
        return {"success": False, "links": [], "elapsed": elapsed, "method": "requests", "error": str(e)}


# ============================================================
# TEST 4: YAHOO SEARCH (Playwright)
# ============================================================
def test_yahoo_playwright(keyword):
    """Test Yahoo Search bằng Playwright"""
    logger.info("🟣 YAHOO SEARCH (Playwright)...")
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("   ⚠️ Playwright chưa cài, bỏ qua")
        return {"success": False, "links": [], "method": "playwright", "error": "not installed"}
    
    found_links = []
    
    start = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            url = f"https://search.yahoo.com/search?p={quote_plus(keyword)}"
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Click qua consent nếu có
            try:
                consent_btn = page.locator("button:has-text('Accept')").first
                if consent_btn.is_visible(timeout=2000):
                    consent_btn.click()
                    time.sleep(1)
            except:
                pass
            
            # Bóc links
            all_links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            
            for link in all_links:
                if "yahoo.com" in link:
                    # Yahoo redirect link - extract real URL
                    match = re.search(r"RU=(https?[^&/]+)", link)
                    if match:
                        from urllib.parse import unquote
                        real_url = unquote(match.group(1))
                        found_links.append(real_url)
                elif link.startswith("http"):
                    found_links.append(link)
            
            browser.close()
        
        elapsed = time.time() - start
        
        # Dedup
        seen = set()
        unique_links = []
        for link in found_links:
            h = url_hash(link)
            if h not in seen:
                seen.add(h)
                unique_links.append(link)
                if len(unique_links) >= MAX_RESULTS_PER_ENGINE:
                    break
        
        logger.info(f"   Time: {elapsed:.2f}s")
        logger.info(f"   ✅ Tìm được {len(unique_links)} links")
        
        return {
            "success": True,
            "links": unique_links,
            "elapsed": elapsed,
            "method": "playwright",
        }
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"   ❌ Lỗi: {e}")
        return {"success": False, "links": [], "elapsed": elapsed, "method": "playwright", "error": str(e)}


# ============================================================
# TEST 5: BING SEARCH (requests thuần) - BACKUP
# ============================================================
def test_bing_requests(keyword):
    """Test Bing Search bằng requests thuần"""
    logger.info("🔵 BING SEARCH (requests)...")
    session = get_session()
    
    url = f"https://www.bing.com/search?q={quote_plus(keyword)}&count={MAX_RESULTS_PER_ENGINE}"
    
    start = time.time()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        
        logger.info(f"   Status: {resp.status_code}")
        logger.info(f"   Size: {len(resp.text)} chars")
        logger.info(f"   Time: {elapsed:.2f}s")
        
        if resp.status_code != 200:
            return {"success": False, "links": [], "elapsed": elapsed, "method": "requests"}
        
        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        
        # Bing dùng <li class="b_algo"> <h2> <a href="...">
        for li in soup.find_all("li", class_="b_algo"):
            a = li.find("a", href=True)
            if a:
                links.append(a["href"])
        
        # Fallback: tất cả links
        if not links:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and "bing.com" not in href and "microsoft.com" not in href:
                    links.append(href)
        
        # Dedup
        seen = set()
        unique_links = []
        for link in links:
            h = url_hash(link)
            if h not in seen:
                seen.add(h)
                unique_links.append(link)
                if len(unique_links) >= MAX_RESULTS_PER_ENGINE:
                    break
        
        logger.info(f"   ✅ Tìm được {len(unique_links)} links")
        return {
            "success": True,
            "links": unique_links,
            "elapsed": elapsed,
            "method": "requests",
            "status": resp.status_code,
        }
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"   ❌ Lỗi: {e}")
        return {"success": False, "links": [], "elapsed": elapsed, "method": "requests", "error": str(e)}


# ============================================================
# TEST 6: DUCKDUCKGO HTML (requests thuần) - BACKUP
# ============================================================
def test_ddg_html_requests(keyword):
    """Test DuckDuckGo HTML version bằng requests"""
    logger.info("🦆 DUCKDUCKGO HTML (requests)...")
    session = get_session()
    
    # DuckDuckGo có HTML-only version: html.duckduckgo.com
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(keyword)}"
    
    start = time.time()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        
        logger.info(f"   Status: {resp.status_code}")
        logger.info(f"   Size: {len(resp.text)} chars")
        logger.info(f"   Time: {elapsed:.2f}s")
        
        if resp.status_code != 200:
            return {"success": False, "links": [], "elapsed": elapsed, "method": "requests"}
        
        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        
        # DDG HTML: <a rel="nofollow" class="result__url" href="...">
        for a in soup.find_all("a", class_="result__snippet"):
            # Snippet link thường redirect, cần lấy từ result__url
            pass
        
        for a in soup.find_all("a", class_="result__a"):
            href = a.get("href", "")
            if href.startswith("//duckduckgo.com/l/?"):
                # Extract real URL từ uddg param
                match = re.search(r"uddg=(https?[^&]+)", href)
                if match:
                    from urllib.parse import unquote
                    real_url = unquote(match.group(1))
                    links.append(real_url)
            elif href.startswith("http"):
                links.append(href)
        
        # Dedup
        seen = set()
        unique_links = []
        for link in links:
            h = url_hash(link)
            if h not in seen:
                seen.add(h)
                unique_links.append(link)
                if len(unique_links) >= MAX_RESULTS_PER_ENGINE:
                    break
        
        logger.info(f"   ✅ Tìm được {len(unique_links)} links")
        return {
            "success": True,
            "links": unique_links,
            "elapsed": elapsed,
            "method": "requests",
            "status": resp.status_code,
        }
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"   ❌ Lỗi: {e}")
        return {"success": False, "links": [], "elapsed": elapsed, "method": "requests", "error": str(e)}


# ============================================================
# TEST 7: STARTPAGE (requests thuần) - BACKUP
# ============================================================
def test_startpage_requests(keyword):
    """Test Startpage (Google results nhưng privacy)"""
    logger.info("🔒 STARTPAGE (requests)...")
    session = get_session()
    
    url = "https://www.startpage.com/do/dsearch"
    data = {"query": keyword, "cat": "web"}
    
    start = time.time()
    try:
        resp = session.post(url, data=data, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        
        logger.info(f"   Status: {resp.status_code}")
        logger.info(f"   Size: {len(resp.text)} chars")
        logger.info(f"   Time: {elapsed:.2f}s")
        
        if resp.status_code != 200:
            return {"success": False, "links": [], "elapsed": elapsed, "method": "requests"}
        
        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        
        # Startpage dùng class="w-gl__result-url"
        for a in soup.find_all("a", class_="w-gl__result-url"):
            href = a.get("href", "")
            if href.startswith("http"):
                links.append(href)
        
        # Fallback
        if not links:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and "startpage.com" not in href:
                    links.append(href)
        
        # Dedup
        seen = set()
        unique_links = []
        for link in links:
            h = url_hash(link)
            if h not in seen:
                seen.add(h)
                unique_links.append(link)
                if len(unique_links) >= MAX_RESULTS_PER_ENGINE:
                    break
        
        logger.info(f"   ✅ Tìm được {len(unique_links)} links")
        return {
            "success": True,
            "links": unique_links,
            "elapsed": elapsed,
            "method": "requests",
            "status": resp.status_code,
        }
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"   ❌ Lỗi: {e}")
        return {"success": False, "links": [], "elapsed": elapsed, "method": "requests", "error": str(e)}


# ============================================================
# TEST 8: QWANT (requests thuần) - BACKUP
# ============================================================
def test_qwant_requests(keyword):
    """Test Qwant search"""
    logger.info("🔷 QWANT (requests)...")
    session = get_session()
    
    url = f"https://www.qwant.com/?q={quote_plus(keyword)}&t=web"
    
    start = time.time()
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start
        
        logger.info(f"   Status: {resp.status_code}")
        logger.info(f"   Size: {len(resp.text)} chars")
        logger.info(f"   Time: {elapsed:.2f}s")
        
        if resp.status_code != 200:
            return {"success": False, "links": [], "elapsed": elapsed, "method": "requests"}
        
        # Qwant dùng JS render → requests có thể không lấy được links
        # Thử bóc SSR data
        ssr_match = re.search(r'<script[^>]*>(.*?"organic_results".*?)</script>', resp.text, re.DOTALL)
        if ssr_match:
            try:
                # Tìm JSON trong script
                json_match = re.search(r'(\{.*"organic_results".*\})', ssr_match.group(1))
                if json_match:
                    data = json.loads(json_match.group(1))
                    links = []
                    for item in data.get("organic_results", []):
                        if "url" in item:
                            links.append(item["url"])
                    
                    logger.info(f"   ✅ Bóc được SSR data: {len(links)} links")
                    return {
                        "success": True,
                        "links": links[:MAX_RESULTS_PER_ENGINE],
                        "elapsed": elapsed,
                        "method": "requests-ssr",
                        "status": resp.status_code,
                    }
            except:
                pass
        
        logger.warning("   ⚠️ Không tìm thấy SSR data (Qwant cần JS)")
        return {"success": False, "links": [], "elapsed": elapsed, "method": "requests", "needs_js": True}
        
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"   ❌ Lỗi: {e}")
        return {"success": False, "links": [], "elapsed": elapsed, "method": "requests", "error": str(e)}


# ============================================================
# SO SÁNH TRÙNG LẶP
# ============================================================
def compare_overlap(results):
    """So sánh độ trùng giữa các engine"""
    logger.info("\n" + "=" * 80)
    logger.info("📊 SO SÁNH ĐỘ TRÙNG LẶP")
    logger.info("=" * 80)
    
    # Gom tất cả links theo engine
    engine_links = {}
    for name, result in results.items():
        if result.get("success") and result.get("links"):
            engine_links[name] = set(normalize_url(u) for u in result["links"])
    
    if len(engine_links) < 2:
        logger.info("⚠️ Không đủ engine thành công để so sánh")
        return
    
    # Ma trận trùng lặp
    engines = list(engine_links.keys())
    logger.info("\n🔀 MA TRẬN TRÙNG LẶP (%):")
    logger.info("-" * 80)
    
    header = f"{'Engine':<30}" + "".join(f"{e[:10]:<12}" for e in engines)
    logger.info(header)
    logger.info("-" * 80)
    
    for e1 in engines:
        row = f"{e1:<30}"
        for e2 in engines:
            if e1 == e2:
                row += f"{'100%':<12}"
            else:
                overlap = len(engine_links[e1] & engine_links[e2])
                total = max(len(engine_links[e1]), len(engine_links[e2]))
                pct = (overlap / total * 100) if total > 0 else 0
                row += f"{pct:.0f}%{'':<8}"
        logger.info(row)
    
    # Links xuất hiện ở NHIỀU engine (chất lượng cao)
    logger.info("\n🏆 LINKS XUẤT HIỆN Ở NHIỀU ENGINE (HIGH CONFIDENCE):")
    logger.info("-" * 80)
    
    all_urls = {}
    for name, urls in engine_links.items():
        for url in urls:
            if url not in all_urls:
                all_urls[url] = []
            all_urls[url].append(name)
    
    multi_engine = [(url, engines) for url, engines in all_urls.items() if len(engines) >= 2]
    multi_engine.sort(key=lambda x: len(x[1]), reverse=True)
    
    for url, engines in multi_engine[:15]:
        logger.info(f"   [{len(engines)} engines] {url}")
        logger.info(f"      Found in: {', '.join(engines)}")
    
    # Links độc quyền (chỉ 1 engine có)
    logger.info("\n🎯 LINKS ĐỘC QUYỀN (chỉ 1 engine có):")
    logger.info("-" * 80)
    
    unique_per_engine = {}
    for name, urls in engine_links.items():
        unique = [u for u in urls if len(all_urls[u]) == 1]
        unique_per_engine[name] = unique
        logger.info(f"   {name}: {len(unique)} links độc quyền")


# ============================================================
# BÁO CÁO TỔNG KẾT
# ============================================================
def generate_report(results):
    """Xuất báo cáo tổng kết"""
    logger.info("\n" + "=" * 80)
    logger.info("📋 BÁO CÁO TỔNG KẾT")
    logger.info("=" * 80)
    
    # Bảng tổng hợp
    logger.info(f"\n{'Engine':<35} {'Method':<15} {'Status':<10} {'Links':<8} {'Time':<10} {'HQ':<5}")
    logger.info("-" * 85)
    
    rankings = []
    
    for name, result in results.items():
        status = "✅ OK" if result.get("success") else "❌ FAIL"
        if result.get("blocked"):
            status = "🚫 BLOCK"
        elif result.get("error"):
            status = "💥 ERROR"
        elif result.get("needs_js"):
            status = "⚠️ NEEDS JS"
        
        links_count = len(result.get("links", []))
        elapsed = result.get("elapsed", 0)
        method = result.get("method", "?")
        
        # Đếm high quality links
        hq_count = sum(1 for u in result.get("links", []) if classify_domain(u) == "HIGH")
        
        logger.info(f"{name:<35} {method:<15} {status:<10} {links_count:<8} {elapsed:<10.2f} {hq_count:<5}")
        
        # Score: links_count * 2 + hq_count * 5 - elapsed
        score = links_count * 2 + hq_count * 5 - elapsed
        rankings.append((name, score, links_count, hq_count, elapsed, result.get("success", False)))
    
    # Xếp hạng
    rankings.sort(key=lambda x: x[1], reverse=True)
    
    logger.info("\n🏆 XẾP HẠNG:")
    logger.info("-" * 85)
    for i, (name, score, links, hq, elapsed, success) in enumerate(rankings, 1):
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"#{i}"
        logger.info(f"   {medal} {name:<35} Score: {score:>6.1f}  (Links: {links}, HQ: {hq}, Time: {elapsed:.2f}s)")
    
    # Khuyến nghị
    logger.info("\n💡 KHUYẾN NGHỊ:")
    logger.info("-" * 85)
    
    top_3 = rankings[:3]
    if top_3:
        best = top_3[0]
        logger.info(f"   🏆 ENGINE TỐT NHẤT: {best[0]}")
        logger.info(f"      Score: {best[1]:.1f}, Links: {best[2]}, HQ: {best[3]}, Time: {best[4]:.2f}s")
        
        if len(top_3) >= 2:
            logger.info(f"   🥈 BACKUP 1: {top_3[1][0]}")
        if len(top_3) >= 3:
            logger.info(f"   🥉 BACKUP 2: {top_3[2][0]}")
    
    # Chiến lược đề xuất
    logger.info("\n🎯 CHIẾN LƯỢC ĐỀ XUẤT:")
    successful = [r for r in rankings if r[5]]
    if len(successful) >= 2:
        logger.info(f"   ✅ Chơi TẤT: Dùng {len(successful)} engine thành công")
        logger.info(f"      - Engine chính: {successful[0][0]}")
        logger.info(f"      - Engine phụ: {successful[1][0]}")
        logger.info(f"      - Dedup bằng URL hash")
    elif len(successful) == 1:
        logger.info(f"   ⚠️ Chỉ có 1 engine hoạt động: {successful[0][0]}")
        logger.info(f"      Cần test thêm hoặc dùng Playwright cho các engine khác")
    else:
        logger.info(f"   ❌ Không engine nào hoạt động với requests")
        logger.info(f"      → PHẢI dùng Playwright cho tất cả")


# ============================================================
# MAIN
# ============================================================
def main():
    logger.info("=" * 80)
    logger.info("🧪 TEST SO SÁNH SEARCH ENGINES")
    logger.info("=" * 80)
    logger.info(f"🔍 Từ khóa test: '{TEST_KEYWORD}'")
    logger.info(f"📊 Max results/engine: {MAX_RESULTS_PER_ENGINE}")
    logger.info("")
    
    results = {}
    
    # Chạy tất cả test
    tests = [
        ("BRAVE-requests", test_brave_requests),
        ("BRAVE-playwright", test_brave_playwright),
        ("YAHOO-requests", test_yahoo_requests),
        ("YAHOO-playwright", test_yahoo_playwright),
        ("BING-requests", test_bing_requests),
        ("DDG-HTML-requests", test_ddg_html_requests),
        ("STARTPAGE-requests", test_startpage_requests),
        ("QWANT-requests", test_qwant_requests),
    ]
    
    for name, test_func in tests:
        logger.info(f"\n{'='*80}")
        logger.info(f"🎯 TEST: {name}")
        logger.info(f"{'='*80}")
        
        try:
            result = test_func(TEST_KEYWORD)
            results[name] = result
        except Exception as e:
            logger.error(f"💥 Test {name} crash: {e}")
            results[name] = {"success": False, "links": [], "error": str(e)}
        
        time.sleep(DELAY_BETWEEN_TESTS)
    
    # So sánh trùng
    compare_overlap(results)
    
    # Báo cáo
    generate_report(results)
    
    # Lưu kết quả chi tiết
    output_file = "search_test_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "keyword": TEST_KEYWORD,
            "timestamp": datetime.now().isoformat(),
            "results": {k: {**v, "links": v.get("links", [])[:10]} for k, v in results.items()}
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n💾 Kết quả chi tiết đã lưu → {output_file}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
