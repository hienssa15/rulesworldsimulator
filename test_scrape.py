"""
Test Scraper - Kiểm tra từng nguồn trước khi lắp vào pipeline
Chỉ scrape, không dùng LLM, không dùng MongoDB
Output: File JSON + thống kê ra console
"""
import json
import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("test_scrape")


def test_orions_arm():
    """Test scrape Orion's Arm"""
    logger.info("=" * 60)
    logger.info("TEST: Orion's Arm")
    logger.info("=" * 60)
    
    try:
        from scrapers.orions_arm import OrionsArmScraper
        
        scraper = OrionsArmScraper()
        articles = scraper.scrape_all()
        
        logger.info(f"✅ Orion's Arm: Lấy được {len(articles)} bài")
        
        if articles:
            logger.info(f"  - Bài đầu tiên: {articles[0].get('title', 'N/A')}")
            logger.info(f"  - URL: {articles[0].get('url', 'N/A')}")
            logger.info(f"  - Độ dài content: {len(articles[0].get('content', ''))} ký tự")
        
        return articles
        
    except Exception as e:
        logger.error(f"❌ Orion's Arm lỗi: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_spec_evo():
    """Test scrape Speculative Evolution"""
    logger.info("=" * 60)
    logger.info("TEST: Speculative Evolution")
    logger.info("=" * 60)
    
    try:
        from scrapers.speculative_evo import SpeculativeEvoScraper
        
        scraper = SpeculativeEvoScraper()
        articles = scraper.scrape_all()
        
        logger.info(f"✅ Speculative Evolution: Lấy được {len(articles)} bài")
        
        if articles:
            logger.info(f"  - Bài đầu tiên: {articles[0].get('title', 'N/A')}")
            logger.info(f"  - URL: {articles[0].get('url', 'N/A')}")
            logger.info(f"  - Độ dài wikitext: {len(articles[0].get('wikitext', ''))} ký tự")
        
        return articles
        
    except Exception as e:
        logger.error(f"❌ Speculative Evolution lỗi: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_project_rho():
    """Test scrape Project Rho"""
    logger.info("=" * 60)
    logger.info("TEST: Project Rho")
    logger.info("=" * 60)
    
    try:
        from scrapers.project_rho import ProjectRhoScraper
        
        scraper = ProjectRhoScraper()
        articles = scraper.scrape_all()
        
        logger.info(f"✅ Project Rho: Lấy được {len(articles)} mục")
        
        if articles:
            logger.info(f"  - Mục đầu tiên: {articles[0].get('title', 'N/A')}")
            logger.info(f"  - URL: {articles[0].get('url', 'N/A')}")
            logger.info(f"  - Type: {articles[0].get('type', 'N/A')}")
        
        return articles
        
    except Exception as e:
        logger.error(f"❌ Project Rho lỗi: {e}")
        import traceback
        traceback.print_exc()
        return []


def save_results(results: dict, output_dir: str = "test_output"):
    """Lưu kết quả test ra file JSON"""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for source, articles in results.items():
        filename = f"{output_dir}/test_{source}_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Đã lưu {len(articles)} bài → {filename}")
    
    # Lưu summary
    summary = {
        "timestamp": timestamp,
        "sources": {
            source: {
                "count": len(articles),
                "first_title": articles[0].get("title", "N/A") if articles else None,
                "first_url": articles[0].get("url", "N/A") if articles else None,
            }
            for source, articles in results.items()
        }
    }
    
    summary_file = f"{output_dir}/test_summary_{timestamp}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    logger.info(f"💾 Summary → {summary_file}")
    return summary


def main():
    logger.info("🚀 BẮT ĐẦU TEST SCRAPE")
    logger.info("")
    
    # Parse arguments
    sources_to_test = sys.argv[1:] if len(sys.argv) > 1 else ["all"]
    
    results = {}
    
    if "all" in sources_to_test or "orions" in sources_to_test:
        results["orions_arm"] = test_orions_arm()
        logger.info("")
    
    if "all" in sources_to_test or "spec_evo" in sources_to_test:
        results["spec_evo"] = test_spec_evo()
        logger.info("")
    
    if "all" in sources_to_test or "project_rho" in sources_to_test:
        results["project_rho"] = test_project_rho()
        logger.info("")
    
    # Lưu kết quả
    summary = save_results(results)
    
    # In báo cáo tổng kết
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 BÁO CÁO TỔNG KẾT")
    logger.info("=" * 60)
    
    total = 0
    for source, data in summary["sources"].items():
        count = data["count"]
        total += count
        status = "✅" if count > 0 else "❌"
        logger.info(f"{status} {source}: {count} bài")
    
    logger.info(f"\n📈 TỔNG CỘNG: {total} bài từ {len(results)} nguồn")
    
    if total == 0:
        logger.error("⚠️  KHÔNG LẤY ĐƯỢC BÀI NÀO - Kiểm tra lại scraper!")
        sys.exit(1)
    else:
        logger.info("✅ TEST HOÀN TẤT - Có thể lắp vào pipeline")
        sys.exit(0)


if __name__ == "__main__":
    main()
