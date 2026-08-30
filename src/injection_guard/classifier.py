from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from transformers import pipeline

from .config import PipelineConfig

logger = logging.getLogger(__name__)


@dataclass
class RawPrediction:
    text: str
    p1: float
    raw_label: int


def build_classifier(config: PipelineConfig):
    return pipeline(
        "text-classification",
        model=config.model_id,
        truncation=True,
        max_length=config.max_length,
        top_k=None,
    )


def batch_predict(
    texts: list[str],
    pipe,
    batch_size: int = 32,
) -> list[RawPrediction]:
    results: list[RawPrediction] = []
    total = len(texts)
    num_batches = (total + batch_size - 1) // batch_size

    logger.info("Starting batch inference: %d texts, %d batches of %d", total, num_batches, batch_size)
    t_start = time.time()

    for batch_idx in range(num_batches):
        lo = batch_idx * batch_size
        hi = min(lo + batch_size, total)
        chunk = texts[lo:hi]

        raw_out = pipe(chunk, batch_size=batch_size, truncation=True, max_length=512)

        for text, scores in zip(chunk, raw_out):
            score_map = {s["label"]: s["score"] for s in scores}
            p_injection = score_map.get("INJECTION", score_map.get("LABEL_1", score_map.get(1, 0.0)))
            p_safe = score_map.get("SAFE", score_map.get("LABEL_0", score_map.get(0, 0.0)))
            p1 = p_injection / (p_safe + p_injection) if (p_safe + p_injection) > 0 else p_injection
            raw_label = 1 if p1 >= 0.5 else 0
            results.append(RawPrediction(text=text, p1=p1, raw_label=raw_label))

        elapsed = time.time() - t_start
        pct = hi / total * 100
        rate = hi / elapsed if elapsed > 0 else 0
        eta = (total - hi) / rate if rate > 0 else 0
        logger.info(
            "Batch %d/%d done (%d/%d rows, %.1f%%) — %.0f rows/s, ETA %ds",
            batch_idx + 1, num_batches, hi, total, pct, rate, eta,
        )

    logger.info("Batch inference complete: %d rows in %.1fs (%.0f rows/s)",
                total, time.time() - t_start, total / (time.time() - t_start))
    return results
