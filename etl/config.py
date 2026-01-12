import os
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# Core Foothill config
BASE_URL = os.getenv(
    "FOOTHILL_BASE_URL",
    "https://foothill.edu/schedule/"
)

DB = os.getenv("FOOTHILL_DB", "foothill.db")

QUARTER = os.getenv("FOOTHILL_QUARTER", "2026W")
DEPT = os.getenv("FOOTHILL_DEPT", "CS")

# Network / crawling behavior
USER_AGENT = os.getenv("ETL_USER_AGENT", "FoothillETL/1.0")
REQUEST_TIMEOUT = int(os.getenv("ETL_TIMEOUT", "30"))

# Safety / future-proofing
MAX_PAGES = int(os.getenv("ETL_MAX_PAGES", "50"))
