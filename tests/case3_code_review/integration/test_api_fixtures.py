import asyncio

import pytest

from src.code_review.triage import run_triage_batch
from src.code_review.full_analysis import run_full_analysis_batch

pytestmark = pytest.mark.api

VULN_SQL = """<?php
$id = $_GET['id'];
$query = "SELECT * FROM users WHERE id = " . $id;
$result = mysqli_query($conn, $query);
?>"""

VULN_OVERFLOW = """#include <stdio.h>
#include <string.h>
void process(char *input) {
    char buf[64];
    strcpy(buf, input);
    printf("%s", buf);
}"""

VULN_SECRET = """API_KEY = "sk-1234567890abcdef"
DB_PASSWORD = "admin123"

def connect():
    return db.connect(password=DB_PASSWORD)"""

SECURE_CODE = """import hashlib

def hash_password(password: str) -> str:
    salt = hashlib.sha256(password.encode()).hexdigest()
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()"""

SECURE_JS = """function add(a, b) {
    return a + b;
}"""

TRIAGE_FIXTURES = [
    {"unique_id": 1001, "code": VULN_SQL},
    {"unique_id": 1002, "code": VULN_OVERFLOW},
    {"unique_id": 1003, "code": VULN_SECRET},
    {"unique_id": 1004, "code": SECURE_CODE},
    {"unique_id": 1005, "code": SECURE_JS},
]


class TestTriageIntegration:
    def test_vulnerable_snippets_detected(self):
        sem = asyncio.Semaphore(5)
        results = asyncio.run(run_triage_batch(TRIAGE_FIXTURES[:3], sem))
        verdicts = {r["unique_id"]: r["verdict"] for r in results}
        for uid in [1001, 1002, 1003]:
            assert verdicts[uid] in ("vulnerable", "uncertain"), \
                f"Expected vulnerable/uncertain for {uid}, got {verdicts[uid]}"

    def test_secure_snippets_not_flagged_vulnerable(self):
        sem = asyncio.Semaphore(5)
        results = asyncio.run(run_triage_batch(TRIAGE_FIXTURES[3:], sem))
        verdicts = {r["unique_id"]: r["verdict"] for r in results}
        for uid in [1004, 1005]:
            assert verdicts[uid] != "vulnerable", \
                f"Secure snippet {uid} incorrectly flagged as vulnerable"


FULL_ANALYSIS_FIXTURES = [
    {"unique_id": 2001, "code": VULN_SQL},
    {"unique_id": 2002, "code": VULN_OVERFLOW},
]


class TestFullAnalysisIntegration:
    def test_returns_cwe_and_fix(self):
        sem = asyncio.Semaphore(5)
        results = asyncio.run(run_full_analysis_batch(FULL_ANALYSIS_FIXTURES, sem))
        for r in results:
            if r["verdict"] == "vulnerable":
                assert r["cwe_id"].startswith("CWE-"), f"Invalid CWE ID: {r['cwe_id']}"
                assert len(r["fixed_code"]) > 0, "Missing fixed_code"
                assert len(r["mechanism"]) > 0, "Missing mechanism"
                assert len(r["justification"]) > 0, "Missing justification"
