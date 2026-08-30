"""Evaluator for case 2 — prompt-injection classification.

Compares model predictions against ground-truth labels from the
``jayavibhav/prompt-injection-safety`` dataset and reports accuracy,
precision / recall / F1, confusion matrix, zone distribution and
harmful-query analysis.

Usage:
    PYTHONPATH=src uv run python -m injection_guard.evaluate
    PYTHONPATH=src uv run python -m injection_guard.evaluate \\
        --predictions output/case2-injection/raw_predictions.jsonl \\
        --thresholds output/case2-injection/calibration_result.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

# ── defaults ────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_PREDICTIONS = _PROJECT_ROOT / "output" / "case2-injection" / "raw_predictions.jsonl"
_DEFAULT_THRESHOLDS = _PROJECT_ROOT / "output" / "case2-injection" / "calibration_result.json"
_DEFAULT_DATASET = "jayavibhav/prompt-injection-safety"


# ── data loading ────────────────────────────────────────────────────────────

def load_ground_truth(dataset_id: str = _DEFAULT_DATASET) -> tuple[list[int], list[str]]:
    """Load GT labels from HuggingFace.

    Returns:
        (raw_labels, texts) — raw_labels are ints (0/1/2), texts are the
        original prompt strings.
    """
    from datasets import load_dataset

    logger.info("Loading ground-truth dataset %s (test split) …", dataset_id)
    ds = load_dataset(dataset_id, split="test")

    raw_labels: list[int] = []
    texts: list[str] = []
    for row in ds:
        raw_labels.append(row["label"])
        texts.append(row["text"])

    dist = Counter(raw_labels)
    logger.info("GT loaded: %d rows, label distribution: %s", len(raw_labels), dict(dist))
    return raw_labels, texts


def load_predictions(pred_path: Path) -> tuple[list[int], list[float]]:
    """Load predictions from raw_predictions.jsonl.

    Returns:
        (raw_labels, p1_scores) — raw_labels are binary (0/1),
        p1_scores are the injection probabilities.
    """
    logger.info("Loading predictions from %s …", pred_path)
    raw_labels: list[int] = []
    p1_scores: list[float] = []
    with pred_path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            raw_labels.append(rec["raw_label"])
            p1_scores.append(rec["p1"])

    logger.info("Predictions loaded: %d rows", len(raw_labels))
    return raw_labels, p1_scores


def load_thresholds(thresholds_path: Path) -> dict:
    """Load calibrated thresholds from calibration_result.json.

    Falls back to config defaults if the file doesn't exist.
    """
    if thresholds_path.exists():
        logger.info("Loading calibrated thresholds from %s", thresholds_path)
        with thresholds_path.open(encoding="utf-8") as fh:
            return json.load(fh)
    else:
        from injection_guard.config import PipelineConfig
        cfg = PipelineConfig()
        logger.warning(
            "Thresholds file %s not found, using config defaults (t_low=%.2f, t_high=%.2f)",
            thresholds_path, cfg.t_low, cfg.t_high,
        )
        return {"t_low": cfg.t_low, "t_high": cfg.t_high}


# ── metrics ─────────────────────────────────────────────────────────────────

def compute_zone_distribution(
    p1_scores: list[float],
    t_low: float,
    t_high: float,
) -> dict:
    """Classify each prediction into a decision zone.

    Zones:
        safe     — p1 < t_low           → decision: пропустить
        review   — t_low ≤ p1 < t_high  → decision: ручная проверка
        block    — p1 ≥ t_high          → decision: заблокировать
    """
    safe = review = block = 0
    for p in p1_scores:
        if p < t_low:
            safe += 1
        elif p >= t_high:
            block += 1
        else:
            review += 1
    total = len(p1_scores)
    return {
        "safe": {"count": safe, "pct": safe / total * 100 if total else 0},
        "review": {"count": review, "pct": review / total * 100 if total else 0},
        "block": {"count": block, "pct": block / total * 100 if total else 0},
        "t_low": t_low,
        "t_high": t_high,
    }


def compute_harmful_analysis(
    gold_labels: list[int],
    p1_scores: list[float],
    t_low: float,
) -> dict:
    """Analyse how harmful (label=2) queries are distributed.

    Key question: what fraction of harmful queries end up in the
    *safe* zone (p1 < t_low), i.e. would be silently passed through?
    """
    harmful_indices = [i for i, l in enumerate(gold_labels) if l == 2]
    total_harmful = len(harmful_indices)
    if total_harmful == 0:
        return {"total_harmful": 0}

    leaked = sum(1 for i in harmful_indices if p1_scores[i] < t_low)
    caught_review = sum(1 for i in harmful_indices if t_low <= p1_scores[i] < 0.5)
    caught_block_review = sum(1 for i in harmful_indices if 0.5 <= p1_scores[i])
    blocked = sum(1 for i in harmful_indices if p1_scores[i] >= 0.5)

    return {
        "total_harmful": total_harmful,
        "leaked_safe": leaked,
        "leaked_safe_pct": leaked / total_harmful * 100,
        "caught_review_zone": caught_review,
        "caught_block_zone": caught_block_review,
        "blocked_at_05": blocked,
        "blocked_at_05_pct": blocked / total_harmful * 100,
    }


def compute_confusion_matrix(
    gold_labels: list[int],
    pred_labels: list[int],
) -> dict:
    """3×3 confusion matrix using raw labels (0/1/2 for GT, 0/1 for pred).

    Since the model only outputs 0/1, we map pred=0→0, pred=1→1 and
    GT label 2 is treated as a separate class.
    """
    from injection_guard.config import map_dataset_label, map_model_label

    # mapped labels
    gold_mapped = [map_dataset_label(l) for l in gold_labels]
    pred_mapped = [map_model_label(l) for l in pred_labels]

    classes = ["safe", "injection and malicious"]
    matrix: dict[str, dict[str, int]] = {g: {p: 0 for p in classes} for g in classes}
    for g, p in zip(gold_mapped, pred_mapped):
        matrix[g][p] += 1

    return {"classes": classes, "matrix": matrix}


def run_evaluation(
    gold_labels: list[int],
    pred_labels: list[int],
    p1_scores: list[float],
    thresholds: dict,
) -> dict:
    """Run the full evaluation pipeline."""
    from injection_guard.calibrate import compute_metrics

    t_low = thresholds["t_low"]
    t_high = thresholds["t_high"]

    # core metrics (uses map_dataset_label / map_model_label internally)
    metrics = compute_metrics(gold_labels, pred_labels)

    # confusion matrix
    confusion = compute_confusion_matrix(gold_labels, pred_labels)

    # zone distribution
    zones = compute_zone_distribution(p1_scores, t_low, t_high)

    # harmful analysis
    harmful = compute_harmful_analysis(gold_labels, p1_scores, t_low)

    return {
        "metrics": metrics,
        "confusion": confusion,
        "zones": zones,
        "harmful": harmful,
        "n_samples": len(gold_labels),
    }


# ── pretty-print ────────────────────────────────────────────────────────────

def print_report(results: dict, thresholds: dict) -> None:
    """Human-readable evaluation report."""
    w = 80
    print()
    print("=" * w)
    print("  CASE 2 — PROMPT INJECTION  EVALUATION REPORT")
    print("=" * w)

    m = results["metrics"]
    print(f"\n  Samples evaluated : {results['n_samples']}")
    print(f"  Thresholds        : t_low={thresholds['t_low']:.2f}, t_high={thresholds['t_high']:.2f}")

    print(f"\n  ── Binary classification metrics (injection = positive) ──")
    print(f"  {'Accuracy':>20s}: {m['accuracy']:.4f}")
    print(f"  {'Precision':>20s}: {m['precision']:.4f}")
    print(f"  {'Recall':>20s}: {m['recall']:.4f}")
    print(f"  {'F1':>20s}: {m['f1']:.4f}")
    print(f"  {'Harmful recall safe':>20s}: {m['harmful_recall_safe']:.4f}")

    # confusion matrix
    cm = results["confusion"]
    classes = cm["classes"]
    mat = cm["matrix"]
    print(f"\n  ── Confusion matrix (mapped labels) ──")
    header = f"  {'GT \\ Pred':>20s}" + "".join(f" {c:>22s}" for c in classes)
    print(header)
    for g in classes:
        row = f"  {g:>20s}" + "".join(f" {mat[g][p]:>22d}" for p in classes)
        print(row)

    # zone distribution
    z = results["zones"]
    print(f"\n  ── Zone distribution (t_low={z['t_low']:.2f}, t_high={z['t_high']:.2f}) ──")
    for zone_name in ("safe", "review", "block"):
        info = z[zone_name]
        print(f"  {zone_name:>10s}: {info['count']:>6d}  ({info['pct']:>5.1f}%)")

    # harmful analysis
    h = results["harmful"]
    if h["total_harmful"] > 0:
        print(f"\n  ── Harmful (label=2) analysis ──")
        print(f"  Total harmful queries  : {h['total_harmful']}")
        print(f"  Leaked (safe zone)     : {h['leaked_safe']} ({h['leaked_safe_pct']:.1f}%)")
        print(f"  Caught (review zone)   : {h['caught_review_zone']}")
        print(f"  Caught (block zone)    : {h['caught_block_zone']}")
        print(f"  Blocked (p1 ≥ 0.5)    : {h['blocked_at_05']} ({h['blocked_at_05_pct']:.1f}%)")

    print("\n" + "=" * w)


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate prompt-injection predictions against ground truth.",
    )
    p.add_argument(
        "--predictions",
        type=Path,
        default=_DEFAULT_PREDICTIONS,
        help="Path to raw_predictions.jsonl (default: %(default)s)",
    )
    p.add_argument(
        "--thresholds",
        type=Path,
        default=_DEFAULT_THRESHOLDS,
        help="Path to calibration_result.json (default: %(default)s)",
    )
    p.add_argument(
        "--dataset",
        type=str,
        default=_DEFAULT_DATASET,
        help="HuggingFace dataset id for ground truth (default: %(default)s)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    args = parse_args(argv)

    gold_labels, _texts = load_ground_truth(args.dataset)
    pred_labels, p1_scores = load_predictions(args.predictions)

    if len(gold_labels) != len(pred_labels):
        logger.error(
            "Size mismatch: GT has %d rows, predictions has %d",
            len(gold_labels), len(pred_labels),
        )
        sys.exit(1)

    thresholds = load_thresholds(args.thresholds)
    results = run_evaluation(gold_labels, pred_labels, p1_scores, thresholds)
    print_report(results, thresholds)


if __name__ == "__main__":
    main()
