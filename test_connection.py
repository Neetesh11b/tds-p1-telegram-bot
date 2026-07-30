# import os
# import requests
# from dotenv import load_dotenv

# load_dotenv()

# url = f"{os.environ['AI_PIPE_BASE_URL']}/chat/completions"

# headers = {
#     "Authorization": f"Bearer {os.environ['AI_PIPE_TOKEN']}",
#     "Content-Type": "application/json",
# }

# payload = {
#     "model": os.environ["MODEL_NAME"],
#     "messages": [
#         {
#             "role": "user",
#             "content": "Reply with exactly one word: hello"
#         }
#     ],
#     "max_tokens": 10,
#     "temperature": 0
# }

# print("URL:", url)
# print("Model:", payload["model"])

# response = requests.post(
#     url,
#     headers=headers,
#     json=payload,
#     timeout=60
# )

# print("\nStatus Code:", response.status_code)
# print("\nResponse:")
# print(response.text)
import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = f"{os.environ['AI_PIPE_BASE_URL']}/models/{os.environ['MODEL_NAME']}:generateContent"

headers = {
    "Authorization": f"Bearer {os.environ['AI_PIPE_TOKEN']}",
    "Content-Type": "application/json",
}

payload = {
    "contents": [
        {
            "parts": [
                {
                    "text": "Reply with exactly one word: hello"
                }
            ]
        }
    ]
}

print("URL:", url)

response = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=60,
)

print(response.status_code)
print(response.text)