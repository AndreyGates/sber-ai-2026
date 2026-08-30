import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

YANDEX_CLOUD_API_KEY = os.environ.get("YANDEX_CLOUD_API_KEY", "")
YANDEX_CLOUD_FOLDER = os.environ.get("YANDEX_CLOUD_FOLDER", "")

BASE_URL = "https://ai.api.cloud.yandex.net/v1"

TRIAGE_MODEL = f"gpt://{YANDEX_CLOUD_FOLDER}/qwen3-235b-a22b-fp8/latest"
FULL_ANALYSIS_MODEL = f"gpt://{YANDEX_CLOUD_FOLDER}/qwen3-235b-a22b-fp8/latest"

TRIAGE_CONCURRENCY = 10
FULL_ANALYSIS_CONCURRENCY = 10

MAX_JSON_RETRIES = 2
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_CSV = PROJECT_ROOT / "data" / "case_3.csv"
OUTPUT_DIR = PROJECT_ROOT / "output" / "case3"
CWE_DICT_PATH = PROJECT_ROOT / "src" / "code_review" / "cwe_dict.json"

# --- Sample run (100 rows, no retries, low concurrency) ---
SAMPLE_SIZE = 100
SAMPLE_TRIAGE_CONCURRENCY = 1
SAMPLE_FULL_ANALYSIS_CONCURRENCY = 1
SAMPLE_MAX_RETRIES = 0
SAMPLE_OUTPUT_DIR = PROJECT_ROOT / "output" / "case3-code-review-sample"
