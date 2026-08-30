"""CLI entry point for the PII anonymization pipeline."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from pii.config import PipelineConfig
from pii.dataset import load_nemotron_pii, save_jsonl
from pii.export import export_json, export_jsonl, export_xlsx
from pii.pipeline import PIIPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="PII Anonymization Pipeline")
    parser.add_argument("--input", type=str, help="Path to input JSONL file (optional, loads from HF if omitted)")
    parser.add_argument("--output-dir", type=str, default="output/case1-pii-anonymization", help="Output directory")
    parser.add_argument("--max-samples", type=int, default=None, help="Max documents to process")
    parser.add_argument("--stratify-by", type=str, default=None, help="Stratify sample by field (e.g. domain)")
    parser.add_argument("--split", type=str, default="test", help="Dataset split")
    parser.add_argument("--device", type=str, default="auto", help="Device: auto/cpu/cuda")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--min-score", type=float, default=0.5)
    parser.add_argument("--high-confidence", type=float, default=0.85)
    parser.add_argument("--no-audit", action="store_true", help="Skip audit artifact generation")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = PipelineConfig(
        device=args.device,
        batch_size=args.batch_size,
        min_score=args.min_score,
        high_confidence_threshold=args.high_confidence,
    )

    pipeline = PIIPipeline(config)
    pipeline.load_model()

    if args.input:
        from pii.dataset import load_from_jsonl
        documents = load_from_jsonl(args.input)
    else:
        documents = load_nemotron_pii(
            split=args.split,
            max_samples=args.max_samples,
            stratify_by=args.stratify_by,
        )

    if args.max_samples:
        documents = documents[:args.max_samples]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.info("Processing %d documents", len(documents))

    start_time = time.time()

    config_with_original = PipelineConfig(
        device=config.device,
        batch_size=config.batch_size,
        min_score=config.min_score,
        high_confidence_threshold=config.high_confidence_threshold,
        include_original=True,
    )
    pipeline.config = config_with_original

    results_with_original = pipeline.process_batch(documents)

    save_jsonl(results_with_original, output_dir / "audit.jsonl")
    logger.info("Audit artifact saved to %s", output_dir / "audit.jsonl")

    config_final = PipelineConfig(
        device=config.device,
        batch_size=config.batch_size,
        min_score=config.min_score,
        high_confidence_threshold=config.high_confidence_threshold,
        include_original=False,
    )
    pipeline.config = config_final

    results_final = pipeline.process_batch(documents)

    export_json(results_final, output_dir / "final.json")
    export_xlsx(results_final, output_dir / "final.xlsx")
    logger.info("Final artifacts saved to %s", output_dir)

    elapsed = time.time() - start_time
    logger.info("Processed %d documents in %.1f seconds", len(documents), elapsed)

    summary = {
        "total_documents": len(documents),
        "elapsed_seconds": round(elapsed, 1),
        "model": config.model_name,
        "model_version": config.model_revision,
        "min_score": config.min_score,
        "high_confidence_threshold": config.high_confidence_threshold,
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
