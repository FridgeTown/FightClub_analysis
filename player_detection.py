import cv2
import numpy as np
from ultralytics import YOLO

class PlayerDetector:
    def __init__(self):
        # YOLO 모델 로드
        self.model = YOLO('yolov8n.pt')
        
    def detect(self, frame):
        # YOLO를 사용하여 선수 감지
        results = self.model(frame)
        players = {}
        
        # 감지된 사람들 중에서 선수 구분
        detections = results[0].boxes.data
        for i, detection in enumerate(detections):
            if detection[5] == 0:  # person class
                x1, y1, x2, y2 = map(int, detection[:4])
                # 왼쪽에 있는 선수를 player1으로 구분
                player_id = f'player{1 if x1 < frame.shape[1]/2 else 2}'
                players[player_id] = (x1, y1, x2, y2)
                
        return players 