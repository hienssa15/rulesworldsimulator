"""
World Lore Harvester - main.py
Pipeline: Scrape → LLM Extract (batch) → Normalize → MongoDB

Thiết kế cho GitHub Actions free tier:
- Mỗi job chạy ≤ 25 phút
- Gemini free tier: 7 keys xoay vòng, delay giữa call
- State tracking: biết đã xử lý đến đâu
- MongoDB: 1 snapshot document master + collection individual rules
"""
import json
import os
import sys
import logging
import time
from datetime import datetime, timezone

from config import settings
from scrapers import OrionsArmScraper, SpeculativeEvoScraper, ProjectRhoScraper
from processors import LoreExtractor
from normalizer import JsonBuilder
from storage import MongoUploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

DATA_DIR = "data"


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# ============================================================
# PHASE 1: SCRAPE
# ============================================================

def cmd_scrape(source: str):
    """Cào dữ liệu thô từ 1 nguồn, lưu vào data/raw_<source>.json"""
    ensure_data_dir()

    scrapers = {
        "orions_arm": (OrionsArmScraper, "raw_orions.json"),
        "spec_evo":   (SpeculativeEvoScraper, "raw_spec_evo.json"),
        "project_rho": (ProjectRhoScraper, "raw_project_rho.json"),
    }

    if source not in scrapers:
        logger.error(f"Nguồn không hợp lệ: {source}. Chọn: {list(scrapers.keys())}")
        sys.exit(1)

    ScraperClass, filename = scrapers[source]
    logger.info(f"Bắt đầu scrape: {source}")

    scraper = ScraperClass()
    articles = scraper.scrape_all()

    output_path = os.path.join(DATA_DIR, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    logger.info(f"Đã lưu {len(articles)} mục → {output_path}")


# ============================================================
# PHASE 2: EXTRACT (batch LLM)
# ============================================================

def _load_all_raw() -> list[dict]:
    """Gộp tất cả file raw JSON thành 1 danh sách."""
    all_articles = []
    files = {
        "raw_orions.json": "orions_arm",
        "raw_spec_evo.json": "speculative_evo",
        "raw_project_rho.json": "project_rho",
    }

    for filename, source in files.items():
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                articles = json.load(f)
                for a in articles:
                    a.setdefault("source", source)
                all_articles.extend(articles)
            logger.info(f"Đã load {len(articles)} mục từ {filename}")
        else:
            logger.warning(f"Không tìm thấy: {filepath}")

    logger.info(f"Tổng số article: {len(all_articles)}")
    return all_articles


def cmd_extract_batch(batch_id: int):
    """
    Xử lý batch thứ batch_id bằng LLM.
    Mỗi batch = ARTICLES_PER_BATCH articles.
    Output: data/extracted_batch_<id>.json
    """
    ensure_data_dir()
    output_path = os.path.join(DATA_DIR, f"extracted_batch_{batch_id}.json")

    # Kiểm tra đã xử lý chưa (tránh chạy lại)
    if os.path.exists(output_path):
        logger.info(f"Batch {batch_id} đã có kết quả, bỏ qua")
        return

    all_articles = _load_all_raw()
    batch_size = settings.ARTICLES_PER_BATCH
    start = batch_id * batch_size
    end = start + batch_size
    batch_articles = all_articles[start:end]

    if not batch_articles:
        logger.info(f"Batch {batch_id} rỗng (start={start}, total={len(all_articles)})")
        # Ghi file rỗng để GitHub Actions artifact không bị lỗi
        with open(output_path, "w") as f:
            json.dump([], f)
        return

    logger.info(
        f"Batch {batch_id}: xử lý article [{start}..{end-1}] "
        f"({len(batch_articles)} bài)"
    )

    extractor = LoreExtractor()
    results = []
    start_time = time.time()

    for i, article in enumerate(batch_articles):
        # Kiểm tra thời gian: dừng lại nếu gần đến giới hạn 22 phút
        elapsed = time.time() - start_time
        if elapsed > 22 * 60:
            logger.warning(f"Gần hết thời gian (elapsed={elapsed:.0f}s), dừng ở article {i}")
            break

        title = article.get("title", f"article_{start+i}")
        logger.info(f"  [{i+1}/{len(batch_articles)}] {title}")

        rule = extractor.extract_from_article(article)
        if rule:
            rule["batch_id"] = batch_id
            rule["article_index"] = start + i
            results.append(rule)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(
        f"Batch {batch_id} hoàn tất: {len(results)} rules "
        f"từ {len(batch_articles)} articles"
    )


# ============================================================
# PHASE 3: FINALIZE
# ============================================================

def cmd_finalize():
    """
    Gộp tất cả extracted_batch_*.json → normalize → upload MongoDB.
    Ghi 2 nơi:
      1. data/biology_rules_final.json (local artifact)
      2. MongoDB: harvest_snapshot (1 doc master) + biology_rules (per-rule)
    """
    ensure_data_dir()
    logger.info("=== FINALIZE: Gộp batches → Normalize → MongoDB ===")

    # Gộp tất cả batches
    all_rules = []
    batch_files = sorted([
        f for f in os.listdir(DATA_DIR)
        if f.startswith("extracted_batch_") and f.endswith(".json")
    ])

    if not batch_files:
        logger.error(
            "Không tìm thấy file extracted_batch_*.json trong thư mục data/\n"
            f"  Nội dung data/: {os.listdir(DATA_DIR) if os.path.exists(DATA_DIR) else 'KHÔNG TỒN TẠI'}"
        )
        sys.exit(1)

    for filename in batch_files:
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                rules = json.load(f)
                if isinstance(rules, list):
                    all_rules.extend(rules)
                    logger.debug(f"  {filename}: {len(rules)} rules")
                else:
                    logger.warning(f"  {filename}: format không hợp lệ, bỏ qua")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"  {filename}: lỗi đọc file — {e}, bỏ qua")

    logger.info(f"Tổng rules từ {len(batch_files)} batch files: {len(all_rules)}")

    if len(all_rules) == 0:
        logger.error("Không có rule nào được extract — kiểm tra lại các bước extract-batch")
        sys.exit(1)

    # Normalize
    run_id = os.getenv("GITHUB_RUN_ID", datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    builder = JsonBuilder()
    final_json = builder.build(all_rules, run_id=run_id)

    # Lưu local
    local_path = os.path.join(DATA_DIR, "biology_rules_final.json")
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    total_rules = final_json["metadata"]["total_rules"]
    logger.info(f"JSON master đã lưu: {total_rules} rules → {local_path}")

    # Upload MongoDB
    if not settings.MONGODB_URI:
        logger.warning("MONGODB_URI không được set — bỏ qua upload MongoDB")
        return

    try:
        uploader = MongoUploader()

        # 1. Upsert snapshot master (1 document tổng)
        ok = uploader.upsert_snapshot(final_json)
        if ok:
            snap_count = uploader.get_snapshot_rule_count()
            logger.info(f"Snapshot MongoDB: {snap_count} rules tổng tích lũy")

        # 2. Upsert individual rules (để tìm kiếm nhanh)
        upserted = uploader.upsert_rules(final_json)
        total_in_db = uploader.get_rule_count()
        logger.info(f"biology_rules collection: {upserted} upserted, {total_in_db} tổng")

        uploader.close()

    except Exception as e:
        logger.error(f"MongoDB upload thất bại: {e}")
        logger.info("File JSON local vẫn sẵn sàng tại: " + local_path)
        # Không exit(1) để artifact vẫn được upload


# ============================================================
# TIỆN ÍCH: Kiểm tra tổng số batches cần thiết
# ============================================================

def cmd_count_batches():
    """In số batch cần thiết dựa trên dữ liệu raw đã scrape."""
    all_articles = _load_all_raw()
    batch_size = settings.ARTICLES_PER_BATCH
    n_batches = (len(all_articles) + batch_size - 1) // batch_size
    print(f"TOTAL_ARTICLES={len(all_articles)}")
    print(f"BATCH_SIZE={batch_size}")
    print(f"N_BATCHES={n_batches}")
    print(f"BATCH_IDS=0..{n_batches-1}")


# ============================================================
# ENTRY POINT
# ============================================================

USAGE = """
Cách dùng:
  python main.py --scrape <source>         Cào dữ liệu (orions_arm | spec_evo | project_rho)
  python main.py --extract-batch <id>      Xử lý batch LLM (id = 0, 1, 2, ...)
  python main.py --finalize                Gộp → normalize → upload MongoDB
  python main.py --count-batches           Kiểm tra số batches cần thiết
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--scrape":
        if len(sys.argv) < 3:
            logger.error("Thiếu tên nguồn. Ví dụ: python main.py --scrape orions_arm")
            sys.exit(1)
        cmd_scrape(sys.argv[2])

    elif cmd == "--scrape-only":
        # Backward compat với workflow cũ
        if len(sys.argv) < 3:
            sys.exit(1)
        cmd_scrape(sys.argv[2])

    elif cmd == "--extract-batch":
        if len(sys.argv) < 3:
            logger.error("Thiếu batch ID. Ví dụ: python main.py --extract-batch 0")
            sys.exit(1)
        cmd_extract_batch(int(sys.argv[2]))

    elif cmd == "--finalize":
        cmd_finalize()

    elif cmd == "--count-batches":
        cmd_count_batches()

    else:
        logger.error(f"Lệnh không hợp lệ: {cmd}")
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
