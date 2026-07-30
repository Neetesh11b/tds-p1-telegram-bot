# import json
# import os
# import time
# import uuid
# import tempfile
# from google.cloud import storage

# # Ye module ek run ke saare steps collect karta hai aur
# # GCS bucket me public JSONL file ke roop me upload karta hai.

# class RunLogger:
#     def __init__(self):
#         self.entries = []
#         self.run_id = str(uuid.uuid4())

#     def log(self, step, **data):
#         entry = {
#             "run_id": self.run_id,
#             "timestamp": time.time(),
#             "step": step,
#             **data
#         }
#         self.entries.append(entry)
#         print(f"[LOG] {step}: {data}")  # local debugging ke liye

#     def upload_and_get_url(self):
#         """
#         Saare log entries ko JSONL banata hai, GCS bucket me upload karta hai,
#         public URL return karta hai.
#         Environment variables chahiye: GCS_BUCKET_NAME
#         """
#         bucket_name = os.environ["GCS_BUCKET_NAME"]
#         filename = f"run_{self.run_id}.jsonl"
#         local_path = os.path.join(tempfile.gettempdir(), filename)
#         with open(local_path, "w") as f:
#             for entry in self.entries:
#                 f.write(json.dumps(entry) + "\n")

#         client = storage.Client()
#         bucket = client.bucket(bucket_name)
#         blob = bucket.blob(f"logs/{filename}")
#         blob.upload_from_filename(local_path)

#         # Public read access - bucket already public honi chahiye (uniform access)
#         # blob.make_public()
#         return f"https://storage.googleapis.com/{bucket_name}/logs/{filename}"

#         # return blob.public_url


import json
import os
import time
import uuid

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Har run apni khud ki file me nahi, balki EK SHARED file me likhenge
# taaki /run.jsonl hamesha ek hi latest-accumulated log dikhaye.
RUN_LOG_PATH = os.path.join(LOGS_DIR, "run.jsonl")


class RunLogger:
    def __init__(self):
        self.entries = []
        self.run_id = str(uuid.uuid4())

    def log(self, step, **data):
        entry = {
            "run_id": self.run_id,
            "timestamp": time.time(),
            "step": step,
            **data
        }
        self.entries.append(entry)
        print(f"[LOG] {step}: {data}")

    def upload_and_get_url(self):
        """
        Ab GCS ki jagah local disk pe append karta hai shared run.jsonl file me,
        aur uska public URL (jo FastAPI serve karega) return karta hai.
        """
        base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")

        with open(RUN_LOG_PATH, "a") as f:
            for entry in self.entries:
                f.write(json.dumps(entry) + "\n")

        return f"{base_url}/run.jsonl"