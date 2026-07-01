import os

# ============================================================
# GEMINI API - KHÔNG CẦN NỮA (đã bỏ LLM)
# ============================================================
# GEMINI_KEY = os.getenv("GEMINI_KEY_1", "").strip()
# GEMINI_MODEL = "gemini-2.5-flash"

# ============================================================
# MONGODB ATLAS
# ============================================================
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DB_NAME = "world_lore_db"

# Collections
MONGODB_COLLECTION_KEYWORDS = "used_keywords"
MONGODB_COLLECTION_LINKS = "scraped_links"
MONGODB_COLLECTION_CONTENT = "raw_content"
MONGODB_COLLECTION_RULES = "biology_rules"
MONGODB_COLLECTION_RUNS = "run_logs"

# ============================================================
# SEARCH ENGINE - STARTPAGE
# ============================================================
SEARCH_ENGINE = "startpage"
SEARCH_URL = "https://www.startpage.com/do/dsearch"
MAX_RESULTS_PER_SEARCH = 20
SEARCH_DELAY_SECONDS = 2.0

# ============================================================
# PIPELINE SETTINGS
# ============================================================
LINKS_PER_RUN = 20
MIN_CONTENT_LENGTH = 500
MIN_BIOLOGY_KEYWORDS = 3

# ============================================================
# BIOLOGY KEYWORDS
# ============================================================
BIOLOGY_KEYWORDS = [
    "silicon", "carbon", "ammonia", "methane",
    "biochemistry", "organism", "metabolism",
    "solvent", "extremophile", "alternative life",
    "base element", "respiration", "photosynthesis",
    "chemosynthesis", "anaerobic", "extreme environment"
]

# ============================================================
# RUN SETTINGS
# ============================================================
RUN_TIMEOUT_MINUTES = 25
DELAY_BETWEEN_REQUESTS = 1.5
