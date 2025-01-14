from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import redis


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_methods=["GET"],
    allow_headers=["*"],
    allow_credentials=True, 
)

redis_client = redis.Redis(
    host="127.0.0.1",  # Redis 서버 IP
    port=6379,        # Redis 포트
    db=0,             # 기본 DB
)

@app.get("/api/stream/{room_name}")
async def stream_players(room_name: str):
    """
    SSE 방식으로 rooms[room_name].players 데이터를 클라이언트에 전송
    """
    async def event_generator():
        while True:
            # Redis에서 데이터 가져오기
            raw_data = redis_client.get(room_name)
            
            if raw_data:
                try:
                    # 바이트 데이터를 JSON 문자열로 변환
                    data = json.loads(raw_data.decode("utf-8"))
                    # 플레이어 데이터 가져오기
                    yield f"data: {json.dumps(data)}\n\n"
                except json.JSONDecodeError as e:
                    # JSON 디코딩 오류 처리
                    yield f"data: {json.dumps({'error': 'Invalid data format in Redis'})}\n\n"
            else:
                # 방 데이터가 없는 경우
                yield f"data: {json.dumps({'error': 'Room not found'})}\n\n"

            # 1초마다 갱신
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)