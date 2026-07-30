# import os
# import json
# import re
# import requests

# AI_PIPE_BASE_URL = os.environ.get(
#     "AI_PIPE_BASE_URL",
#     "https://aipipe.org/geminiv1beta"
# )
# AI_PIPE_TOKEN = os.environ["AI_PIPE_TOKEN"]
# MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash-lite")


# def call_llm(messages, logger):
#     """
#     Gemini Native endpoint use karta hai.
#     OpenAI-style messages ko Gemini contents me convert karta hai.
#     """

#     logger.log("llm_call_start", messages=messages)

#     contents = []

#     for msg in messages:
#         role = "user"
#         if msg["role"] == "assistant":
#             role = "model"

#         contents.append(
#             {
#                 "role": role,
#                 "parts": [
#                     {
#                         "text": msg["content"]
#                     }
#                 ]
#             }
#         )

#     url = f"{AI_PIPE_BASE_URL}/models/{MODEL_NAME}:generateContent"

#     response = requests.post(
#         url,
#         headers={
#             "Authorization": f"Bearer {AI_PIPE_TOKEN}",
#             "Content-Type": "application/json",
#         },
#         json={
#             "contents": contents,
#             "generationConfig": {
#                 "temperature": 0
#             }
#         },
#         timeout=120,
#     )

#     response.raise_for_status()

#     data = response.json()

#     text = (
#         data["candidates"][0]
#         ["content"]["parts"][0]["text"]
#     )

#     logger.log("llm_call_end", response=text)

#     return text


# def extract_urls(text):
#     return re.findall(r"https?://\S+", text)


# def try_fetch_url(url, logger):
#     try:
#         r = requests.get(url, timeout=30)
#         r.raise_for_status()

#         logger.log(
#             "url_fetch_success",
#             url=url,
#             status=r.status_code,
#         )

#         return r.text

#     except Exception as e:

#         logger.log(
#             "url_fetch_failed",
#             url=url,
#             error=str(e),
#         )

#         return None


# def answer_question(conversation_history, logger):

#     logger.log(
#         "question_received",
#         history=conversation_history,
#     )

#     last_message = conversation_history[-1]

#     fetched = []

#     for url in extract_urls(last_message):
#         data = try_fetch_url(url, logger)
#         if data:
#             fetched.append(
#                 f"URL:\n{url}\n\nDATA:\n{data[:5000]}"
#             )

#     system_prompt = """
# You are a precise data analyst.

# Reply ONLY with the JSON value requested for the "answer".

# Never include markdown.

# Never include explanations.

# Never include log_url.

# Only output valid JSON.
# """

#     # user_prompt = "Conversation:\n\n"

#     # for m in conversation_history:
#     #     user_prompt += m + "\n\n"

#     # if fetched:
#     #     user_prompt += "\nFetched data:\n\n"
#     #     user_prompt += "\n\n".join(fetched)
#     user_prompt = "Conversation so far (each line is one message in order):\n\n"

#     for i, m in enumerate(conversation_history):
#         user_prompt += f"[{i+1}] {m}\n"

#     user_prompt += (
#         f"\n\nAnswer ONLY the LAST message above (message [{len(conversation_history)}]: "
#         f"\"{conversation_history[-1]}\"). Ignore earlier messages except as context if needed.\n"
#     )

#     if fetched:
#         user_prompt += "\nFetched data:\n\n"
#         user_prompt += "\n\n".join(fetched)

#     messages = [
#         {
#             "role": "system",
#             "content": system_prompt,
#         },
#         {
#             "role": "user",
#             "content": user_prompt,
#         },
#     ]

#     raw = call_llm(messages, logger).strip()

#     if raw.startswith("```"):
#         raw = raw.replace("```json", "")
#         raw = raw.replace("```", "")
#         raw = raw.strip()

#     try:
#         parsed = json.loads(raw)

#     except Exception:

#         logger.log(
#             "json_parse_failed",
#             raw=raw,
#         )

#         parsed = raw

#     # ---- FIX: agar LLM ne khud "answer" key ke andar wrap kar diya ho
#     # (e.g. {"answer": "Chennai"} ki jagah poora {"answer": {"answer": "Chennai"}}
#     # ban raha tha), to yahan usse unwrap kar denge taaki double-nesting na ho.
#     if (
#         isinstance(parsed, dict)
#         and "answer" in parsed
#         and len(parsed) <= 2
#     ):
#         parsed = parsed["answer"]

#     logger.log(
#         "answer_generated",
#         answer=parsed,
#     )

#     return parsed

import os
import json
import re
import io
import contextlib
import threading
import requests
import pandas as pd

AI_PIPE_BASE_URL = os.environ.get(
    "AI_PIPE_BASE_URL",
    "https://aipipe.org/geminiv1beta"
)
AI_PIPE_TOKEN = os.environ["AI_PIPE_TOKEN"]
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash-lite")

MAX_STEPS = 6           # agent loop me max kitni baar LLM<->code round-trip ho
CODE_TIMEOUT = 15       # seconds, ek code-run ke liye max allowed time


def call_llm(messages, logger):
    """Gemini Native endpoint use karta hai. OpenAI-style messages ko Gemini contents me convert karta hai."""
    logger.log("llm_call_start", messages=messages)

    contents = []
    for msg in messages:
        role = "user"
        if msg["role"] == "assistant":
            role = "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    url = f"{AI_PIPE_BASE_URL}/models/{MODEL_NAME}:generateContent"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {AI_PIPE_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "contents": contents,
            "generationConfig": {"temperature": 0}
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]

    logger.log("llm_call_end", response=text)
    return text


