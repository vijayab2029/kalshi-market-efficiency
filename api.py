import os
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from upstash_redis import Redis

load_dotenv()

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

redis = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN"),
)

KEY_1 = "kalshi:live_violations"


@app.get("/api/violations")
def get_violations():
    raw = redis.get(KEY_1)
    if raw is None:
        return {"updated_at": None, "violation_count": 0, "violations": []}
    return json.loads(raw)