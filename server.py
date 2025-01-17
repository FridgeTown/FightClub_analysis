from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import redis
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_methods=["GET"],
    allow_headers=["*"],
    allow_credentials=True, 
)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "127.0.0.1"),  # 기본값: 127.0.0.1
    port=int(os.getenv("REDIS_PORT", 6379)),   # 기본값: 6379
    db=int(os.getenv("REDIS_DB", 0)),           # 기본 DB
)

def has_significant_change(old_data: dict, new_data: dict) -> bool:
    """
    old_data와 new_data에서 player1/player2의 비교
    - player1.hits.face, player2.hits.face
    - player1.hits.body, player2.hits.body
    - player1.punches.hook, player2.punches.hook
    """
    # 중첩 딕셔너리 접근 (없으면 default 반환)
    def get_nested(d, keys, default=None):
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        return d

    fields_to_check = [
        ["player1", "hits", "face"],
        ["player1", "hits", "body"],
        ["player1", "punches", "hook"],
        ["player2", "hits", "face"],
        ["player2", "hits", "body"],
        ["player2", "punches", "hook"],
    ]

    for field_keys in fields_to_check:
        old_val = get_nested(old_data, field_keys)
        new_val = get_nested(new_data, field_keys)
        if old_val != new_val:
            return True

    return False

@app.get("/api/stream/{room_name}")
async def stream_players(room_name: str):
    async def event_generator():
        previous_data = {}
        while True:
            raw_data = redis_client.get(room_name)
            
            if raw_data:
                try:
                    current_data = json.loads(raw_data.decode("utf-8"))

                    if has_significant_change(previous_data, current_data):
                        yield f"data: {json.dumps(current_data)}\n\n"
                        previous_data = current_data 

                except json.JSONDecodeError as e:
                    yield f"data: {json.dumps({'error': 'Invalid data format in Redis'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': 'Room not found'})}\n\n"

            await asyncio.sleep(0.4)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn\
    app_port = int(os.getenv("APP_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=app_port)