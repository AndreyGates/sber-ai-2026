from __future__ import annotations

import numpy as np

from .config import CLASS_INJECTION, CLASS_SAFE, map_dataset_label, map_model_label


def _binary_metrics(gold: list[str], pred: list[str], pos: str = CLASS_INJECTION) -> dict:
    tp = sum(1 for g, p in zip(gold, pred) if g == pos and p == pos)
    fp = sum(1 for g, p in zip(gold, pred) if g != pos and p == pos)
    fn = sum(1 for g, p in zip(gold, pred) if g == pos and p != pos)
    tn = sum(1 for g, p in zip(gold, pred) if g != pos and p != pos)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "accuracy": accuracy}


def compute_metrics(gold_labels: list[int], pred_labels: list[int]) -> dict:
    gold_mapped = [map_dataset_label(l) for l in gold_labels]
    pred_mapped = [map_model_label(l) for l in pred_labels]
    metrics = _binary_metrics(gold_mapped, pred_mapped)

    harmful_recall_safe = 0.0
    harmful_total = sum(1 for l in gold_labels if l == 2)
    if harmful_total > 0:
        harmful_leaked = sum(
            1 for g, p in zip(gold_labels, pred_labels)
            if g == 2 and map_model_label(p) == CLASS_SAFE
        )
        harmful_recall_safe = 1.0 - harmful_leaked / harmful_total
    metrics["harmful_recall_safe"] = harmful_recall_safe
    return metrics


def calibrate_thresholds(
    gold_labels: list[int],
    p1_scores: list[float],
) -> dict:
    gold_mapped = [map_dataset_label(l) for l in gold_labels]
    p1_arr = np.array(p1_scores)
    harmful_mask = np.array([l == 2 for l in gold_labels])
    total_harmful = int(harmful_mask.sum())

    best_t_low = 0.15
    best_t_high = 0.75
    best_score = -1.0

    for t_low_c in np.arange(0.05, 0.40, 0.05):
        for t_high_c in np.arange(0.55, 0.95, 0.05):
            pred_labels: list[str] = []
            for p in p1_arr:
                if p < t_low_c:
                    pred_labels.append(CLASS_SAFE)
                elif p >= t_high_c:
                    pred_labels.append(CLASS_INJECTION)
                else:
                    pred_labels.append(CLASS_INJECTION if p >= 0.5 else CLASS_SAFE)

            metrics = _binary_metrics(gold_mapped, pred_labels)

            safe_zone = p1_arr < t_low_c
            harmful_in_safe = int((harmful_mask & safe_zone).sum())
            recall_harmful = 1.0 - (harmful_in_safe / total_harmful) if total_harmful > 0 else 1.0

            score = 0.6 * recall_harmful + 0.4 * metrics["f1"]
            if score > best_score:
                best_score = score
                best_t_low = round(float(t_low_c), 2)
                best_t_high = round(float(t_high_c), 2)

    return {
        "t_low": best_t_low,
        "t_high": best_t_high,
        "calibration_score": round(best_score, 4),
    }
