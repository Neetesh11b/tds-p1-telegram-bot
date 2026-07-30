import os
from dotenv import load_dotenv
load_dotenv()
import requests

resp = requests.post(
    f"{os.environ['AI_PIPE_BASE_URL']}/chat/completions",
    headers={"Authorization": f"Bearer {os.environ['AI_PIPE_TOKEN']}"},
    # json={
    #     "model": os.environ.get("MODEL_NAME", "google/gemini-2.0-flash"),
    #     "messages": [{"role": "user", "content": "say hi"}]
    # }
    json={
    "model": os.environ["MODEL_NAME"],
    "messages": [
        {"role": "user", "content": "Say only: hi"}
    ],
    "max_tokens": 5
}
)
print(resp.status_code)
print(resp.text)