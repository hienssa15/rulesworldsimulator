import os

# ============================================================
# GEMINI API - Chỉ dùng 1 key để sinh từ khóa
# ============================================================
GEMINI_KEY = os.getenv("GEMINI_KEY_1", "").strip()
GEMINI_MODEL = "gemini-2.5-flash"

# ============================================================
# MONGODB ATLAS - ĐÃ SỬA: strip whitespace
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
# SEARCH ENGINE - STARTPAGE (đã test và xác nhận)
# ============================================================
SEARCH_ENGINE = "startpage"
SEARCH_URL = "https://www.startpage.com/do/dsearch"
MAX_RESULTS_PER_SEARCH = 20
SEARCH_DELAY_SECONDS = 2.0

# ============================================================
# PIPELINE SETTINGS
# ============================================================
LINKS_PER_RUN = 20              # 20 links/phiên
MIN_CONTENT_LENGTH = 500        # Ít nhất 500 ký tự
MIN_BIOLOGY_KEYWORDS = 3        # Ít nhất 3 từ khóa sinh học

# ============================================================
# BIOLOGY KEYWORDS (để validate content)
# ============================================================
BIOLOGY_KEYWORDS = [
    "silicon", "carbon", "ammonia", "methane",
    "biochemistry", "organism", "metabolism",
    "solvent", "extremophile", "alternative life",
    "base element", "respiration", "photosynthesis",
    "chemosynthesis", "anaerobic", "extreme environment"
]

# ============================================================
# TOPIC TREE (để LLM sinh từ khóa đa dạng)
# ============================================================
TOPIC_TREE = {
    "base_elements": ["silicon", "boron", "arsenic", "sulfur", "phosphorus"],
    "solvents": ["ammonia", "methane", "sulfuric acid", "hydrogen fluoride", "liquid nitrogen"],
    "environments": [
        "high pressure", "extreme cold", "extreme heat", "vacuum",
        "acidic", "alkaline", "radiation", "deep ocean", "volcanic"
    ],
    "metabolism": [
        "anaerobic", "chemosynthesis", "radiosynthesis", "methanogenesis",
        "sulfur metabolism", "iron metabolism"
    ]
}

# ============================================================
# RUN SETTINGS
# ============================================================
RUN_TIMEOUT_MINUTES = 25        # Giới hạn 25 phút/phiên
DELAY_BETWEEN_REQUESTS = 1.5    # Delay giữa các request
