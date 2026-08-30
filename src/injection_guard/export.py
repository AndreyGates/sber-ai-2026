from __future__ import annotations

from pathlib import Path

import pandas as pd

from .policy import Decision


def build_results_table(
    texts: list[str],
    predictions: list,
    decisions: list[Decision],
    rationales: list[str],
) -> pd.DataFrame:
    rows = []
    for text, pred, dec, rationale in zip(texts, predictions, decisions, rationales):
        rows.append({
            "запрос": text,
            "присвоенный класс": dec.assigned_class,
            "рекомендуемое решение": dec.decision,
            "краткое обоснование": rationale,
        })
    return pd.DataFrame(rows)


def export_xlsx(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False, engine="openpyxl")
    return path


def validate_table(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    required_cols = {"запрос", "присвоенный класс", "рекомендуемое решение", "краткое обоснование"}
    missing = required_cols - set(df.columns)
    if missing:
        errors.append(f"missing columns: {missing}")

    valid_classes = {"safe", "injection and malicious"}
    if "присвоенный класс" in df.columns:
        bad_classes = df[~df["присвоенный класс"].isin(valid_classes)]
        if len(bad_classes) > 0:
            errors.append(f"{len(bad_classes)} rows with invalid class values")

    valid_decisions = {"пропустить", "заблокировать", "ручная проверка"}
    if "рекомендуемое решение" in df.columns:
        bad_decisions = df[~df["рекомендуемое решение"].isin(valid_decisions)]
        if len(bad_decisions) > 0:
            errors.append(f"{len(bad_decisions)} rows with invalid decision values")

    if "краткое обоснование" in df.columns and "рекомендуемое решение" in df.columns:
        review_rows = df[df["рекомендуемое решение"] == "ручная проверка"]
        empty_rationale = review_rows[review_rows["краткое обоснование"].isna() | (review_rows["краткое обоснование"] == "")]
        if len(empty_rationale) > 0:
            errors.append(f"{len(empty_rationale)} review rows with empty rationale")

    if "присвоенный класс" in df.columns:
        empty_class = df[df["присвоенный класс"].isna() | (df["присвоенный класс"] == "")]
        if len(empty_class) > 0:
            errors.append(f"{len(empty_class)} rows with empty class")

    return errors
