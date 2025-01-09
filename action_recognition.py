import os
import cv2
import numpy as np
from ultralytics import YOLO

class ActionRecognizer:
    def __init__(self):
        # CombatSports 모델 초기화
        self.model = self.initialize_model()
        self.classes = ['boxing-bag', 'cross', 'high-guard', 'hook', 'kick', 'low-guard', 'person']
        
    def initialize_model(self):
        try:
            # 학습된 모델 경로들
            possible_paths = [
                'runs/detect/combatsports_model/weights/best.pt',  # 기본 저장 경로
                './runs/detect/combatsports_model/weights/best.pt',
                '../runs/detect/combatsports_model/weights/best.pt',
                'yolov8n.pt'  # 학습된 모델이 없으면 기본 모델 사용
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    print(f"모델을 다음 경로에서 찾았습니다: {path}")
                    return YOLO(path)
                    
            raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다. 다음 경로들을 확인했습니다: {possible_paths}")
            
        except Exception as e:
            print(f"모델 로드 중 오류 발생: {str(e)}")
            raise
        
    def recognize(self, frame, player_bbox):
        x1, y1, x2, y2 = player_bbox
        player_frame = frame[y1:y2, x1:x2]
        
        # 동작 인식 수행
        results = self.model(player_frame)
        
        # 감지된 동작들을 리스트로 변환
        actions = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                if conf > 0.5:  # 신뢰도가 50% 이상인 경우만
                    action_name = self.classes[cls_id]
                    if action_name in ['cross', 'hook']:  # 펀치 관련 동작만 카운트
                        actions.append(action_name)
        
        return actions
