"""Evaluator for case 1 — PII anonymization.

Compares predicted entities (from audit.jsonl) against ground-truth spans
from the nvidia/Nemotron-PII dataset using document-level label counting.

Usage:
    PYTHONPATH=src uv run python -m pii.evaluate
    PYTHONPATH=src uv run python -m pii.evaluate --audit path/to/audit.jsonl
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

# ── defaults ────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_AUDIT = _PROJECT_ROOT / "output" / "case1-pii" / "stratified_1000" / "audit.jsonl"
_DEFAULT_DATASET = "nvidia/Nemotron-PII"


# ── parsing helpers ─────────────────────────────────────────────────────────

def _parse_spans(raw: str) -> list[dict]:
    """Parse the ``spans`` field from Nemotron-PII.

    99 999 / 100 000 rows are Python-literal strings (``ast.literal_eval``);
    the remaining row is a JSON string.  Try both.
    """
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        pass
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cannot parse spans: {exc}") from exc


# ── data loading ────────────────────────────────────────────────────────────

def load_ground_truth(dataset_id: str = _DEFAULT_DATASET) -> dict[str, list[dict]]:
    """Load GT spans grouped by UID.

    The dataset has duplicate UIDs (each UID appears exactly twice with
    different content).  We merge all spans for a UID into one list so that
    the evaluation covers every annotated entity.

    Returns:
        ``{uid: [span_dict, ...]}`` where each span has at least
        ``label``, ``start``, ``end``.
    """
    from datasets import load_dataset

    logger.info("Loading ground-truth dataset %s (test split) …", dataset_id)
    ds = load_dataset(dataset_id, split="test")

    gt: dict[str, list[dict]] = defaultdict(list)
    parse_errors = 0
    for row in ds:
        uid = row["uid"]
        try:
            spans = _parse_spans(row["spans"])
        except ValueError:
            parse_errors += 1
            continue
        gt[uid].extend(spans)

    logger.info(
        "GT loaded: %d unique UIDs, %d total spans, %d parse errors",
        len(gt),
        sum(len(v) for v in gt.values()),
        parse_errors,
    )
    return dict(gt)


def load_predictions(audit_path: Path) -> dict[str, list[dict]]:
    """Load predicted entities from audit.jsonl, keyed by doc_id (= uid)."""
    logger.info("Loading predictions from %s …", audit_path)
    preds: dict[str, list[dict]] = {}
    with audit_path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            doc_id = rec["doc_id"]
            preds[doc_id] = rec.get("entities", [])
    logger.info("Predictions loaded: %d documents", len(preds))
    return preds


# ── metrics ─────────────────────────────────────────────────────────────────

def _label_counts(entities: list[dict]) -> Counter:
    """Return lowercased label → count for a list of entity dicts."""
    c: Counter = Counter()
    for e in entities:
        c[e["label"].lower()] += 1
    return c


def compute_document_level_metrics(
    gt: dict[str, list[dict]],
    preds: dict[str, list[dict]],
) -> dict:
    """Per-document label-count matching.

    For each document *d* and each label *ℓ*:
        TP_ℓ += min(gt_count_dℓ, pred_count_dℓ)
        FP_ℓ += max(0, pred_count_dℓ − gt_count_dℓ)
        FN_ℓ += max(0, gt_count_dℓ − pred_count_dℓ)

    Returns a dict with overall and per-label precision / recall / F1.
    """
    # find common doc ids
    common_ids = sorted(set(gt) & set(preds))
    gt_only = set(gt) - set(preds)
    pred_only = set(preds) - set(gt)

    logger.info(
        "Matching documents: %d common, %d GT-only, %d pred-only",
        len(common_ids),
        len(gt_only),
        len(pred_only),
    )

    # accumulate per-label confusion
    label_tp: Counter = Counter()
    label_fp: Counter = Counter()
    label_fn: Counter = Counter()

    docs_matched = 0
    for doc_id in common_ids:
        gt_counts = _label_counts(gt[doc_id])
        pred_counts = _label_counts(preds[doc_id])
        all_labels = set(gt_counts) | set(pred_counts)
        for lbl in all_labels:
            g = gt_counts.get(lbl, 0)
            p = pred_counts.get(lbl, 0)
            tp = min(g, p)
            label_tp[lbl] += tp
            label_fp[lbl] += max(0, p - g)
            label_fn[lbl] += max(0, g - p)
        docs_matched += 1

    # overall (only matched documents — GT-only docs are out of scope)
    total_tp = sum(label_tp.values())
    total_fp = sum(label_fp.values())
    total_fn = sum(label_fn.values())

    overall_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    overall_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = (
        2 * overall_p * overall_r / (overall_p + overall_r)
        if (overall_p + overall_r) > 0
        else 0.0
    )

    # per-label
    all_labels = sorted(set(label_tp) | set(label_fp) | set(label_fn))
    per_label: dict[str, dict] = {}
    for lbl in all_labels:
        tp = label_tp[lbl]
        fp = label_fp[lbl]
        fn = label_fn[lbl]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        support = tp + fn  # total GT instances
        per_label[lbl] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": p, "recall": r, "f1": f1,
            "support": support,
        }

    return {
        "docs_matched": docs_matched,
        "docs_gt_only": len(gt_only),
        "docs_pred_only": len(pred_only),
        "overall_precision": overall_p,
        "overall_recall": overall_r,
        "overall_f1": overall_f1,
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "per_label": per_label,
    }


# ── pretty-print ────────────────────────────────────────────────────────────

def print_report(results: dict) -> None:
    """Human-readable evaluation report."""
    w = 90
    print()
    print("=" * w)
    print("  CASE 1 — PII ANONYMIZATION  EVALUATION REPORT")
    print("=" * w)

    print(f"\n  Documents matched : {results['docs_matched']}")
    print(f"  GT-only documents : {results['docs_gt_only']}")
    print(f"  Pred-only documents: {results['docs_pred_only']}")

    print(f"\n  {'Overall precision':>22s}: {results['overall_precision']:.4f}")
    print(f"  {'Overall recall':>22s}: {results['overall_recall']:.4f}")
    print(f"  {'Overall F1':>22s}: {results['overall_f1']:.4f}")

    print(f"\n  Confusion totals  —  TP: {results['total_tp']}  FP: {results['total_fp']}  FN: {results['total_fn']}")

    # per-label table — top N by support
    per_label = results["per_label"]
    sorted_labels = sorted(per_label.items(), key=lambda kv: kv[1]["support"], reverse=True)

    top_n = 15
    print(f"\n  Per-label metrics (top {top_n} by support, {len(per_label)} labels total):")
    print(f"  {'label':<35s} {'P':>7s} {'R':>7s} {'F1':>7s} {'TP':>6s} {'FP':>6s} {'FN':>6s} {'sup':>7s}")
    print("  " + "-" * 86)
    for lbl, m in sorted_labels[:top_n]:
        print(
            f"  {lbl:<35s} {m['precision']:>7.4f} {m['recall']:>7.4f} {m['f1']:>7.4f}"
            f" {m['tp']:>6d} {m['fp']:>6d} {m['fn']:>6d} {m['support']:>7d}"
        )

    # remaining labels summary
    if len(sorted_labels) > top_n:
        rest_tp = sum(m["tp"] for _, m in sorted_labels[top_n:])
        rest_fp = sum(m["fp"] for _, m in sorted_labels[top_n:])
        rest_fn = sum(m["fn"] for _, m in sorted_labels[top_n:])
        rest_sup = sum(m["support"] for _, m in sorted_labels[top_n:])
        rest_p = rest_tp / (rest_tp + rest_fp) if (rest_tp + rest_fp) > 0 else 0.0
        rest_r = rest_tp / (rest_tp + rest_fn) if (rest_tp + rest_fn) > 0 else 0.0
        rest_f1 = 2 * rest_p * rest_r / (rest_p + rest_r) if (rest_p + rest_r) > 0 else 0.0
        print(
            f"  {'(other ' + str(len(sorted_labels) - top_n) + ' labels)':<35s}"
            f" {rest_p:>7.4f} {rest_r:>7.4f} {rest_f1:>7.4f}"
            f" {rest_tp:>6d} {rest_fp:>6d} {rest_fn:>6d} {rest_sup:>7d}"
        )

    print("\n" + "=" * w)


# ── CLI ─────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Evaluate PII anonymization predictions against Nemotron-PII ground truth.",
    )
    p.add_argument(
        "--audit",
        type=Path,
        default=_DEFAULT_AUDIT,
        help="Path to audit.jsonl with predicted entities (default: %(default)s)",
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

    gt = load_ground_truth(args.dataset)
    preds = load_predictions(args.audit)
    results = compute_document_level_metrics(gt, preds)
    print_report(results)


if __name__ == "__main__":
    main()
