import os
import json
import re
import requests

AI_PIPE_BASE_URL = os.environ.get(
    "AI_PIPE_BASE_URL",
    "https://aipipe.org/geminiv1beta"
)
AI_PIPE_TOKEN = os.environ["AI_PIPE_TOKEN"]
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash-lite")


def call_llm(messages, logger):
    """
    Gemini Native endpoint use karta hai.
    OpenAI-style messages ko Gemini contents me convert karta hai.
    """

    logger.log("llm_call_start", messages=messages)

    contents = []

    for msg in messages:
        role = "user"
        if msg["role"] == "assistant":
            role = "model"

        contents.append(
            {
                "role": role,
                "parts": [
                    {
                        "text": msg["content"]
                    }
                ]
            }
        )

    url = f"{AI_PIPE_BASE_URL}/models/{MODEL_NAME}:generateContent"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {AI_PIPE_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "contents": contents,
            "generationConfig": {
                "temperature": 0
            }
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    text = (
        data["candidates"][0]
        ["content"]["parts"][0]["text"]
    )

    logger.log("llm_call_end", response=text)

    return text


def extract_urls(text):
    return re.findall(r"https?://\S+", text)


def try_fetch_url(url, logger):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()

        logger.log(
            "url_fetch_success",
            url=url,
            status=r.status_code,
        )

        return r.text

    except Exception as e:

        logger.log(
            "url_fetch_failed",
            url=url,
            error=str(e),
        )

        return None


def answer_question(conversation_history, logger):

    logger.log(
        "question_received",
        history=conversation_history,
    )

    last_message = conversation_history[-1]

    fetched = []

    for url in extract_urls(last_message):
        data = try_fetch_url(url, logger)
        if data:
            fetched.append(
                f"URL:\n{url}\n\nDATA:\n{data[:5000]}"
            )

    system_prompt = """
You are a precise data analyst.

Reply ONLY with the JSON value requested for the "answer".

Never include markdown.

Never include explanations.

Never include log_url.

Only output valid JSON.
"""

    user_prompt = "Conversation:\n\n"

    for m in conversation_history:
        user_prompt += m + "\n\n"

    if fetched:
        user_prompt += "\nFetched data:\n\n"
        user_prompt += "\n\n".join(fetched)

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    raw = call_llm(messages, logger).strip()

    if raw.startswith("```"):
        raw = raw.replace("```json", "")
        raw = raw.replace("```", "")
        raw = raw.strip()

    try:
        parsed = json.loads(raw)

    except Exception:

        logger.log(
            "json_parse_failed",
            raw=raw,
        )

        parsed = raw

    logger.log(
        "answer_generated",
        answer=parsed,
    )

    return parsed