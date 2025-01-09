from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import cv2
import base64
import json
import asyncio
import argparse
import os
from punch_detector import PunchDetector
import signal
import sys

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

@app.get("/", response_class=HTMLResponse)
async def get():
    return """
    <html>
        <head>
            <title>실시간 스파링 분석</title>
            <style>
                .container {
                    display: flex;
                    justify-content: center;
                    align-items: start;
                    padding: 20px;
                }
                .video-feed {
                    max-width: 800px;
                    width: 100%;
                }
                .stats {
                    margin-left: 20px;
                    padding: 20px;
                    background: #f5f5f5;
                    border-radius: 8px;
                }
                .stats-row {
                    margin: 10px 0;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div>
                    <img id="video-feed" class="video-feed"/>
                </div>
                <div class="stats">
                    <h2>경기 통계</h2>
                    <div id="player1-stats">
                        <div class="stats-row">Player 1 - Hook: <span id="p1-hook">0</span></div>
                        <div class="stats-row">Hits - Face: <span id="p1-face">0</span>, Body: <span id="p1-body">0</span></div>
                        <div class="stats-row">Total Hits: <span id="p1-total">0</span></div>
                    </div>
                    <div id="player2-stats">
                        <div class="stats-row">Player 2 - Hook: <span id="p2-hook">0</span></div>
                        <div class="stats-row">Hits - Face: <span id="p2-face">0</span>, Body: <span id="p2-body">0</span></div>
                        <div class="stats-row">Total Hits: <span id="p2-total">0</span></div>
                    </div>
                </div>
            </div>
            <script>
                const ws = new WebSocket('ws://localhost:8000/ws');
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    // 이미지 업데이트
                    document.getElementById('video-feed').src = 'data:image/jpeg;base64,' + data.image;
                    
                    // 통계 업데이트
                    document.getElementById('p1-hook').textContent = data.stats.player1.hook;
                    document.getElementById('p1-face').textContent = data.stats.player1.hits.face;
                    document.getElementById('p1-body').textContent = data.stats.player1.hits.body;
                    document.getElementById('p1-total').textContent = 
                        data.stats.player1.hits.face + data.stats.player1.hits.body;
                    
                    document.getElementById('p2-hook').textContent = data.stats.player2.hook;
                    document.getElementById('p2-face').textContent = data.stats.player2.hits.face;
                    document.getElementById('p2-body').textContent = data.stats.player2.hits.body;
                    document.getElementById('p2-total').textContent = 
                        data.stats.player2.hits.face + data.stats.player2.hits.body;
                };
            </script>
        </body>
    </html>
    """

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("새로운 웹소켓 연결 시작")
    await websocket.accept()
    
    # 비디오 캡스 설정
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print(f"Error: 비디오 소스를 열 수 없습니다 - {VIDEO_SOURCE}")
        await websocket.close()
        return
    
    # 비디오 파일과 웹캠에 따른 설정 조정
    is_video_file = isinstance(VIDEO_SOURCE, str)
    if is_video_file:
        # 비디오 파일 설정
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_delay = 1.0 / fps if fps > 0 else 0.03
        print(f"비디오 파일 모드 - FPS: {fps}")
    else:
        # 웹캠 설정
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # YOLO 입력 크기에 맞춤
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)  # 정사각형 비율 사용
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
        frame_delay = 0.01
        print("웹캠 모드 - HD 설정")
    
    print(f"비디오 캡처 성공 - 소스: {VIDEO_SOURCE}")
    
    # 큐 초기화
    await detector.initialize_queues()
    
    # 프레임 처리 작업자 생성
    async def frame_processor():
        try:
            while not shutdown_event.is_set():
                if detector.processing_queue.empty():
                    await asyncio.sleep(0.01)
                    continue
                    
                frame = await detector.processing_queue.get()
                if frame is None:
                    continue
                    
                # 웹캠 모드에서 프레임 전처리
                if not is_video_file:
                    # 밝기와 대비 조정
                    frame = cv2.convertScaleAbs(frame, alpha=1.2, beta=10)
                    
                    # 노이즈 제거
                    frame = cv2.GaussianBlur(frame, (5, 5), 0)
                
                result = await detector.process_frame_async(frame)
                if result:
                    await detector.result_queue.put(result)
                
        except Exception as e:
            print(f"Frame processor error: {e}")
    
    # 작업자 시작
    processor_task = asyncio.create_task(frame_processor())
    frame_count = 0
    
    try:
        while not shutdown_event.is_set():
            try:
                ret, frame = cap.read()
                if not ret:
                    if is_video_file:
                        print("비디오 파일 재시작")
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        print("웹캠 프레임을 읽을 수 없습니다")
                        break
                
                frame_count += 1
                
                # 비디오 파일일 경우만 프레임 스킵
                if is_video_file and frame_count % 2 != 0:
                    continue
                
                if not is_video_file:
                    # 웹캠 프레임 전처리 순서 변경
                    frame = cv2.resize(frame, (640, 640))  # YOLO 입력 크기에 맞춤
                    frame = cv2.convertScaleAbs(frame, alpha=1.3, beta=5)  # 약간의 밝기 조정
                
                # 프레임 처리 큐에 추가
                if not detector.processing_queue.full():
                    await detector.processing_queue.put(frame)
                
                # 결과 가져오기
                if not detector.result_queue.empty():
                    result = await detector.result_queue.get()
                    if result and 'visualization' in result:
                        # JPEG 품질 조정
                        quality = 70 if not is_video_file else 80
                        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                        _, buffer = cv2.imencode('.jpg', result['visualization'], encode_param)
                        image_base64 = base64.b64encode(buffer).decode('utf-8')
                        
                        await websocket.send_json({
                            'image': image_base64,
                            'stats': result.get('stats', {
                                'player1': {'hook': 0, 'hits': {'face': 0, 'body': 0}},
                                'player2': {'hook': 0, 'hits': {'face': 0, 'body': 0}}
                            })
                        })
                        
                        if frame_count % 30 == 0:
                            print(f"프레임 전송 완료: {frame_count}")
                
                await asyncio.sleep(frame_delay)
                
            except asyncio.CancelledError:
                print("작업이 취소되었습니다")
                break
            except Exception as e:
                print(f"메인 루프 오류: {e}")
                continue
            
    except Exception as e:
        print(f"Websocket error: {e}")
    finally:
        print("연결 종료 및 정리 작업 시작")
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass
        
        cap.release()
        await websocket.close()
        print("웹소켓 연결이 종료되었습니다")

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
