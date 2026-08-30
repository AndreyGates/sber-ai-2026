import json
from pathlib import Path

import pandas as pd

from .config import OUTPUT_DIR


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def merge_and_export(
    stage1_path: Path,
    stage2_path: Path,
    dataset: list[dict],
    output_dir: Path = OUTPUT_DIR,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)

    stage1 = {r["unique_id"]: r for r in load_jsonl(stage1_path)}
    stage2 = {r["unique_id"]: r for r in load_jsonl(stage2_path)}

    code_map = {r["unique_id"]: r["code"] for r in dataset}

    rows = []
    for uid in sorted(stage1.keys()):
        s1 = stage1[uid]
        verdict = s1["verdict"]
        s2 = stage2.get(uid, {})

        if verdict == "secure" and not s2:
            rows.append({
                "unique_id": uid,
                "code": code_map.get(uid, ""),
                "verdict": "secure",
                "cwe_id": "",
                "mechanism": "",
                "fixed_code": "",
                "justification": "",
            })
        else:
            rows.append({
                "unique_id": uid,
                "code": code_map.get(uid, ""),
                "verdict": s2.get("verdict", verdict),
                "cwe_id": s2.get("cwe_id", ""),
                "mechanism": s2.get("mechanism", ""),
                "fixed_code": s2.get("fixed_code", ""),
                "justification": s2.get("justification", ""),
            })

    df = pd.DataFrame(rows)

    xlsx_path = output_dir / "case3_results.xlsx"
    csv_path = output_dir / "case3_results.csv"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    df.to_csv(csv_path, index=False, encoding="utf-8")

    return df


def validate_output(df: pd.DataFrame) -> list[str]:
    errors = []
    valid_verdicts = {"vulnerable", "secure", "uncertain"}

    if df["verdict"].isna().any():
        errors.append("Found rows with empty verdict")

    invalid = set(df["verdict"].unique()) - valid_verdicts
    if invalid:
        errors.append(f"Invalid verdicts: {invalid}")

    vuln = df[df["verdict"] == "vulnerable"]
    empty_cwe = vuln[vuln["cwe_id"].isna() | (vuln["cwe_id"] == "")]
    if len(empty_cwe) > 0:
        errors.append(f"{len(empty_cwe)} vulnerable rows with empty CWE ID")

    empty_fix = vuln[vuln["fixed_code"].isna() | (vuln["fixed_code"] == "")]
    if len(empty_fix) > 0:
        errors.append(f"{len(empty_fix)} vulnerable rows with empty fixed_code")

    return errors
