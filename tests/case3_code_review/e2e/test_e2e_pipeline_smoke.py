import asyncio

import pytest

from src.code_review.triage import run_triage_batch
from src.code_review.full_analysis import run_full_analysis_batch
from src.code_review.export import merge_and_export, validate_output

pytestmark = pytest.mark.api

SMALL_SAMPLE = [
    {"unique_id": 9001, "code": 'query = "SELECT * FROM users WHERE id = " + user_input'},
    {"unique_id": 9002, "code": "def add(a, b):\n    return a + b"},
    {"unique_id": 9003, "code": '#include <stdlib.h>\nvoid f() { char b[4]; strcpy(b, "longstring"); }'},
    {"unique_id": 9004, "code": "import os\nos.system('rm -rf ' + user_input)"},
    {"unique_id": 9005, "code": "x = 42\nprint(x)"},
]


class TestPipelineSmoke:
    def test_full_pipeline_on_small_sample(self, tmp_path):
        sem1 = asyncio.Semaphore(5)
        stage1 = asyncio.run(run_triage_batch(SMALL_SAMPLE, sem1))

        assert len(stage1) == 5
        for r in stage1:
            assert r["verdict"] in ("vulnerable", "secure", "uncertain")

        flagged_ids = {r["unique_id"] for r in stage1 if r["verdict"] in ("vulnerable", "uncertain")}
        flagged_items = [d for d in SMALL_SAMPLE if d["unique_id"] in flagged_ids]

        stage2 = []
        if flagged_items:
            sem2 = asyncio.Semaphore(5)
            stage2 = asyncio.run(run_full_analysis_batch(flagged_items, sem2))

        import json
        s1_path = tmp_path / "s1.jsonl"
        s2_path = tmp_path / "s2.jsonl"
        with open(s1_path, "w") as f:
            for r in stage1:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(s2_path, "w") as f:
            for r in stage2:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        out_dir = tmp_path / "out"
        df = merge_and_export(s1_path, s2_path, SMALL_SAMPLE, out_dir)

        assert len(df) == 5
        assert set(df["verdict"].unique()).issubset({"vulnerable", "secure", "uncertain"})
        assert (out_dir / "case3_results.xlsx").exists()
        assert (out_dir / "case3_results.csv").exists()

        errors = validate_output(df)
        vuln_rows = df[df["verdict"] == "vulnerable"]
        for _, row in vuln_rows.iterrows():
            assert row["cwe_id"].startswith("CWE-"), f"Row {row['unique_id']}: invalid CWE"
