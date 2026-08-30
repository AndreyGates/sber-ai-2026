import asyncio
import json
import logging
import time
from pathlib import Path

from .config import OUTPUT_DIR, FULL_ANALYSIS_CONCURRENCY
from .data_loader import load_dataset
from .export import merge_and_export, validate_output
from .full_analysis import run_full_analysis_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def run_stage2_only():
    output_dir = OUTPUT_DIR
    stage1_path = output_dir / "stage1_results.jsonl"
    stage2_path = output_dir / "stage2_results.jsonl"

    log.info("Loading stage 1 results from %s", stage1_path)
    stage1_results = []
    with open(stage1_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                stage1_results.append(json.loads(line))
    log.info("Stage 1 results: %d rows", len(stage1_results))

    flagged_ids = {r["unique_id"] for r in stage1_results if r["verdict"] in ("vulnerable", "uncertain")}
    log.info("Flagged for stage 2: %d items", len(flagged_ids))

    dataset = load_dataset()
    code_map = {r["unique_id"]: r["code"] for r in dataset}
    flagged_items = [{"unique_id": uid, "code": code_map[uid]} for uid in flagged_ids if uid in code_map]

    log.info("=== Stage 2: Full analysis (deepseek-v4-flash, concurrency=%d) on %d items ===",
             FULL_ANALYSIS_CONCURRENCY, len(flagged_items))

    t0 = time.monotonic()
    sem = asyncio.Semaphore(FULL_ANALYSIS_CONCURRENCY)
    stage2_results = await run_full_analysis_batch(flagged_items, sem)
    elapsed = time.monotonic() - t0

    with open(stage2_path, "w", encoding="utf-8") as f:
        for r in stage2_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    counts = {}
    for r in stage2_results:
        v = r["verdict"]
        counts[v] = counts.get(v, 0) + 1
    log.info("Stage 2 done in %.1fs. Verdicts: %s", elapsed, counts)

    log.info("=== Merging and exporting ===")
    df = merge_and_export(stage1_path, stage2_path, dataset, output_dir)
    errors = validate_output(df)
    if errors:
        log.warning("Validation errors: %s", errors)
    else:
        log.info("Validation passed")

    log.info("Output in %s", output_dir)
    return df


if __name__ == "__main__":
    asyncio.run(run_stage2_only())
