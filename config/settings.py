import os

# ============================================
# GEMINI API KEYS - Xoay vòng round-robin
# Dùng gemini-2.5-flash (free tier hiện tại)
# ============================================
GEMINI_KEYS = [k for k in [
    os.getenv("GEMINI_KEY_1", ""),
    os.getenv("GEMINI_KEY_2", ""),
    os.getenv("GEMINI_KEY_3", ""),
    os.getenv("GEMINI_KEY_4", ""),
    os.getenv("GEMINI_KEY_5", ""),
    os.getenv("GEMINI_KEY_6", ""),
    os.getenv("GEMINI_KEY_7", ""),
] if k.strip()]

# gemini-2.5-flash là model free tier ổn định nhất hiện tại
GEMINI_MODEL = "gemini-2.5-flash"

# ============================================
# MONGODB ATLAS
# ============================================
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = "world_lore_db"
MONGODB_COLLECTION_RULES = "biology_rules"
MONGODB_COLLECTION_SNAPSHOT = "harvest_snapshot"
MONGODB_COLLECTION_STATE = "harvest_state"

# ============================================
# SCRAPE SOURCES
# ============================================
ORIONS_ARM_API = "https://orionsarm.com/api.php"
ORIONS_ARM_CATEGORIES = [
    "Xenobiology",
    "Non-Carbon_Based_Life",
    "Silicon_Based_Life",
    "Exotic_Biology",
    "Biochemistry",
]

SPEC_EVO_API = "https://speculativeevolution.fandom.com/api.php"
SPEC_EVO_CATEGORIES = [
    "Species",
    "Ecosystems",
]

PROJECT_RHO_BASE = "http://www.projectrho.com/public_html/rocket/"
PROJECT_RHO_PAGES = [
    "aliens.html",
    "alienbiology.html",
    "exoticbiology.html",
    "nonhuman.html",
]

# ============================================
# SCRAPE SETTINGS
# ============================================
REQUEST_DELAY_SECONDS = 1.5
MAX_ARTICLES_PER_CATEGORY = 200
MAX_ARTICLES_TOTAL = 1500

# ============================================
# BATCH / RATE LIMIT
# Mỗi job GitHub Actions chạy tối đa 25 phút
# ARTICLES_PER_BATCH nhỏ để xoay key không bị 429
# ============================================
ARTICLES_PER_BATCH = 15          # số article mỗi batch LLM
DELAY_BETWEEN_CALLS_SEC = 4.0    # delay giữa 2 lần gọi Gemini
RETRY_WAIT_SEC = 60              # chờ khi tất cả key bị rate limit

# ============================================
# QUALITY / OUTPUT
# ============================================
MIN_QUALITY_SCORE = 0.55
MAX_FINAL_RULES = 500

# ============================================
# SNAPSHOT KEY trong MongoDB
# Toàn bộ dữ liệu gói vào 1 document duy nhất
# ============================================
SNAPSHOT_DOC_ID = "world_lore_master"
