import os
import json
import requests
import pandas as pd
import io

# LLM call ke liye AI Pipe (ya OpenAI-compatible) endpoint use kar rahe hain
AI_PIPE_BASE_URL = os.environ.get("AI_PIPE_BASE_URL", "https://aipipe.org/openrouter/v1")
AI_PIPE_TOKEN = os.environ["AI_PIPE_TOKEN"]
MODEL_NAME = os.environ.get("MODEL_NAME", "google/gemini-2.0-flash")


def call_llm(messages, logger):
    """Ek simple chat-completion call, tool-calling ke bina (keep it robust)."""
    logger.log("llm_call_start", messages=messages)
    resp = requests.post(
        f"{AI_PIPE_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {AI_PIPE_TOKEN}"},
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0
        },
        timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    logger.log("llm_call_end", response=content)
    return content


def try_fetch_url(url, logger):
    """Agar question me koi URL ho to uska content fetch karo (CSV/JSON/HTML)."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        logger.log("fetched_url", url=url, status=r.status_code)
        return r.text
    except Exception as e:
        logger.log("fetch_url_failed", url=url, error=str(e))
        return None


def extract_urls(text):
    import re
    return re.findall(r'https?://\S+', text)


def answer_question(conversation_history, logger):
    """
    conversation_history: list of past user messages (strings), last one = current question.
    Returns: dict wala final JSON object jo bot reply karega (Python dict, not string).
    """
    last_message = conversation_history[-1]
    logger.log("received_question", text=last_message, history_len=len(conversation_history))

    # Step 1: agar message me URL hai to uska data fetch karo
    urls = extract_urls(last_message)
    fetched_data = {}
    for url in urls:
        content = try_fetch_url(url, logger)
        if content:
            fetched_data[url] = content[:5000]  # bahut bada data truncate kar do

    # Step 2: LLM ko poora context do - pichle messages + fetched data - aur
    # usse bolo ki sirf ek JSON object return kare, jaisa question ne manga hai
    system_prompt = (
        "You are a precise data analyst agent. You will be given a conversation "
        "(possibly multi-turn) ending in a data-analysis question. Some external "
        "data fetched from URLs mentioned in the question may be included. "
        "Answer using this data if relevant, or your own knowledge/computation. "
        "You MUST reply with ONLY the exact JSON object the question asks for - "
        "no markdown, no explanation, no extra text before or after. "
        "If the question specifies a JSON shape like {\"answer\": ..., \"log_url\": \"...\"}, "
        "output only the 'answer' portion's VALUE as your entire response in JSON form; "
        "do not include log_url yourself, that will be added separately."
    )

    user_content = "Conversation so far:\n"
    for i, msg in enumerate(conversation_history):
        user_content += f"[{i+1}] {msg}\n"

    if fetched_data:
        user_content += "\nFetched external data (truncated):\n"
        for url, content in fetched_data.items():
            user_content += f"--- {url} ---\n{content}\n"

    user_content += (
        "\nNow answer the LAST question above. Reply with ONLY the JSON value "
        "for the 'answer' key, matching the exact shape requested in the question."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    raw_reply = call_llm(messages, logger)

    # Step 3: LLM ka output clean karke JSON parse karo
    cleaned = raw_reply.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).strip()

    try:
        answer_value = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.log("json_parse_failed", raw=raw_reply)
        # fallback: raw string hi de do answer ke roop me
        answer_value = cleaned

    logger.log("final_answer", answer=answer_value)
    return answer_value