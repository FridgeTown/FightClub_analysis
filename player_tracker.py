import numpy as np
from collections import deque
from typing import Dict, List, Tuple
import cv2

class EnhancedPlayerTracker:
    def __init__(self, max_history=30, max_players=2):
        self.max_history = max_history
        self.max_players = max_players
        self.players = {}
        self.track_ids = set()
        
    def calculate_pose_similarity(self, pose1, pose2):
        """포즈 간 유사도 계산"""
        keypoints1 = np.array([[lm.x, lm.y] for lm in pose1])
        keypoints2 = np.array([[lm.x, lm.y] for lm in pose2])
        
        # Procrustes 분석으로 포즈 정렬 및 유사도 계산
        similarity = self._procrustes_similarity(keypoints1, keypoints2)
        return similarity
    
    def _procrustes_similarity(self, X, Y):
        """Procrustes 분석으로 포즈 유사도 계산"""
        X_c = X - np.mean(X, axis=0)
        Y_c = Y - np.mean(Y, axis=0)
        
        # 정규화
        X_n = X_c / np.linalg.norm(X_c)
        Y_n = Y_c / np.linalg.norm(Y_c)
        
        # SVD로 회전 매트릭스 계산
        U, _, Vt = np.linalg.svd(X_n.T @ Y_n)
        R = Vt.T @ U.T
        
        # 변환 후 유사도 계산
        similarity = np.sum((X_n @ R - Y_n) ** 2)
        return similarity
    
    def update(self, detections: List[Dict]):
        """선수 추적 업데이트"""
        if not self.players:  # 초기화
            for i, det in enumerate(detections[:self.max_players]):
                track_id = i
                self.track_ids.add(track_id)
                self.players[track_id] = {
                    'pose_history': deque(maxlen=self.max_history),
                    'position': 'left' if i == 0 else 'right',
                    'last_pose': det['landmarks'],
                    'confidence': det['confidence'],
                    'lost_frames': 0
                }
        else:
            # 현재 프레임의 detection을 이전 선수들과 매칭
            cost_matrix = np.zeros((len(detections), len(self.players)))
            for i, det in enumerate(detections):
                for j, (track_id, player) in enumerate(self.players.items()):
                    cost_matrix[i, j] = self.calculate_pose_similarity(
                        det['landmarks'], player['last_pose']
                    )
            
            # Hungarian 알고리즘으로 최적 매칭
            from scipy.optimize import linear_sum_assignment
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            
            # 매칭 결과 적용
            matched_track_ids = set()
            for i, j in zip(row_ind, col_ind):
                if i < len(detections) and j < len(self.players):
                    track_id = list(self.players.keys())[j]
                    matched_track_ids.add(track_id)
                    self.players[track_id].update({
                        'last_pose': detections[i]['landmarks'],
                        'confidence': detections[i]['confidence'],
                        'lost_frames': 0
                    })
            
            # 매칭되지 않은 선수 처리
            for track_id in self.track_ids - matched_track_ids:
                self.players[track_id]['lost_frames'] += 1
                if self.players[track_id]['lost_frames'] > 30:  # 1초 이상 감지 안됨
                    del self.players[track_id]
                    self.track_ids.remove(track_id) 