# from dotenv import load_dotenv
# load_dotenv()

# import os
# import json
# import logging
# from collections import defaultdict
# from telegram import Update
# from telegram.ext import Application, MessageHandler, ContextTypes, filters

# from agent import answer_question
# from logger import RunLogger

# logging.basicConfig(level=logging.INFO)
# logger_std = logging.getLogger(__name__)

# BOT_TOKEN = os.environ["BOT_TOKEN"]
# MAX_HISTORY = 5  # multi-turn ke liye kitne pichle messages yaad rakhne hain

# # chat_id -> list of message texts (simple in-memory store)
# chat_histories = defaultdict(list)


# async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     chat_id = update.message.chat_id
#     if not update.message or not update.message.text:
#          return

#     text = update.message.text.strip()

#     logger_std.info(f"Received from {chat_id}: {text}")

#     # history update karo
#     chat_histories[chat_id].append(text)
#     chat_histories[chat_id] = chat_histories[chat_id][-MAX_HISTORY:]

#     run_logger = RunLogger()

#     try:
#         answer_value = answer_question(chat_histories[chat_id], run_logger)
#     except Exception as e:
#         run_logger.log("error", error=str(e))
#         answer_value = "internal error"
#     log_url = run_logger.upload_and_get_url()

#     final_reply = {
#         "answer": answer_value,
#         "log_url": log_url
#     }

#     reply_text = json.dumps(
#     final_reply,
#     separators=(",", ":"),
#     ensure_ascii=False,
# )
#     logger_std.info(f"Replying: {reply_text}")

#     await update.message.reply_text(reply_text)


# def main():
#     app = Application.builder().token(BOT_TOKEN).build()
#     app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
#     logger_std.info("Bot started, polling...")
#     app.run_polling()


# if __name__ == "__main__":
#     main()

from dotenv import load_dotenv
load_dotenv()

import os
import json
import logging
import asyncio
from collections import defaultdict

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, FileResponse
import uvicorn

from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

from agent import answer_question
from logger import RunLogger, RUN_LOG_PATH

logging.basicConfig(level=logging.INFO)
logger_std = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
MAX_HISTORY = 5
chat_histories = defaultdict(list)

# ---------- Telegram handlers ----------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text
    logger_std.info(f"Received from {chat_id}: {text}")

    chat_histories[chat_id].append(text)
    chat_histories[chat_id] = chat_histories[chat_id][-MAX_HISTORY:]

    run_logger = RunLogger()
    try:
        answer_value = answer_question(chat_histories[chat_id], run_logger)
    except Exception as e:
        run_logger.log("error", error=str(e))
        answer_value = {"error": "failed to compute answer"}

    log_url = run_logger.upload_and_get_url()
    final_reply = {"answer": answer_value, "log_url": log_url}
    reply_text = json.dumps(final_reply)
    logger_std.info(f"Replying: {reply_text}")
    await update.message.reply_text(reply_text)


# ---------- FastAPI app ----------

app = FastAPI()


@app.get("/health")
async def health():
    return PlainTextResponse("OK")


@app.get("/run.jsonl")
async def get_run_log():
    if not os.path.exists(RUN_LOG_PATH):
        return PlainTextResponse("", media_type="text/plain")
    return FileResponse(RUN_LOG_PATH, media_type="application/jsonl")


# ---------- Run both Telegram bot and FastAPI together ----------

telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


@app.on_event("startup")
async def startup():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()
    logger_std.info("Telegram bot polling started alongside FastAPI")


@app.on_event("shutdown")
async def shutdown():
    await telegram_app.updater.stop()
    await telegram_app.stop()
    await telegram_app.shutdown()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)