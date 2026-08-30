"""Sample run: 100 rows, no retries, concurrency 1, non-reasoning models.

Demonstrates the pipeline on a representative subset of the dataset.
Output goes to output/case3-code-review-sample/.

Usage:
    uv run python -m src.code_review.run_sample
"""

import asyncio
import json
import logging
import time

from .client import make_async_client
from .config import (
    CWE_DICT_PATH,
    SAMPLE_FULL_ANALYSIS_CONCURRENCY,
    SAMPLE_OUTPUT_DIR,
    SAMPLE_SIZE,
    SAMPLE_TRIAGE_CONCURRENCY,
    TRIAGE_MODEL,
    FULL_ANALYSIS_MODEL,
)
from .cwe_validator import validate_cwe_id
from .data_loader import load_dataset
from .export import merge_and_export, validate_output
from .json_parser import parse_triage_response, parse_full_analysis_response
from .prompts import TRIAGE_INSTRUCTIONS, FULL_ANALYSIS_INSTRUCTIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


async def triage_no_retry(client, code: str) -> dict:
    response = await client.responses.create(
        model=TRIAGE_MODEL,
        temperature=0.0,
        instructions=TRIAGE_INSTRUCTIONS,
        input=code,
        max_output_tokens=200,
    )
    text = response.output_text
    if not text or not text.strip():
        log.warning("EMPTY triage response")
        return {"verdict": "uncertain", "parse_error": True}
    return parse_triage_response(text)


async def full_analysis_no_retry(client, code: str) -> dict:
    response = await client.responses.create(
        model=FULL_ANALYSIS_MODEL,
        temperature=0.3,
        instructions=FULL_ANALYSIS_INSTRUCTIONS,
        input=code,
        max_output_tokens=2000,
    )
    text = response.output_text
    if not text or not text.strip():
        log.warning("EMPTY analysis response")
        return {
            "verdict": "uncertain",
            "cwe_id": "",
            "mechanism": "",
            "fixed_code": "",
            "justification": "",
            "parse_error": True,
        }
    result = parse_full_analysis_response(text)

    cwe_id = result.get("cwe_id", "")
    if result["verdict"] == "vulnerable" and cwe_id:
        valid, reason = validate_cwe_id(cwe_id, CWE_DICT_PATH)
        if not valid:
            result["verdict"] = "uncertain"
            result["invalid_cwe_id"] = True
            result["cwe_invalid_reason"] = reason
    return result


async def run_batch(items, semaphore, process_fn):
    client = make_async_client()

    async def _process(item):
        async with semaphore:
            try:
                return await process_fn(client, item["code"])
            except Exception as e:
                log.warning("Error processing %s: %s", item["unique_id"], e)
                return {
                    "verdict": "uncertain",
                    "cwe_id": "",
                    "mechanism": "",
                    "fixed_code": "",
                    "justification": "",
                    "parse_error": True,
                }

    tasks = [asyncio.create_task(_process(item)) for item in items]
    return list(await asyncio.gather(*tasks))


async def run_sample_pipeline():
    output_dir = SAMPLE_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Loading dataset (sample=%d)...", SAMPLE_SIZE)
    dataset = load_dataset()[:SAMPLE_SIZE]
    log.info("Dataset sample: %d rows", len(dataset))

    stage1_path = output_dir / "stage1_results.jsonl"
    stage2_path = output_dir / "stage2_results.jsonl"

    # Stage 1: Triage
    log.info("=== Stage 1: Triage (qwen3-235b, concurrency=%d, no retry) ===",
             SAMPLE_TRIAGE_CONCURRENCY)
    t0 = time.monotonic()
    sem1 = asyncio.Semaphore(SAMPLE_TRIAGE_CONCURRENCY)
    stage1_raw = await run_batch(dataset, sem1, triage_no_retry)
    stage1_results = [
        {"unique_id": item["unique_id"], **result}
        for item, result in zip(dataset, stage1_raw)
    ]
    elapsed1 = time.monotonic() - t0

    with open(stage1_path, "w", encoding="utf-8") as f:
        for r in stage1_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    s1_counts = {}
    for r in stage1_results:
        v = r["verdict"]
        s1_counts[v] = s1_counts.get(v, 0) + 1
    log.info("Stage 1 done in %.1fs. Verdicts: %s", elapsed1, s1_counts)

    # Stage 2: Full analysis on flagged items
    flagged = [r for r in stage1_results if r["verdict"] in ("vulnerable", "uncertain")]
    flagged_ids = {r["unique_id"] for r in flagged}
    flagged_items = [d for d in dataset if d["unique_id"] in flagged_ids]

    log.info("=== Stage 2: Full analysis (qwen3-235b, concurrency=%d, no retry) on %d items ===",
             SAMPLE_FULL_ANALYSIS_CONCURRENCY, len(flagged_items))
    t1 = time.monotonic()
    sem2 = asyncio.Semaphore(SAMPLE_FULL_ANALYSIS_CONCURRENCY)
    stage2_raw = await run_batch(flagged_items, sem2, full_analysis_no_retry)
    stage2_results = [
        {"unique_id": item["unique_id"], **result}
        for item, result in zip(flagged_items, stage2_raw)
    ]
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
    asyncio.run(run_sample_pipeline())


if __name__ == "__main__":
    main()
