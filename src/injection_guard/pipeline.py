from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from datasets import load_dataset

from .classifier import RawPrediction, batch_predict, build_classifier
from .config import PipelineConfig
from .export import build_results_table, export_xlsx, validate_table
from .heuristic import detect_heuristic_flags
from .policy import decide, generate_rationale

logger = logging.getLogger(__name__)


def load_splits(dataset_id: str, train_sample: int | None = None):
    ds = load_dataset(dataset_id)
    train = ds["train"]
    test = ds["test"]
    if train_sample and train_sample < len(train):
        train = train.select(range(train_sample))
    return train, test


def run_pipeline(
    config: PipelineConfig | None = None,
    output_dir: str | Path = "output/case2-injection",
) -> dict:
    if config is None:
        config = PipelineConfig()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading dataset %s...", config.dataset_id)
    _, test_split = load_splits(config.dataset_id)
    if config.test_sample and config.test_sample < len(test_split):
        test_split = test_split.select(range(config.test_sample))
    texts = list(test_split["text"])
    logger.info("Test split: %d rows", len(texts))

    logger.info("Loading model %s...", config.model_id)
    pipe = build_classifier(config)

    logger.info("Running batch inference (batch_size=%d, max_length=%d)...", config.batch_size, config.max_length)
    t0 = time.time()
    predictions = batch_predict(texts, pipe, batch_size=config.batch_size)
    elapsed = time.time() - t0
    logger.info("Inference done in %.1fs (%.0f rows/s)", elapsed, len(texts) / elapsed)

    raw_path = output_dir / "raw_predictions.jsonl"
    with open(raw_path, "w") as f:
        for pred in predictions:
            f.write(json.dumps({
                "text": pred.text,
                "p1": pred.p1,
                "raw_label": pred.raw_label,
            }, ensure_ascii=False) + "\n")
    logger.info("Raw predictions saved to %s", raw_path)

    logger.info("Applying heuristic layer + decision policy...")
    decisions = []
    rationales = []
    heuristic_hits = 0
    for pred in predictions:
        flags = detect_heuristic_flags(pred.text)
        if flags:
            heuristic_hits += 1
        dec = decide(pred.p1, flags, config)
        decisions.append(dec)
        rationales.append(generate_rationale(pred.p1, flags, dec))
    logger.info("Heuristic layer: %d/%d rows with flags (%.1f%%)",
                heuristic_hits, len(predictions), heuristic_hits / len(predictions) * 100)

    df = build_results_table(texts, predictions, decisions, rationales)

    errors = validate_table(df)
    if errors:
        logger.warning("Validation errors: %s", errors)
    else:
        logger.info("Table validation passed")

    xlsx_path = export_xlsx(df, output_dir / "case2_results.xlsx")
    logger.info("Results exported to %s", xlsx_path)

    n_pass = sum(1 for d in decisions if d.decision == "пропустить")
    n_block = sum(1 for d in decisions if d.decision == "заблокировать")
    n_review = sum(1 for d in decisions if d.decision == "ручная проверка")
    logger.info("Decision distribution: pass=%d, block=%d, review=%d", n_pass, n_block, n_review)

    return {
        "elapsed_seconds": elapsed,
        "rows": len(texts),
        "rows_per_second": len(texts) / elapsed,
        "xlsx_path": str(xlsx_path),
        "raw_path": str(raw_path),
        "config": {
            "t_low": config.t_low,
            "t_high": config.t_high,
            "batch_size": config.batch_size,
            "model_id": config.model_id,
        },
    }
