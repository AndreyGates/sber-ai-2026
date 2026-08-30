import asyncio
import json
import logging
import time
from pathlib import Path

from .config import OUTPUT_DIR, TRIAGE_CONCURRENCY, FULL_ANALYSIS_CONCURRENCY
from .data_loader import load_dataset
from .export import merge_and_export, validate_output
from .full_analysis import run_full_analysis_batch
from .triage import run_triage_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def run_pipeline(sample_size: int | None = None):
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Loading dataset...")
    dataset = load_dataset()
    if sample_size:
        dataset = dataset[:sample_size]
    log.info("Dataset loaded: %d rows", len(dataset))

    stage1_path = output_dir / "stage1_results.jsonl"
    stage2_path = output_dir / "stage2_results.jsonl"

    # Stage 1: Triage
    log.info("=== Stage 1: Triage (gpt-oss-20b) ===")
    t0 = time.monotonic()
    sem1 = asyncio.Semaphore(TRIAGE_CONCURRENCY)
    stage1_results = await run_triage_batch(dataset, sem1)
    elapsed1 = time.monotonic() - t0

    with open(stage1_path, "w", encoding="utf-8") as f:
        for r in stage1_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    counts = {}
    for r in stage1_results:
        v = r["verdict"]
        counts[v] = counts.get(v, 0) + 1
    log.info("Stage 1 done in %.1fs. Verdicts: %s", elapsed1, counts)

    # Stage 2: Full analysis on flagged items
    flagged = [r for r in stage1_results if r["verdict"] in ("vulnerable", "uncertain")]
    flagged_ids = {r["unique_id"] for r in flagged}
    flagged_items = [d for d in dataset if d["unique_id"] in flagged_ids]

    log.info("=== Stage 2: Full analysis (deepseek-v4-flash) on %d flagged items ===", len(flagged_items))
    t1 = time.monotonic()
    sem2 = asyncio.Semaphore(FULL_ANALYSIS_CONCURRENCY)
    stage2_results = await run_full_analysis_batch(flagged_items, sem2)
    elapsed2 = time.monotonic() - t1

    with open(stage2_path, "w", encoding="utf-8") as f:
        for r in stage2_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    s2_counts = {}
    for r in stage2_results:
        v = r["verdict"]
        s2_counts[v] = s2_counts.get(v, 0) + 1
    log.info("Stage 2 done in %.1fs. Verdicts: %s", elapsed2, s2_counts)

    # Merge and export
    log.info("=== Merging and exporting ===")
    df = merge_and_export(stage1_path, stage2_path, dataset, output_dir)
    errors = validate_output(df)
    if errors:
        log.warning("Validation errors: %s", errors)
    else:
        log.info("Validation passed")

    log.info("Total time: %.1fs. Output in %s", elapsed1 + elapsed2, output_dir)
    return df


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Code vulnerability review pipeline")
    parser.add_argument("--sample", type=int, default=None, help="Process only N rows (for testing)")
    args = parser.parse_args()
    asyncio.run(run_pipeline(sample_size=args.sample))


if __name__ == "__main__":
    main()
