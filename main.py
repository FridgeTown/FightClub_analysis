import os
from dotenv import load_dotenv
import logging
import asyncio
import cv2
import numpy as np
from livekit import api, rtc
from punch_detector import PunchDetector
import time

# .env 파일 로드
load_dotenv()

# Set the following environment variables with your own values
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

ROOM_NAME = "0"  # 참여하려는 방 이름
PARTICIPANT_IDENTITY = "participant_F4xG2aH9"
PARTICIPANT_NAME = "name_Y8zQ1pX3"

FRAME_INTERVAL = 0.05

detector = PunchDetector()
shutdown_event = asyncio.Event()

async def frame_processor():
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
                if result and 'visualization' in result:
                    vis_frame = result['visualization']
                    cv2.imshow("Visualization", vis_frame)
                    cv2.waitKey(1)

            except Exception as e:
                print(f"프레임 처리 오류: {e}")
    except asyncio.CancelledError:
        print("frame_processor task cancelled.")

async def process_video_frames(video_stream: rtc.VideoStream):   
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

async def main(room: rtc.Room) -> None:
    processor_task = asyncio.create_task(frame_processor())

    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant) -> None:
        logging.info(
            "participant connected: %s %s", participant.sid, participant.identity
        )

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        logging.info(
            "participant disconnected: %s %s", participant.sid, participant.identity
        )

    @room.on("local_track_published")
    def on_local_track_published(publication: rtc.LocalTrackPublication):
        logging.info("local track published: %s", publication.sid)

    @room.on("local_track_unpublished")
    def on_local_track_unpublished(publication: rtc.LocalTrackPublication):
        logging.info("local track unpublished: %s", publication.sid)

    @room.on("track_published")
    def on_track_published(
        publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
    ):
        logging.info(
            "track published: %s from participant %s (%s)",
            publication.sid,
            participant.sid,
            participant.identity,
        )

    @room.on("track_unpublished")
    def on_track_unpublished(
        publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
    ):
        logging.info("track unpublished: %s", publication.sid)

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        logging.info("track subscribed: %s", publication.sid)
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            _video_stream = rtc.VideoStream(track)
            asyncio.ensure_future(process_video_frames(_video_stream))

            # video_stream is an async iterator that yields VideoFrame
        elif track.kind == rtc.TrackKind.KIND_AUDIO:
            print("Subscribed to an Audio Track")
            _audio_stream = rtc.AudioStream(track)
            # audio_stream is an async iterator that yields AudioFrame

    @room.on("track_unsubscribed")
    def on_track_unsubscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        logging.info("track unsubscribed: %s", publication.sid)

    @room.on("data_received")
    def on_data_received(data: rtc.DataPacket):
        logging.info("received data from %s: %s", data.participant.identity, data.data)

    @room.on("connection_quality_changed")
    def on_connection_quality_changed(
        participant: rtc.Participant, quality: rtc.ConnectionQuality
    ):
        logging.info("connection quality changed for %s", participant.identity)

    @room.on("track_subscription_failed")
    def on_track_subscription_failed(
        participant: rtc.RemoteParticipant, track_sid: str, error: str
    ):
        logging.info("track subscription failed: %s %s", participant.identity, error)

    @room.on("connection_state_changed")
    def on_connection_state_changed(state: rtc.ConnectionState):
        logging.info("connection state changed: %s", state)

    @room.on("connected")
    def on_connected() -> None:
        logging.info("connected")

    @room.on("disconnected")
    def on_disconnected() -> None:
        shutdown_event.set()
        processor_task.cancel()
        logging.info("disconnected")

    @room.on("reconnecting")
    def on_reconnecting() -> None:
        logging.info("reconnecting")

    @room.on("reconnected")
    def on_reconnected() -> None:
        logging.info("reconnected")

    token = (
        api.AccessToken()
        .with_identity(PARTICIPANT_IDENTITY)
        .with_name(PARTICIPANT_NAME)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=ROOM_NAME,
            )
        )
        .to_jwt()
    )
    await room.connect(LIVEKIT_URL, token)

    logging.info("connected to room %s", room.name)

    try:
        await processor_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.FileHandler("basic_room.log"), logging.StreamHandler()],
    )
    
    loop = asyncio.get_event_loop()
    room = rtc.Room(loop=loop)
    async def cleanup():
        await room.disconnect()
        loop.stop()

    asyncio.ensure_future(main(room))

    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(room.disconnect())
        loop.close()

