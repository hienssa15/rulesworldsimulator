"""
Debug Radar - Khảo sát địa hình 3 nguồn trước khi viết scraper
In ra status code + content preview cho từng URL
"""
import requests
import json
import sys
import time

# Danh sách URL cần thăm dò
URLS_TO_PROBE = {
    "Orion's Arm": [
        ("MediaWiki API (cũ)", "https://orionsarm.com/api.php?action=query&meta=siteinfo&format=json"),
        ("MediaWiki API www", "https://www.orionsarm.com/api.php?action=query&meta=siteinfo&format=json"),
        ("Wiki path", "https://orionsarm.com/wiki/api.php?action=query&meta=siteinfo&format=json"),
        ("Encyclopedia home", "https://www.orionsarm.com/encyclopedia"),
        ("Main site", "https://www.orionsarm.com/"),
        ("Sitemap", "https://www.orionsarm.com/sitemap.xml"),
    ],
    "Speculative Evolution": [
        ("Fandom API (cũ)", "https://speculativeevolution.fandom.com/api.php?action=query&meta=siteinfo&format=json"),
        ("Fandom home", "https://speculativeevolution.fandom.com/wiki/Main_Page"),
        ("Miraheze API (mới)", "https://speculativeevolution.miraheze.org/w/api.php?action=query&meta=siteinfo&format=json"),
        ("Miraheze home", "https://speculativeevolution.miraheze.org/wiki/Main_Page"),
        ("Miraheze Species cat", "https://speculativeevolution.miraheze.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:Species&cmlimit=5&format=json"),
    ],
    "Project Rho": [
        ("aliens.html (cũ)", "http://www.projectrho.com/public_html/rocket/aliens.html"),
        ("aliens.php (mới)", "http://www.projectrho.com/public_html/rocket/aliens.php"),
        ("HTTPS aliens.php", "https://www.projectrho.com/public_html/rocket/aliens.php"),
        ("HTTPS aliens.html", "https://www.projectrho.com/public_html/rocket/aliens.html"),
        ("Home", "https://www.projectrho.com/"),
    ],
}


def probe_url(name: str, url: str) -> dict:
    """Thăm dò 1 URL, trả về thông tin"""
    result = {"name": name, "url": url, "status": None, "content_type": None, "preview": "", "error": None}
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (research-bot/2.0)"}
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        result["status"] = resp.status_code
        result["content_type"] = resp.headers.get("content-type", "unknown")
        result["final_url"] = resp.url
        
        # Preview: 300 chars đầu
        text = resp.text[:300].replace("\n", " ").replace("\r", " ")
        result["preview"] = text
        
        # Nếu là JSON, parse thử
        if "json" in result["content_type"].lower():
            try:
                data = resp.json()
                result["is_valid_json"] = True
                result["json_keys"] = list(data.keys()) if isinstance(data, dict) else "array"
            except:
                result["is_valid_json"] = False
        else:
            result["is_valid_json"] = False
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


def main():
    print("=" * 80)
    print("🔍 DEBUG RADAR - KHẢO SÁT ĐỊA HÌNH 3 NGUỒN")
    print("=" * 80)
    print()
    
    all_results = {}
    
    for source_name, urls in URLS_TO_PROBE.items():
        print(f"\n{'='*80}")
        print(f"📡 NGUỒN: {source_name}")
        print(f"{'='*80}")
        
        results = []
        for probe_name, url in urls:
            print(f"\n  🎯 {probe_name}")
            print(f"     URL: {url}")
            
            r = probe_url(probe_name, url)
            results.append(r)
            
            if r["error"]:
                print(f"     ❌ LỖI: {r['error']}")
            else:
                print(f"     Status: {r['status']}")
                print(f"     Content-Type: {r['content_type']}")
                if r.get("final_url") != url:
                    print(f"     Redirect → {r['final_url']}")
                print(f"     JSON hợp lệ: {r.get('is_valid_json', 'N/A')}")
                if r.get("json_keys"):
                    print(f"     JSON keys: {r['json_keys']}")
                print(f"     Preview: {r['preview'][:200]}...")
            
            time.sleep(1)  # Lịch sự
        
        all_results[source_name] = results
    
    # Lưu kết quả chi tiết
    output_file = "debug_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print(f"💾 Kết quả chi tiết đã lưu → {output_file}")
    print(f"{'='*80}")
    
    # Phân tích và đưa ra kết luận
    print(f"\n📋 KẾT LUẬN:")
    print("-" * 80)
    
    # Orion's Arm
    oa_results = all_results.get("Orion's Arm", [])
    working_oa = [r for r in oa_results if r.get("status") == 200]
    print(f"\n🔸 Orion's Arm: {len(working_oa)}/{len(oa_results)} URL hoạt động")
    for r in working_oa:
        print(f"    ✅ {r['name']}: {r['url']}")
    
    # Spec Evo
    se_results = all_results.get("Speculative Evolution", [])
    working_se = [r for r in se_results if r.get("status") == 200]
    print(f"\n🔸 Speculative Evolution: {len(working_se)}/{len(se_results)} URL hoạt động")
    for r in working_se:
        print(f"    ✅ {r['name']}: {r['url']}")
    
    # Project Rho
    pr_results = all_results.get("Project Rho", [])
    working_pr = [r for r in pr_results if r.get("status") == 200]
    print(f"\n🔸 Project Rho: {len(working_pr)}/{len(pr_results)} URL hoạt động")
    for r in working_pr:
        print(f"    ✅ {r['name']}: {r['url']}")


if __name__ == "__main__":
    main()
