"""
T1: CLASSIFY LINKS - Phân loại links với扩展 sources
Pattern Tinnhanh + Rulesworld sources
"""
import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class T1Classify:
    def __init__(self):
        # Mở rộng domains cho astrobiology
        self.domain_rules = {
            # Academic/Research - High priority
            "arxiv.org": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "nature.com": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "science.org": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "ncbi.nlm.nih.gov": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "pubmed.ncbi.nlm.nih.gov": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "researchgate.net": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "academia.edu": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "scholar.google.com": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "doi.org": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "springer.com": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "wiley.com": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "elsevier.com": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            "plos.org": {"label": "academic_paper", "scraper_type": "html_simple", "priority": 1},
            
            # Government/Space Agencies - High priority
            "nasa.gov": {"label": "government_research", "scraper_type": "html_simple", "priority": 1},
            "esa.int": {"label": "government_research", "scraper_type": "html_simple", "priority": 1},
            "jaxa.jp": {"label": "government_research", "scraper_type": "html_simple", "priority": 1},
            
            # Wikipedia - High priority
            "wikipedia.org": {"label": "wiki_article", "scraper_type": "html_simple", "priority": 1},
            
            # Science News/Magazines - Medium priority
            "scientificamerican.com": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            "space.com": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            "universetoday.com": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            "astrobio.net": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            "phys.org": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            "sciencedaily.com": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            "newscientist.com": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            "quantaMagazine.org": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            "wired.com": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            "theverge.com": {"label": "science_news", "scraper_type": "html_simple", "priority": 2},
            
            # Wiki/Fandom - Medium priority
            "fandom.com": {"label": "wiki_fandom", "scraper_type": "html_simple", "priority": 2},
            "wikia.com": {"label": "wiki_fandom", "scraper_type": "html_simple", "priority": 2},
            "wikidot.com": {"label": "wiki_fandom", "scraper_type": "html_simple", "priority": 2},
            
            # Community/Discussion - Medium-low priority
            "reddit.com": {"label": "community_discussion", "scraper_type": "reddit", "priority": 3},
            "stackexchange.com": {"label": "community_discussion", "scraper_type": "html_simple", "priority": 3},
            "quora.com": {"label": "community_discussion", "scraper_type": "html_simple", "priority": 3},
        }
        
        # Path-based rules
        self.path_rules = [
            (r"\.pdf$", "pdf_document", "pdf", 2),
            (r"/blog/", "blog_article", "html_simple", 2),
            (r"/article/", "blog_article", "html_simple", 2),
            (r"/news/", "science_news", "html_simple", 2),
            (r"/research/", "academic_paper", "html_simple", 1),
            (r"/paper/", "academic_paper", "html_simple", 1),
            (r"/publication/", "academic_paper", "html_simple", 1),
        ]

    def classify_link(self, url: str) -> dict:
        """Phân loại link dựa trên URL và domain"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Check domain rules first
        for domain_pattern, rule in self.domain_rules.items():
            if domain_pattern in domain:
                return {
                    "label": rule["label"],
                    "scraper_type": rule["scraper_type"],
                    "priority": rule["priority"],
                    "domain": domain
                }
        
        # Check path rules
        for pattern, label, scraper_type, priority in self.path_rules:
            if re.search(pattern, path):
                return {
                    "label": label,
                    "scraper_type": scraper_type,
                    "priority": priority,
                    "domain": domain
                }
        
        # Default
        return {
            "label": "general_article",
            "scraper_type": "html_simple",
            "priority": 4,
            "domain": domain
        }

    def classify_links(self, links: list[dict]) -> list[dict]:
        """Phân loại tất cả links"""
        logger.info("=" * 80)
        logger.info("🏷️  T1: CLASSIFY LINKS")
        logger.info("=" * 80)
        
        classified = []
        for link in links:
            classification = self.classify_link(link["url"])
            link.update(classification)
            classified.append(link)
            
            # Log ngắn gọn
            priority_icon = {1: "🔴", 2: "🟡", 3: "🟢", 4: "⚪"}.get(classification["priority"], "⚪")
            logger.info(f"   {priority_icon} {link['domain'][:30]:<30} → {classification['label']}")
        
        # Sắp xếp theo priority (1 = cao nhất)
        classified.sort(key=lambda x: x["priority"])
        
        # Thống kê
        labels = {}
        for link in classified:
            label = link["label"]
            labels[label] = labels.get(label, 0) + 1
        
        logger.info(f"\n📊 Thống kê:")
        for label, count in sorted(labels.items(), key=lambda x: -x[1]):
            logger.info(f"   {label}: {count}")
        
        return classified


def run_t1(links: list[dict]) -> list[dict]:
    """Entry point cho T1"""
    classifier = T1Classify()
    return classifier.classify_links(links)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [T1] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Test
    test_links = [
        {"url": "https://arxiv.org/abs/2301.12345"},
        {"url": "https://en.wikipedia.org/wiki/Astrobiology"},
        {"url": "https://www.reddit.com/r/astrobiology/comments/abc123"},
        {"url": "https://www.nasa.gov/mission/"},
        {"url": "https://example.com/random-page"},
    ]
    
    classified = run_t1(test_links)
    print(f"\n✅ Classified {len(classified)} links")
