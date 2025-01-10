from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import cv2
import base64
import json
import asyncio
import argparse
import os
from punch_detector import PunchDetector
import signal
import sys
import numpy as np

app = FastAPI()
detector = PunchDetector()
shutdown_event = asyncio.Event()

def signal_handler(sig, frame):
    """시그널 핸들러"""
    print('\n프로그램을 종료합니다...')
    shutdown_event.set()

@app.on_event("startup")
async def startup_event():
    """앱 시작 시 시그널 핸들러 등록"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

app.mount("/public", StaticFiles(directory="public"), name="public")

@app.get("/", response_class=HTMLResponse)
async def get():
    html_path = os.path.join("public", "index.html")
    with open(html_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    return HTMLResponse(content=html_content)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("새로운 웹소켓 연결 시작")
    await websocket.accept()
    
    # 큐 초기화
    await detector.initialize_queues()

    async def frame_processor():
        """프레임 처리 작업자"""
        try:
            while not shutdown_event.is_set():
                if detector.processing_queue.empty():
                    await asyncio.sleep(0.01)
                    continue
                
                # 큐에서 base64 데이터를 가져오기
                base64_data = await detector.processing_queue.get()
                print(f"Processing queue received: {len(base64_data)} bytes")  # 디버깅
                if base64_data is None:
                    print("Received None in processing queue")
                    continue
                
                try:
                    # Base64 디코딩
                    image_data = base64.b64decode(base64_data)
                    np_array = np.frombuffer(image_data, dtype=np.uint8)
                    frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
                    
                    if frame is None:
                        print("Error: Frame decoding failed")
                        continue
                    
                    print(f"Frame shape after decoding: {frame.shape}")  # 디버깅
                    
                    # 밝기와 대비 조정
                    frame = cv2.convertScaleAbs(frame, alpha=1.2, beta=10)
                    frame = cv2.GaussianBlur(frame, (5, 5), 0)

                    result = await detector.process_frame_async(frame)
                    if result:
                        print(f"Processed result: {result.keys()}")  # 디버깅
                        await detector.result_queue.put(result)

                except Exception as e:
                    print(f"프레임 처리 오류: {e}")
        except asyncio.CancelledError:
            print("프레임 처리 작업이 취소되었습니다")
        except Exception as e:
            print(f"프레임 처리 루프 오류: {e}")

    # 작업자 시작
    processor_task = asyncio.create_task(frame_processor())

    try:
        while not shutdown_event.is_set():
            message = await websocket.receive_json()
            if "image" in message:
                print(f"New frame received, Base64 length: {len(message['image'])}")  # 디버깅
                base64_image = message["image"]
                
                # 프레임 처리 큐에 추가
                if not detector.processing_queue.full():
                    await detector.processing_queue.put(base64_image)
                else:
                    print("Processing queue is full")

                # 결과 가져오기
                if not detector.result_queue.empty():
                    result = await detector.result_queue.get()
                    print(f"Result queue received: {result.keys()}")  # 디버깅
                    if result and 'visualization' in result:
                        _, buffer = cv2.imencode('.jpg', result['visualization'])
                        image_base64 = base64.b64encode(buffer).decode('utf-8')
                        print(f"Base64 length of processed image: {len(image_base64)}")  # 디버깅
                        await websocket.send_json({
                            'image': image_base64,
                            'stats': result.get('stats', {})
                        })
            else:
                print("지원되지 않는 메시지 포맷")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass
        await websocket.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', type=str, help='비디오 파일 경로')
    args = parser.parse_args()
    
    VIDEO_SOURCE = args.video if args.video else 0
    
    import uvicorn
    
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        loop="asyncio",
        log_level="info",
        reload=False
    )
    
    server = uvicorn.Server(config)
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다...")
    finally:
        # 추가 정리 작업이 필요한 경우
        cv2.destroyAllWindows() 
