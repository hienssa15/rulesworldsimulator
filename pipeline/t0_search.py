"""
T0: SEARCH ENGINE - Startpage
Sinh từ khóa mới bằng LLM, search trên Startpage, trả về 20 links
"""
import requests
import time
import json
import re
import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus
from config import settings

logger = logging.getLogger(__name__)


class T0Search:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        
        # Handle MongoDB connection với try-catch
        self.mongo = None
        self.db = None
        
        if settings.MONGODB_URI:
            try:
                from pymongo import MongoClient
                self.mongo = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
                # Test connection
                self.mongo.admin.command('ping')
                self.db = self.mongo[settings.MONGODB_DB_NAME]
                logger.info("✅ MongoDB connected successfully")
            except Exception as e:
                logger.warning(f"⚠️  MongoDB connection failed: {e}")
                logger.warning("   Pipeline will continue without MongoDB")
                self.mongo = None
                self.db = None

    def get_used_keywords(self) -> list[str]:
        """Lấy danh sách từ khóa đã dùng từ MongoDB"""
        if not self.db:
            return []
        
        try:
            keywords = list(self.db[settings.MONGODB_COLLECTION_KEYWORDS].find())
            return [kw["keyword"] for kw in keywords]
        except Exception as e:
            logger.warning(f"Không thể đọc keywords từ MongoDB: {e}")
            return []

    def generate_keywords_with_llm(self, count: int = 5) -> list[str]:
        """Dùng LLM sinh từ khóa mới, không lặp lại"""
        if not settings.GEMINI_KEY:
            logger.warning("Không có GEMINI_KEY, dùng từ khóa mặc định")
            return self._fallback_keywords(count)
        
        used_keywords = self.get_used_keywords()
        
        prompt = f"""Bạn là chuyên gia về alternative biochemistry và speculative evolution.
Sinh {count} từ khóa tìm kiếm tiếng Anh về sự sống ngoài Trái Đất.

Yêu cầu:
1. Mỗi từ khóa phải kết hợp ít nhất 2 yếu tố từ danh sách sau:
   - Base elements: {', '.join(settings.TOPIC_TREE['base_elements'])}
   - Solvents: {', '.join(settings.TOPIC_TREE['solvents'])}
   - Environments: {', '.join(settings.TOPIC_TREE['environments'])}
   - Metabolism: {', '.join(settings.TOPIC_TREE['metabolism'])}

2. KHÔNG lặp lại các từ khóa đã dùng:
{chr(10).join(['- ' + kw for kw in used_keywords[-50:]])}

3. Từ khóa phải cụ thể, dễ tìm được bài viết chất lượng.

Output: JSON array, ví dụ: ["keyword 1", "keyword 2", ...]
"""
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.7, "max_output_tokens": 500}
            )
            
            # Parse JSON từ response
            text = response.text
            json_match = re.search(r'\[.*?\]', text, re.DOTALL)
            if json_match:
                keywords = json.loads(json_match.group())
                return keywords[:count]
            
        except Exception as e:
            logger.error(f"Lỗi gọi LLM: {e}")
        
        return self._fallback_keywords(count)

    def _fallback_keywords(self, count: int) -> list[str]:
        """Từ khóa mặc định nếu LLM fail"""
        import random
        
        keywords = []
        for _ in range(count):
            base = random.choice(settings.TOPIC_TREE["base_elements"])
            solvent = random.choice(settings.TOPIC_TREE["solvents"])
            env = random.choice(settings.TOPIC_TREE["environments"])
            keywords.append(f"{base} based life with {solvent} in {env}")
        
        return keywords

    def search_startpage(self, keyword: str) -> list[dict]:
        """Search trên Startpage, trả về danh sách links"""
        data = {"query": keyword, "cat": "web"}
        
        try:
            resp = self.session.post(
                settings.SEARCH_URL,
                data=data,
                timeout=20
            )
            resp.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            
            links = []
            for a in soup.find_all("a", class_="w-gl__result-url"):
                href = a.get("href", "")
                if href.startswith("http"):
                    links.append({
                        "url": href,
                        "title": a.get_text(strip=True),
                        "keyword": keyword,
                        "searched_at": datetime.now(timezone.utc).isoformat()
                    })
            
            # Fallback nếu không tìm thấy class cụ thể
            if not links:
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and "startpage.com" not in href:
                        links.append({
                            "url": href,
                            "title": a.get_text(strip=True)[:100],
                            "keyword": keyword,
                            "searched_at": datetime.now(timezone.utc).isoformat()
                        })
            
            return links[:settings.MAX_RESULTS_PER_SEARCH]
            
        except Exception as e:
            logger.error(f"Lỗi search '{keyword}': {e}")
            return []

    def save_keywords(self, keywords: list[str], run_id: str):
        """Lưu từ khóa đã dùng vào MongoDB"""
        if not self.db:
            return
        
        try:
            for kw in keywords:
                self.db[settings.MONGODB_COLLECTION_KEYWORDS].insert_one({
                    "keyword": kw,
                    "normalized": self._normalize_keyword(kw),
                    "used_at": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id
                })
        except Exception as e:
            logger.warning(f"Không thể lưu keywords vào MongoDB: {e}")

    def _normalize_keyword(self, kw: str) -> str:
        """Chuẩn hóa từ khóa để so sánh"""
        kw = kw.lower()
        kw = re.sub(r'[^a-z0-9\s]', '', kw)
        words = sorted(kw.split())
        return ' '.join(words)

    def run(self, run_id: str) -> list[dict]:
        """
        Chạy T0: sinh từ khóa + search
        Trả về danh sách links (tối đa LINKS_PER_RUN)
        """
        logger.info("=" * 80)
        logger.info("🔍 T0: SEARCH ENGINE")
        logger.info("=" * 80)
        
        # Sinh từ khóa
        keywords = self.generate_keywords_with_llm(count=5)
        logger.info(f"✅ Sinh được {len(keywords)} từ khóa:")
        for i, kw in enumerate(keywords, 1):
            logger.info(f"   {i}. {kw}")
        
        # Lưu từ khóa
        self.save_keywords(keywords, run_id)
        
        # Search từng từ khóa
        all_links = []
        for keyword in keywords:
            logger.info(f"\n🔎 Searching: {keyword}")
            links = self.search_startpage(keyword)
            logger.info(f"   ✅ Tìm được {len(links)} links")
            all_links.extend(links)
            time.sleep(settings.SEARCH_DELAY_SECONDS)
            
            if len(all_links) >= settings.LINKS_PER_RUN:
                break
        
        # Giới hạn số links
        all_links = all_links[:settings.LINKS_PER_RUN]
        
        logger.info(f"\n📊 TỔNG: {len(all_links)} links")
        
        return all_links
