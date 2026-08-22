import logging

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


PROMPT_TEMPLATE = """Answer the question using the context below. If the question has any relevance to the context, answer it. If the question can't be answered using the context, say "I don't know".

context = {context}
question = {question}
"""


@retry(
    stop=stop_after_attempt(settings.MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def generate_answer(question: str, context: str) -> str:
    """Call Gemini with retries on transient failures (rate limits, timeouts)."""
    prompt = PROMPT_TEMPLATE.format(context=context, question=question)
    client = get_client()
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
    )
    return response.text
