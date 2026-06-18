import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# Cloudflare D1
D1_DATABASE_NAME = os.getenv("CLOUDFLARE_DATABASE_NAME", os.getenv("D1_DATABASE_NAME", "minor-testdb"))
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_DATABASE_ID = os.getenv("CLOUDFLARE_DATABASE_ID")

# Google OAuth
GOOGLE_CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
GOOGLE_TOKEN_FILE = BASE_DIR / "token.json"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Data and log directories
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Metadata files
REGISTRY_FILE = DATA_DIR / "sheet_registry.json"
SCHEMA_HISTORY_FILE = DATA_DIR / "schema_history.json"
SYNC_HISTORY_FILE = DATA_DIR / "sync_history.json"
QUERY_LOG_FILE = LOGS_DIR / "query_log.jsonl"

# LangChain / Groq settings
GROQ_MODEL = "llama-3.3-70b-versatile"
LLM_MAX_TOKENS = 300
LLM_TEMPERATURE = 0