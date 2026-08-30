import logging
import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .client import make_async_client
from .config import TRIAGE_CONCURRENCY, TRIAGE_MODEL, MAX_JSON_RETRIES
from .json_parser import parse_triage_response
from .prompts import TRIAGE_INSTRUCTIONS

log = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(MAX_JSON_RETRIES + 1),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((openai.RateLimitError, openai.InternalServerError)),
    reraise=True,
)
async def triage_async(client, code: str) -> dict:
    response = await client.responses.create(
        model=TRIAGE_MODEL,
        temperature=0.0,
        instructions=TRIAGE_INSTRUCTIONS,
        input=code,
        max_output_tokens=200,
    )
    text = response.output_text
    if not text or not text.strip():
        log.warning("EMPTY triage response, model=%s", TRIAGE_MODEL)
    return parse_triage_response(text)


async def run_triage_batch(items: list[dict], semaphore) -> list[dict]:
    import asyncio

    client = make_async_client()

    async def _process(item):
        async with semaphore:
            try:
                result = await triage_async(client, item["code"])
            except Exception:
                result = {"verdict": "uncertain", "parse_error": True}
            return {"unique_id": item["unique_id"], **result}

    tasks = [asyncio.create_task(_process(item)) for item in items]
    results = await asyncio.gather(*tasks)
    return list(results)
