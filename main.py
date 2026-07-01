"""
MAIN: Orchestrator - TUẦN TỰ TỪNG KEYWORD
Flow: Keyword A → Search → Classify → Scrape → Normalize → Dedup → Upload → Keyword B → ...
"""
import os
import sys
import time
import logging
import uuid
import json
import argparse
from datetime import datetime, timezone

from config import settings
from t0_search import run_t0_single_keyword
from t1_classify import run_t1
from t2_scrape import run_t2
from t3_normalize import run_t3
from t4_deduplicate import run_t4
from t5_upload import run_t5
from stealth import keyword_break, human_delay

MAX_LOOPS = int(os.getenv("MAX_LOOPS", "8"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stderr
)
logger = logging.getLogger("MAIN")


def load_keywords() -> list[str]:
    """Load 35 keywords"""
    path = settings.KEYWORDS_FILE
    if not os.path.exists(path):
        logger.error(f"Không tìm thấy {path}")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f).get("keywords", [])


def process_single_keyword(keywords: list[str], run_id: str, stats: dict) -> bool:
    """
    Xửśli 1 keyword hoàn chỉnh: Search → Classify → Scrape → Normalize → Dedup → Upload
    Trả về True nếu xử lý thành công, False nếu hết keyword/thời gian
    """
    # === T0: Search 1 keyword ===
    result = run_t0_single_keyword(keywords)
    if result is None:
        return False
    
    keyword, links, state = result
    stats["keywords_used"].append(keyword)
    stats["links_found"] += len(links)
    
    # === T1: Classify ===
    classified = run_t1(links)
    
    # === T2: Scrape (CHẬM - 8-20s/link) ===
    scraped = run_t2(classified)
    stats["links_scraped"] += len(scraped)
    
    if not scraped:
        return True  # Vẫn trả về True để chuyển keyword khác
    
    # === T3: Normalize ===
    normalized = run_t3(scraped)
    
    # === T4: Deduplicate & Save ===
    unique = run_t4(normalized, run_id)
    stats["duplicates_removed"] += len(normalized) - len(unique)
    stats["contents_validated"] += len(unique)
    
    # === T5: Upload ===
    run_t5(unique, run_id, stats)
    stats["rules_uploaded"] += len(unique)
    
    return True


def run_pomodoro_loop():
    """Loop Pomodoro với xử lý tuần tự từng keyword"""
    keywords = load_keywords()
    logger.info("🎯 RULESWORLD SCRAPER - ANTI-BAN MODE")
    logger.info(f"   Keywords: {len(keywords)}")
    logger.info(f"   Delay/req: {settings.MIN_REQUEST_DELAY}-{settings.MAX_REQUEST_DELAY}s")
    logger.info(f"   Break/kw: {settings.MIN_KEYWORD_BREAK}-{settings.MAX_KEYWORD_BREAK}s")
    logger.info(f"   Max loops: {MAX_LOOPS}")
    logger.info("")
    
    session_count = 0
    
    try:
        while session_count < MAX_LOOPS:
            session_count += 1
            run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            session_start = time.time()
            
            logger.info("\n" + "🟢" * 40)
            logger.info(f"📝 SESSION #{session_count}/{MAX_LOOPS}")
            logger.info(f"   Run ID: {run_id}")
            logger.info(f"   Start: {datetime.now().strftime('%H:%M:%S')}")
            logger.info("🟢" * 40 + "\n")
            
            stats = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "keywords_used": [],
                "links_found": 0,
                "links_scraped": 0,
                "contents_validated": 0,
                "duplicates_removed": 0,
                "rules_uploaded": 0
            }
            
            # XỬ LÝ TUẦN TỰ TỪNG KEYWORD
            while True:
                # Check thời gian 25 phút
                elapsed = time.time() - session_start
                if elapsed >= (settings.WORK_MINUTES * 60 - 30):
                    logger.info(f"\n⏰ Hết 25 phút (đã dùng {elapsed/60:.1f} phút)")
                    break
                
                # Xử lý 1 keyword
                success = process_single_keyword(keywords, run_id, stats)
                
                if not success:
                    logger.info("🏁 Hết keyword hoặc không tìm được link mới")
                    break
                
                # NGHỈ DÀI giữa các keywords
                keyword_break(
                    min_sec=settings.MIN_KEYWORD_BREAK,
                    max_sec=settings.MAX_KEYWORD_BREAK
                )
            
            # Session summary
            stats["duration_seconds"] = time.time() - session_start
            logger.info("\n" + "=" * 80)
            logger.info(f"📊 SESSION #{session_count} SUMMARY")
            logger.info("=" * 80)
            logger.info(f"   Duration:    {stats['duration_seconds']/60:.1f} phút")
            logger.info(f"   Keywords:    {len(stats['keywords_used'])}")
            logger.info(f"   Links:       {stats['links_found']} found → {stats['links_scraped']} scraped")
            logger.info(f"   Contents:    {stats['contents_validated']} valid ({stats['duplicates_removed']} dup)")
            logger.info("=" * 80)
            
            # Save run log
            run_t5([], run_id, stats)
            
            # Nghỉ Pomodoro nếu chưa phải vòng cuối
            if session_count < MAX_LOOPS:
                break_sec = settings.BREAK_MINUTES * 60
                logger.info("\n" + "🔴" * 40)
                logger.info(f"☕ POMODORO BREAK - {settings.BREAK_MINUTES} phút")
                next_t = datetime.fromtimestamp(time.time() + break_sec).strftime('%H:%M:%S')
                logger.info(f"   Next session: {next_t}")
                logger.info("🔴" * 40 + "\n")
                time.sleep(break_sec)
            else:
                logger.info("\n🏁 ĐẠT GIỚI HẠN VÒNG LẶP")
                
    except KeyboardInterrupt:
        logger.info("\n🛑 Dừng bởi người dùng")


def run_single_session():
    """Chạy 1 session (test)"""
    global MAX_LOOPS
    MAX_LOOPS = 1
    keywords = load_keywords()
    
    run_id = f"test_{uuid.uuid4().hex[:8]}"
    stats = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "keywords_used": [], "links_found": 0, "links_scraped": 0,
        "contents_validated": 0, "duplicates_removed": 0, "rules_uploaded": 0
    }
    
    process_single_keyword(keywords, run_id, stats)
    
    logger.info(f"\n📊 Test hoàn tất: {stats}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Chạy loop Pomodoro")
    parser.add_argument("--once", action="store_true", help="Chạy 1 keyword (test)")
    args = parser.parse_args()
    
    if args.loop:
        run_pomodoro_loop()
    else:
        run_single_session()
