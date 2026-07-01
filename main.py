"""
MAIN: Orchestrator - Pattern Pomodoro 25 phút / 15 phút nghỉ
Xoay vòng 35 từ khóa
Hỗ trợ chạy Local (vô hạn) và GitHub Actions (giới hạn bởi MAX_LOOPS)
"""
import os
import sys
import time
import logging
import uuid
import argparse
from datetime import datetime, timezone

from config import settings

# Import pipeline stages
from t0_search import run_t0
from t1_classify import run_t1
from t2_scrape import run_t2
from t3_normalize import run_t3
from t4_deduplicate import run_t4
from t5_upload import run_t5

# Đọc giới hạn vòng lặp từ Environment Variable (Dùng cho GitHub Actions)
# Mặc định là 8 vòng (~5.3 tiếng) để nằm trong giới hạn 6 tiếng của GitHub Free
MAX_LOOPS = int(os.getenv("MAX_LOOPS", "8"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stderr
)
logger = logging.getLogger("MAIN")


def run_pipeline_session() -> dict:
    """
    Chạy 1 phiên pipeline hoàn chỉnh (trong giới hạn 25 phút của T0)
    """
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    logger.info("=" * 80)
    logger.info(f"🚀 PIPELINE SESSION STARTED")
    logger.info(f"   Run ID: {run_id}")
    logger.info(f"   Start:  {datetime.now().strftime('%H:%M:%S')}")
    logger.info("=" * 80)
    
    stats = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "keywords_used": [],
        "links_found": 0,
        "links_scraped": 0,
        "contents_validated": 0,
        "duplicates_removed": 0,
        "rules_uploaded": 0
    }
    
    session_start = time.time()
    
    try:
        # === T0: SEARCH (Tự giới hạn 25 phút bên trong) ===
        logger.info("\n" + "=" * 80)
        logger.info("🔍 STAGE T0: SEARCH")
        logger.info("=" * 80)
        
        links = run_t0()
        stats["links_found"] = len(links)
        
        if not links:
            logger.warning("⚠️  Không tìm được link nào, kết thúc session sớm")
            return stats
        
        # === T1: CLASSIFY ===
        logger.info("\n" + "=" * 80)
        logger.info("🏷️  STAGE T1: CLASSIFY")
        logger.info("=" * 80)
        
        classified_links = run_t1(links)
        
        if not classified_links:
            logger.warning("⚠️  Không có link nào sau khi classify")
            return stats

        # === T2: SCRAPE ===
        logger.info("\n" + "=" * 80)
        logger.info("📥 STAGE T2: SCRAPE")
        logger.info("=" * 80)
        
        scraped_contents = run_t2(classified_links)
        stats["links_scraped"] = len(scraped_contents)
        
        if not scraped_contents:
            logger.warning("⚠️  Không scrape được nội dung nào")
            return stats
        
        # === T3: NORMALIZE ===
        logger.info("\n" + "=" * 80)
        logger.info("🔧 STAGE T3: NORMALIZE")
        logger.info("=" * 80)
        
        normalized_contents = run_t3(scraped_contents)
        
        # === T4: DEDUPLICATE & SAVE LOCAL ===
        logger.info("\n" + "=" * 80)
        logger.info("🔍 STAGE T4: DEDUPLICATE")
        logger.info("=" * 80)
        
        unique_contents = run_t4(normalized_contents, run_id)
        stats["duplicates_removed"] = len(normalized_contents) - len(unique_contents)
        stats["contents_validated"] = len(unique_contents)
        
        # === T5: UPLOAD MONGODB ===
        logger.info("\n" + "=" * 80)
        logger.info("📤 STAGE T5: UPLOAD")
        logger.info("=" * 80)
        
        run_t5(unique_contents, run_id, stats)
        stats["rules_uploaded"] = len(unique_contents)
        
    except KeyboardInterrupt:
        logger.warning("⚠️  Người dùng ngắt (Ctrl+C) giữa chừng. Đang lưu trạng thái...")
    except Exception as e:
        logger.error(f"❌ Pipeline error: {e}", exc_info=True)
    
    # Calculate duration
    stats["duration_seconds"] = time.time() - session_start
    
    logger.info("\n" + "=" * 80)
    logger.info("📊 SESSION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"   Duration:        {stats['duration_seconds']/60:.1f} phút")
    logger.info(f"   Links found:     {stats['links_found']}")
    logger.info(f"   Links scraped:   {stats['links_scraped']}")
    logger.info(f"   Contents valid:  {stats['contents_validated']}")
    logger.info(f"   Duplicates:      {stats['duplicates_removed']}")
    logger.info(f"   Rules uploaded:  {stats['rules_uploaded']}")
    logger.info("=" * 80)
    
    return stats


def run_pomodoro_loop():
    """
    Loop Pomodoro: 25 phút làm việc, 15 phút nghỉ
    Tự động dừng sau MAX_LOOPS vòng (Phục vụ GitHub Actions)
    """
    logger.info("🎯 RULESWORLD SCRAPER - POMODORO MODE")
    logger.info(f"   Work time:    {settings.WORK_MINUTES} phút")
    logger.info(f"   Break time:   {settings.BREAK_MINUTES} phút")
    logger.info(f"   Max loops:    {MAX_LOOPS} vòng (~{MAX_LOOPS * (settings.WORK_MINUTES + settings.BREAK_MINUTES) / 60:.1f} giờ)")
    logger.info("")
    
    session_count = 0
    
    try:
        while session_count < MAX_LOOPS:
            session_count += 1
            
            logger.info("\n" + "🟢" * 40)
            logger.info(f"📝 SESSION #{session_count}/{MAX_LOOPS} - BẮT ĐẦU LÀM VIỆC")
            logger.info("🟢" * 40 + "\n")
            
            # Run pipeline
            stats = run_pipeline_session()
            
            # Nếu không còn gì để làm (tất cả keywords exhausted), có thể thoát sớm
            if stats["links_found"] == 0 and session_count > 1:
                logger.info("🏁 Không tìm được link mới nào. Có thể tất cả keywords đã exhausted.")
                break
            
            # Nếu chưa phải vòng cuối, mới nghỉ
            if session_count < MAX_LOOPS:
                break_time_seconds = settings.BREAK_MINUTES * 60
                next_time = datetime.fromtimestamp(time.time() + break_time_seconds).strftime('%H:%M:%S')
                
                logger.info("\n" + "🔴" * 40)
                logger.info(f"☕ BREAK TIME - NGHỈ {settings.BREAK_MINUTES} PHÚT")
                logger.info(f"   Session #{session_count} completed.")
                logger.info(f"   Next session starts at: {next_time}")
                logger.info("🔴" * 40 + "\n")
                
                # Sleep for break duration
                time.sleep(break_time_seconds)
            else:
                logger.info("\n🏁 ĐÃ ĐẠT GIỚI HẠN VÒNG LẶP, DỪNG PIPELINE.")
                
    except KeyboardInterrupt:
        logger.info("\n🛑 Nhận tín hiệu dừng từ người dùng (Ctrl+C). Thoát loop.")


def run_single_session():
    """Chạy 1 session duy nhất (cho testing local)"""
    # Ép MAX_LOOPS = 1 nếu chạy mode single
    global MAX_LOOPS
    MAX_LOOPS = 1
    stats = run_pipeline_session()
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rulesworld Scraper Pipeline")
    parser.add_argument(
        "--loop", 
        action="store_true", 
        help="Chạy loop Pomodoro liên tục (giới hạn bởi MAX_LOOPS)"
    )
    parser.add_argument(
        "--once", 
        action="store_true", 
        help="Chạy 1 session duy nhất (dùng để test)"
    )
    args = parser.parse_args()
    
    if args.loop:
        run_pomodoro_loop()
    else:
        # Mặc định nếu không truyền argument sẽ chạy 1 lần
        run_single_session()
