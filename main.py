import os
from dotenv import load_dotenv
import asyncio
import cv2
import numpy as np
from livekit import api, rtc
from punch_detector import PunchDetector
import time
import signal
import json
import redis

redis_client = redis.Redis(
    host="127.0.0.1",  # Redis 서버 IP
    port=6379,        # Redis 포트
    db=0,             # 기본 DB
)

# .env 파일 로드
load_dotenv()

# Set the following environment variables with your own values
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

os.environ["LIVEKIT_URL"] = LIVEKIT_URL
os.environ["LIVEKIT_API_KEY"] = LIVEKIT_API_KEY
os.environ["LIVEKIT_API_SECRET"] = LIVEKIT_API_SECRET

# ROOM_NAME = "0"  # 참여하려는 방 이름
PARTICIPANT_IDENTITY = "participant_F4xG2aH9"
PARTICIPANT_NAME = "name_Y8zQ1pX3"

FRAME_INTERVAL = 0.05

# detector = PunchDetector()
shutdown_event = asyncio.Event()
rooms = dict()


async def frame_processor(detector, room_name):
    try:
        while not shutdown_event.is_set():
            if detector.processing_queue.empty():
                await asyncio.sleep(0.01)
                continue
            
            frame = await detector.processing_queue.get()
            if frame is None:
                continue
            
            try:
                # 데이터 타입 변환 (float64 → uint8)
                if frame.dtype != np.uint8:
                    frame = (frame * 255).astype(np.uint8)

                # NumPy로 밝기와 대비 조정
                frame = frame * 1.2 + 10
                frame = np.clip(frame, 0, 255).astype(np.uint8)  # 값 범위 제한 및 uint8로 변환

                # OpenCV로 블러 적용
                frame = cv2.blur(frame, (3, 3))  # 작은 커널 사용


                result = await detector.process_frame_async(frame)
                if result:
                    await detector.result_queue.put(result)

                if not detector.result_queue.empty():
                    result = await detector.result_queue.get()
                    redis_client.set(room_name, json.dumps(detector.players))
                # if result and 'visualization' in result:
                #     vis_frame = result['visualization']
                #     cv2.imshow("Visualization", vis_frame)
                #     if cv2.waitKey(1) & 0xFF == ord("q"):
                #         return

            except Exception as e:
                print(f"프레임 처리 오류: {e}")
    except asyncio.CancelledError:
        print("frame_processor task cancelled.")

async def process_video_frames(video_stream: rtc.VideoStream, detector):   
    last_processed_time = 0  # 마지막으로 프레임을 처리한 시간
    async for frame_event in video_stream:
        
        current_time = time.time()
        
        # 설정한 간격이 지나지 않았다면 다음 프레임으로 넘어감
        if current_time - last_processed_time < FRAME_INTERVAL:
            continue
        # VideoFrameEvent 객체에서 frame 데이터 추출
        frame_obj = frame_event.frame 

        yuv_data = np.frombuffer(frame_obj.data, dtype=np.uint8)
        height = frame_obj.height
        width = frame_obj.width
        yuv_image = yuv_data.reshape((height + height // 2, width))
        bgr_image = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2BGR_I420)

        if not detector.processing_queue.full():
            await detector.processing_queue.put(bgr_image)

        last_processed_time = current_time


    cv2.destroyAllWindows()

async def main(rtc_room: rtc.Room, room_name) -> None:
    processor_task = asyncio.create_task(frame_processor(rooms[room_name], room_name))

    @rtc_room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        # logging.info("track subscribed: %s", participant.name)
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            _video_stream = rtc.VideoStream(track)
            asyncio.ensure_future(process_video_frames(_video_stream, rooms[room_name]))

    @rtc_room.on("disconnected")
    def on_disconnected() -> None:
        shutdown_event.set()
        processor_task.cancel()
        rooms.pop(room_name)
        redis_client.delete(room_name)

    token = (
        api.AccessToken()
        .with_identity(PARTICIPANT_IDENTITY)
        .with_name(PARTICIPANT_NAME)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
        .to_jwt()
    )
    await rtc_room.connect(LIVEKIT_URL, token)

    try:
        await processor_task
    except asyncio.CancelledError:
        pass

async def connect_and_process_room(room_name):
    rtc_room = rtc.Room()
    await main(rtc_room, room_name)


async def poll_rooms():
    lkapi = api.LiveKitAPI()
    while not shutdown_event.is_set():
        try:
            roomlist = await lkapi.room.list_rooms(api.ListRoomsRequest())
            current_rooms = {room.name for room in roomlist.rooms}
            for current_room in current_rooms:
                if current_room not in rooms:
                    rooms[current_room] = PunchDetector()
                    redis_client.set(current_room, json.dumps({}))
                    asyncio.create_task(connect_and_process_room(current_room))

        except Exception as e:
            print(f"Error while polling rooms: {e}")

        await asyncio.sleep(3)  # 1초 대기


def shutdown_handler():
    redis_client.flushdb()
    shutdown_event.set()



if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: shutdown_handler())
    signal.signal(signal.SIGTERM, lambda s, f: shutdown_handler())
    # WebRTC 관련 작업 실행
    try:
        asyncio.run(poll_rooms())
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        redis_client.flushdb()