def extract_urls(text):
    return re.findall(r"https?://\S+", text)


def try_fetch_url(url, logger):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        logger.log("url_fetch_success", url=url, status=r.status_code)
        return r.text
    except Exception as e:
        logger.log("url_fetch_failed", url=url, error=str(e))
        return None


def run_python_code(code, available_data, logger, timeout=CODE_TIMEOUT):
    """
    Diye gaye Python/pandas code ko ek background thread me chalata hai (taaki hang na ho jaaye),
    print() output capture karke return karta hai. available_data dict ke keys
    (jaise 'data', 'data1', etc.) code ke andar variables ke roop me available hote hain.
    """
    logger.log("code_execution_start", code=code)

    output_buffer = io.StringIO()
    local_vars = dict(available_data)
    local_vars["pd"] = pd
    result_holder = {}

    def target():
        try:
            with contextlib.redirect_stdout(output_buffer):
                exec(code, {"pd": pd, "__builtins__": __builtins__}, local_vars)
            result_holder["success"] = True
        except Exception as e:
            result_holder["success"] = False
            result_holder["error"] = str(e)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        logger.log("code_execution_timeout", code=code)
        return f"ERROR: code execution timed out ({timeout}s limit)"

    stdout_text = output_buffer.getvalue()

    if not result_holder.get("success"):
        err = result_holder.get("error", "unknown error")
        logger.log("code_execution_error", error=err)
        return f"ERROR: {err}"

    logger.log("code_execution_success", stdout=stdout_text[:2000])
    return stdout_text if stdout_text.strip() else "(no output - use print() to show your result)"


def answer_question(conversation_history, logger):
    logger.log("question_received", history=conversation_history)
    last_message = conversation_history[-1]

    # Step 1: URLs fetch karo aur try karo CSV ke roop me parse karna
    fetched = {}
    for url in extract_urls(last_message):
        raw_text = try_fetch_url(url, logger)
        if raw_text is None:
            continue
        try:
            df = pd.read_csv(io.StringIO(raw_text))
            fetched[url] = df
            logger.log(
                "parsed_as_csv",
                url=url,
                shape=str(df.shape),
                columns=list(df.columns),
            )
        except Exception:
            fetched[url] = raw_text
            logger.log("kept_as_raw_text", url=url, length=len(raw_text))

    # Step 2: LLM ke liye data-description aur available_data (code exec ke liye) banao
    available_data = {}
    data_description = ""
    for i, (url, content) in enumerate(fetched.items()):
        var_name = "data" if len(fetched) == 1 else f"data{i+1}"
        available_data[var_name] = content
        if isinstance(content, pd.DataFrame):
            data_description += (
                f"\n`{var_name}` is a pandas DataFrame fetched from {url}\n"
                f"Shape: {content.shape}\n"
                f"Columns: {list(content.columns)}\n"
                f"First rows:\n{content.head(3).to_string()}\n"
            )
        else:
            data_description += (
                f"\n`{var_name}` is a raw text string fetched from {url} "
                f"(first 500 chars):\n{content[:500]}\n"
            )

    # Step 3: System prompt jo agent ko "run_code" / "final_answer" protocol sikhata hai
    system_prompt = f"""You are a precise data analyst agent with the ability to run Python code.

You will be given a conversation ending in a data-analysis question, and possibly
some pre-fetched data available as Python variables (pandas DataFrames or raw text).

{data_description if data_description else "No external data was fetched for this question."}

You work in a loop. On EACH turn, reply with EXACTLY ONE JSON object and nothing else:

To run code:
{{"action": "run_code", "code": "<python code using pandas as pd, MUST use print() to show results>"}}

To give your final answer:
{{"action": "final_answer", "answer": <the answer value, in the exact shape the question asks for>}}

Rules:
- Only use run_code when you need to compute/verify something using the available data variables.
- Your code MUST use print() - you only see printed output, not variable values.
- Do not fabricate data - use only the provided variables, or say you cannot answer.
- Once confident, respond with final_answer using ONLY the JSON value shape requested by the question.
- Never include "log_url" in your answer.
- Never use markdown formatting or code fences.
"""

    user_prompt = "Conversation so far (each line is one message in order):\n\n"
    for i, m in enumerate(conversation_history):
        user_prompt += f"[{i+1}] {m}\n"
    user_prompt += (
        f"\nAnswer ONLY the LAST message above (message [{len(conversation_history)}]): "
        f"\"{conversation_history[-1]}\". Ignore earlier messages except as context.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    final_answer = None

    for step in range(MAX_STEPS):
        raw = call_llm(messages, logger).strip()

        if raw.startswith("```"):
            raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(raw)
        except Exception:
            logger.log("json_parse_failed", raw=raw, step=step)
            final_answer = raw
            break

        action = parsed.get("action") if isinstance(parsed, dict) else None

        if action == "run_code":
            code = parsed.get("code", "")
            result = run_python_code(code, available_data, logger)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"Code output:\n{result}\n\nContinue: run more code, or give final_answer."
            })
            continue

        elif action == "final_answer":
            final_answer = parsed.get("answer")
            break

        else:
            # LLM protocol follow nahi kiya, lekin agar khud "answer" diya hai to use lo
            if isinstance(parsed, dict) and "answer" in parsed and len(parsed) <= 2:
                final_answer = parsed["answer"]
            else:
                final_answer = parsed
            break

    if final_answer is None:
        final_answer = {"error": "could not determine an answer within step limit"}

    logger.log("answer_generated", answer=final_answer)
    return final_answer