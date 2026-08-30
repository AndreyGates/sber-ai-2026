import openai

from .config import BASE_URL, YANDEX_CLOUD_API_KEY, YANDEX_CLOUD_FOLDER


def make_client() -> openai.OpenAI:
    return openai.OpenAI(
        api_key=YANDEX_CLOUD_API_KEY,
        base_url=BASE_URL,
        project=YANDEX_CLOUD_FOLDER,
    )


def make_async_client() -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(
        api_key=YANDEX_CLOUD_API_KEY,
        base_url=BASE_URL,
        project=YANDEX_CLOUD_FOLDER,
    )
