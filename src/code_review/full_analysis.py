import logging
import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .client import make_async_client
from .config import FULL_ANALYSIS_MODEL, MAX_JSON_RETRIES, CWE_DICT_PATH
from .cwe_validator import validate_cwe_id
from .json_parser import parse_full_analysis_response
from .prompts import FULL_ANALYSIS_INSTRUCTIONS

log = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(MAX_JSON_RETRIES + 1),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((openai.RateLimitError, openai.InternalServerError)),
    reraise=True,
)
async def full_analysis_async(client, code: str) -> dict:
    response = await client.responses.create(
        model=FULL_ANALYSIS_MODEL,
        temperature=0.3,
        instructions=FULL_ANALYSIS_INSTRUCTIONS,
        input=code,
        max_output_tokens=2000,
    )
    text = response.output_text
    if not text or not text.strip():
        log.warning("EMPTY analysis response, model=%s", FULL_ANALYSIS_MODEL)
    return parse_full_analysis_response(text)


def validate_analysis_result(result: dict) -> dict:
    if result.get("parse_error"):
        return result

    cwe_id = result.get("cwe_id", "")
    if result["verdict"] == "vulnerable" and cwe_id:
        valid, reason = validate_cwe_id(cwe_id, CWE_DICT_PATH)
        if not valid:
            result["verdict"] = "uncertain"
            result["invalid_cwe_id"] = True
            result["cwe_invalid_reason"] = reason
    return result


async def run_full_analysis_batch(items: list[dict], semaphore) -> list[dict]:
    import asyncio

    client = make_async_client()

    async def _process(item):
        async with semaphore:
            try:
                result = await full_analysis_async(client, item["code"])
            except Exception:
                result = {
                    "verdict": "uncertain",
                    "cwe_id": "",
                    "mechanism": "",
                    "fixed_code": "",
                    "justification": "",
                    "parse_error": True,
                }
            result = validate_analysis_result(result)
            return {"unique_id": item["unique_id"], **result}

    tasks = [asyncio.create_task(_process(item)) for item in items]
    results = await asyncio.gather(*tasks)
    return list(results)
