import os
from dotenv import load_dotenv
load_dotenv()
import requests

resp = requests.get(
    "https://aipipe.org/openrouter/v1/models",
    headers={"Authorization": f"Bearer {os.environ['AI_PIPE_TOKEN']}"}
)
print(resp.status_code)
# sirf gemini wale model names print karo, taaki output chhota rahe
import json
data = resp.json()
for m in data.get("data", []):
    if "gemini" in m.get("id", "").lower():
        print(m["id"])