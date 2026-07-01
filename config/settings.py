import os

# ============================================================
# GEMINI API KEYS - Xoay vòng round-robin
# ============================================================
GEMINI_KEYS = [k for k in [
    os.getenv("GEMINI_KEY_1", ""),
    os.getenv("GEMINI_KEY_2", ""),
    os.getenv("GEMINI_KEY_3", ""),
    os.getenv("GEMINI_KEY_4", ""),
    os.getenv("GEMINI_KEY_5", ""),
    os.getenv("GEMINI_KEY_6", ""),
    os.getenv("GEMINI_KEY_7", ""),
] if k.strip()]

GEMINI_MODEL = "gemini-2.5-flash"

# ============================================================
# MONGODB ATLAS
# ============================================================
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = "world_lore_db"
MONGODB_COLLECTION_RULES = "biology_rules"
MONGODB_COLLECTION_SNAPSHOT = "harvest_snapshot"
MONGODB_COLLECTION_STATE = "harvest_state"

# ============================================================
# SCRAPE SOURCES - ĐÃ SỬA THEO DEBUG RADAR
# ============================================================

# Orion's Arm: Site đã chuyển sang CMS mới (SPA), cần Playwright
ORIONS_ARM_BASE = "https://www.orionsarm.com"
ORIONS_ARM_ENCYCLOPEDIA = "https://www.orionsarm.com/encyclopedia"

# Speculative Evolution: Fandom API VẪN HOẠT ĐỘNG (đã xác nhận qua debug)
SPEC_EVO_API = "https://speculativeevolution.fandom.com/api.php"
SPEC_EVO_CATEGORIES = [
    "Species",
    "Creatures",
    "Organisms",
    "Animals",
    "Plants",
    "Alien_life",
    "Biology",
    "Ecosystems",
]

# Project Rho: ĐÃ SỬA .html sang .php (đã xác nhận qua debug)
PROJECT_RHO_BASE = "https://www.projectrho.com/public_html/rocket/"
PROJECT_RHO_PAGES = [
    "aliens.php",
    "alienbiology.php",
    "exoticbiology.php",
    "nonhuman.php",
]

# ============================================================
# SCRAPE SETTINGS
# ============================================================
REQUEST_DELAY_SECONDS = 1.5
MAX_ARTICLES_PER_CATEGORY = 200
MAX_ARTICLES_TOTAL = 1500

# ============================================================
# BATCH / RATE LIMIT
# ============================================================
ARTICLES_PER_BATCH = 15
DELAY_BETWEEN_CALLS_SEC = 4.0
RETRY_WAIT_SEC = 60

# ============================================================
# QUALITY / OUTPUT
# ============================================================
MIN_QUALITY_SCORE = 0.55
MAX_FINAL_RULES = 500

# ============================================================
# SNAPSHOT KEY trong MongoDB
# ============================================================
SNAPSHOT_DOC_ID = "world_lore_master"

# ============================================================
# PLAYWRIGHT SETTINGS (cho Orion's Arm)
# ============================================================
PLAYWRIGHT_TIMEOUT = 30000
PLAYWRIGHT_HEADLESS = True
