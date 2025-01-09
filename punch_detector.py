import mediapipe as mp
import numpy as np
import cv2
from ultralytics import YOLO
import time
import asyncio

class PunchDetector:
    def __init__(self):
        # YOLO 초기화 (person 감지용)
        self.person_model = YOLO('yolov8n.pt')
        self.person_model.classes = [0]  # person class만 사용
        self.person_model.conf = 0.3     # 신뢰도 임계값 낮춤
        self.person_model.iou = 0.45
        
        # MediaPipe 초기화
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1
        )
        self.mp_drawing = mp.solutions.drawing_utils
        
        # 선수 추적 설정
        self.players = {
            'player1': {
                'position': 'left',
                'punches': {'hook': 0},
                'hits': {'face': 0, 'body': 0},
                'last_punch_time': 0,
                'tracking_id': None,
                'last_position': None
            },
            'player2': {
                'position': 'right',
                'punches': {'hook': 0},
                'hits': {'face': 0, 'body': 0},
                'last_punch_time': 0,
                'tracking_id': None,
                'last_position': None
            }
        }
        
        # 성능 최적화 설정
        self.frame_skip = 2
        self.process_count = 0
        self.prev_results = None
        
        # 펀치 감지 임계값
        self.cooldown_time = 0.3
        self.extension_threshold = 0.2
        self.cross_angle_min = 150
        self.hook_angle_min = 70
        self.hook_angle_max = 120
        
        # 비동기 처리를 위한 큐 초기화
        self.processing_queue = asyncio.Queue(maxsize=4)
        self.result_queue = asyncio.Queue(maxsize=4)

    async def initialize_queues(self):
        """큐 초기화"""
        self.processing_queue = asyncio.Queue(maxsize=4)
        self.result_queue = asyncio.Queue(maxsize=4)

    async def process_frame_async(self, frame):
        try:
            # 프레임 스킵
            self.process_count += 1
            if self.process_count % self.frame_skip != 0:
                return self.prev_results
            
            # 프레임 전처리
            frame = cv2.resize(frame, (640, 480))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # YOLO 감지
            person_results = await asyncio.get_event_loop().run_in_executor(
                None, self.person_model, frame
            )
            
            # 사람 감지 결과 처리
            person_boxes = []
            for box in person_results[0].boxes:
                if box.cls[0] == 0:  # person class
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    center_x = (x1 + x2) / 2
                    
                    person_boxes.append({
                        'bbox': (x1, y1, x2, y2),
                        'center_x': center_x,
                        'conf': conf
                    })
            
            # MediaPipe 포즈 추정
            pose_results = await asyncio.get_event_loop().run_in_executor(
                None, self.pose.process, frame_rgb
            )
            
            annotated_frame = frame.copy()
            stats = {
                'player1': {
                    'hook': self.players['player1']['punches']['hook'],
                    'hits': self.players['player1']['hits'].copy()
                },
                'player2': {
                    'hook': self.players['player2']['punches']['hook'],
                    'hits': self.players['player2']['hits'].copy()
                }
            }
            
            if pose_results.pose_landmarks and len(person_boxes) >= 2:
                # 왼쪽/오른쪽 위치 기반으로 선수 구분
                sorted_boxes = sorted(person_boxes, key=lambda x: x['center_x'])
                
                # 선수별 처리
                for i, box in enumerate(sorted_boxes[:2]):  # 최대 2명만 처리
                    player_id = 'player1' if i == 0 else 'player2'
                    x1, y1, x2, y2 = box['bbox']
                    
                    # 선수 위치 업데이트
                    self.players[player_id]['last_position'] = box['center_x']
                    
                    # 바운딩 박스 그리기
                    color = (0, 255, 0) if player_id == 'player1' else (0, 0, 255)
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(annotated_frame, f"{player_id}", (x1, y1-10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    # 펀치 감지
                    punch_info = await asyncio.get_event_loop().run_in_executor(
                        None, self.analyze_punch, pose_results.pose_landmarks.landmark,
                        player_id
                    )
                    
                    if punch_info:
                        # 펀치 효과 표시
                        self.draw_punch_effect(annotated_frame, 
                                            pose_results.pose_landmarks.landmark,
                                            punch_info, player_id)
                        
                        # 통계 업데이트
                        stats[player_id]['hook'] = self.players[player_id]['punches']['hook']
                        stats[player_id]['hits'] = self.players[player_id]['hits'].copy()
                
                # 포즈 시각화
                self.mp_drawing.draw_landmarks(
                    annotated_frame,
                    pose_results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=(245,117,66), 
                                                                    thickness=2, 
                                                                    circle_radius=2),
                    connection_drawing_spec=self.mp_drawing.DrawingSpec(color=(245,66,230), 
                                                                      thickness=2)
                )
            
            # 통계 표시 업데이트
            for i, (player_id, player_stats) in enumerate(stats.items()):
                hits = player_stats['hits']
                total_hits = hits['face'] + hits['body']
                
                # Hook 카운트
                text1 = f"{player_id}: Hook={player_stats['hook']}"
                cv2.putText(annotated_frame, text1, (10, 30 + i * 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                           (0, 255, 0) if player_id == 'player1' else (0, 0, 255), 2)
                
                # Hit 카운트
                text2 = f"Hits - Face: {hits['face']}, Body: {hits['body']} (Total: {total_hits})"
                cv2.putText(annotated_frame, text2, (10, 55 + i * 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                           (0, 255, 0) if player_id == 'player1' else (0, 0, 255), 2)
            
            self.prev_results = {
                'visualization': annotated_frame,
                'stats': stats
            }
            return self.prev_results
            
        except Exception as e:
            print(f"Error in process_frame_async: {e}")
            return self.prev_results

    def analyze_punch(self, landmarks, player_id):
        """펀치 동작 감지 및 타격 판정"""
        try:
            current_time = time.time()
            if current_time - self.players[player_id]['last_punch_time'] < self.cooldown_time:
                return None
            
            is_left = player_id == 'player1'
            opponent_id = 'player2' if is_left else 'player1'
            
            # 주요 관절 좌표 추출
            shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value if is_left else self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
            elbow = landmarks[self.mp_pose.PoseLandmark.LEFT_ELBOW.value if is_left else self.mp_pose.PoseLandmark.RIGHT_ELBOW.value]
            wrist = landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST.value if is_left else self.mp_pose.PoseLandmark.RIGHT_WRIST.value]
            
            # 상대방의 얼굴과 몸통 부위 좌표
            opponent_nose = landmarks[self.mp_pose.PoseLandmark.NOSE.value]
            opponent_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value if is_left else self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            opponent_hip = landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP.value if is_left else self.mp_pose.PoseLandmark.LEFT_HIP.value]
            
            # 2D 좌표로 변환
            wrist_pos = np.array([wrist.x, wrist.y])
            shoulder_pos = np.array([shoulder.x, shoulder.y])
            elbow_pos = np.array([elbow.x, elbow.y])
            
            opponent_nose_pos = np.array([opponent_nose.x, opponent_nose.y])
            opponent_shoulder_pos = np.array([opponent_shoulder.x, opponent_shoulder.y])
            opponent_hip_pos = np.array([opponent_hip.x, opponent_hip.y])
            
            # 타격 판정을 위한 거리 계산
            hit_distances = {
                'face': np.linalg.norm(wrist_pos - opponent_nose_pos),
                'body': min(
                    np.linalg.norm(wrist_pos - opponent_shoulder_pos),
                    np.linalg.norm(wrist_pos - opponent_hip_pos)
                )
            }
            
            # Hook 동작 감지 로직
            arm_extension = np.linalg.norm(wrist_pos - shoulder_pos)
            elbow_angle = self.calculate_angle(shoulder_pos, elbow_pos, wrist_pos)
            
            velocity = 0
            if hasattr(self, f'prev_wrist_{player_id}'):
                prev_wrist = getattr(self, f'prev_wrist_{player_id}')
                dt = current_time - getattr(self, f'prev_time_{player_id}')
                if dt > 0:
                    velocity = np.linalg.norm(wrist_pos - prev_wrist) / dt
            
            setattr(self, f'prev_wrist_{player_id}', wrist_pos)
            setattr(self, f'prev_time_{player_id}', current_time)
            
            # Hook 판정
            is_hook = (
                velocity > 0.05 and
                arm_extension > 0.15 * 0.8 and
                60 < elbow_angle < 120
            )
            
            # 타격 판정 (거리 임계값 조정 필요)
            HIT_THRESHOLD = 0.2  # 타격 거리 임계값
            hit_target = None
            if is_hook:
                if hit_distances['face'] < HIT_THRESHOLD:
                    hit_target = 'face'
                elif hit_distances['body'] < HIT_THRESHOLD:
                    hit_target = 'body'
            
            # 디버그 정보
            print(f"Player {player_id} - Vel: {velocity:.3f}, Ext: {arm_extension:.3f}, "
                  f"Angle: {elbow_angle:.1f}, Hook: {is_hook}, "
                  f"Hit Face: {hit_distances['face']:.3f}, Hit Body: {hit_distances['body']:.3f}")
            
            if is_hook:
                self.players[player_id]['last_punch_time'] = current_time
                self.players[player_id]['punches']['hook'] += 1
                
                # Hit 카운트 증가
                if hit_target:
                    self.players[player_id]['hits'][hit_target] += 1
                
                # 타격 정보 반환
                return {
                    'type': 'hook',
                    'hit': hit_target,
                    'distance': min(hit_distances.values())
                }
            
            return None
            
        except Exception as e:
            print(f"Error in analyze_punch: {e}")
            return None

    def calculate_angle(self, a, b, c):
        """세 점 사이의 각도 계산"""
        try:
            ba = a - b
            bc = c - b
            cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
            angle = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
            return angle
        except:
            return 0

    def draw_punch_effect(self, frame, landmarks, punch_info, player_id):
        """펀치 효과와 타격 시각화"""
        try:
            is_left = player_id == 'player1'
            wrist_idx = self.mp_pose.PoseLandmark.LEFT_WRIST.value if is_left else self.mp_pose.PoseLandmark.RIGHT_WRIST.value
            wrist = landmarks[wrist_idx]
            
            # 화면 좌표로 변환
            x = int(wrist.x * frame.shape[1])
            y = int(wrist.y * frame.shape[0])
            
            # 펀치 효과
            color = (255, 0, 0)  # 기본 파란색
            size = 30
            thickness = 2
            
            # 타격 시 효과 강화
            if punch_info['hit']:
                color = (0, 0, 255)  # 타격 시 빨간색
                size = 40
                thickness = 3
                
                # 타격 위치 표시
                hit_text = f"HIT: {punch_info['hit']}"
                cv2.putText(frame, hit_text, (x - 30, y - 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # 효과 그리기
            cv2.circle(frame, (x, y), size, color, thickness)
            cv2.putText(frame, "HOOK", (x - 30, y - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # 펀치 및 Hit 카운트 표시
            stats = self.players[player_id]['punches']
            hits = self.players[player_id]['hits']
            total_hits = hits['face'] + hits['body']
            
            # 첫 번째 줄: Hook 카운트
            cv2.putText(frame, 
                       f"{player_id}: Hook: {stats['hook']}", 
                       (10, 30 + (0 if player_id == 'player1' else 60)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # 두 번째 줄: Hit 카운트 (Face/Body)
            cv2.putText(frame, 
                       f"Hits - Face: {hits['face']}, Body: {hits['body']} (Total: {total_hits})", 
                       (10, 55 + (0 if player_id == 'player1' else 60)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
        except Exception as e:
            print(f"Error in draw_punch_effect: {e}")

    def identify_players(self, frame, person_boxes, landmarks_list):
        """향상된 선수 식별 로직"""
        try:
            frame_center = frame.shape[1] / 2
            current_detections = []
            
            # 각 감지된 사람에 대한 특성 추출
            for box in person_boxes:
                x1, y1, x2, y2 = box['bbox']
                center_x = box['center_x']
                
                # 신체 특성 계산
                height = y2 - y1
                roi = frame[y1:y2, x1:x2]
                color_hist = cv2.calcHist([roi], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                color_hist = cv2.normalize(color_hist, color_hist).flatten()
                
                # 어깨 너비 계산
                shoulder_width = None
                try:
                    left_shoulder = landmarks_list[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
                    right_shoulder = landmarks_list[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
                    shoulder_width = np.sqrt((left_shoulder.x - right_shoulder.x)**2 + 
                                          (left_shoulder.y - right_shoulder.y)**2)
                except:
                    pass
                
                current_detections.append({
                    'center_x': center_x,
                    'height': height,
                    'color_hist': color_hist,
                    'shoulder_width': shoulder_width,
                    'bbox': box['bbox']
                })
            
            # 선수 할당 로직
            assignments = []
            if len(current_detections) >= 2:
                # 왼쪽/오른쪽 위치 기반으로 기본 할당
                sorted_detections = sorted(current_detections, key=lambda x: x['center_x'])
                assignments = [
                    {
                        'player_id': 'player1',
                        'bbox': sorted_detections[0]['bbox'],
                        'features': {
                            'height': sorted_detections[0]['height'],
                            'color_hist': sorted_detections[0]['color_hist'],
                            'shoulder_width': sorted_detections[0]['shoulder_width']
                        }
                    },
                    {
                        'player_id': 'player2',
                        'bbox': sorted_detections[1]['bbox'],
                        'features': {
                            'height': sorted_detections[1]['height'],
                            'color_hist': sorted_detections[1]['color_hist'],
                            'shoulder_width': sorted_detections[1]['shoulder_width']
                        }
                    }
                ]
                
                # 특성 업데이트
                for assign in assignments:
                    self.update_player_features(assign['player_id'], assign['features'])
            
            return assignments
            
        except Exception as e:
            print(f"Error in identify_players: {e}")
            return []

    def update_player_features(self, player_id, features):
        """선수 특성 업데이트"""
        try:
            alpha = 0.3
            if self.player_features[player_id]['avg_height'] is None:
                self.player_features[player_id].update({
                    'avg_height': features['height'],
                    'color_hist': features['color_hist'],
                    'avg_shoulder_width': features['shoulder_width']
                })
            else:
                self.player_features[player_id].update({
                    'avg_height': (1 - alpha) * self.player_features[player_id]['avg_height'] + 
                                 alpha * features['height'],
                    'color_hist': features['color_hist'],
                    'avg_shoulder_width': features['shoulder_width'] if features['shoulder_width'] 
                                        else self.player_features[player_id]['avg_shoulder_width']
                })
        except Exception as e:
            print(f"Error in update_player_features: {e}") 
