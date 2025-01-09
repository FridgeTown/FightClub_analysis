from collections import deque
import numpy as np
from typing import Dict, List, Optional

class PlayerTracker:
    def __init__(self, max_history=30):
        self.max_history = max_history
        self.players = {
            'player1': {
                'position': 'left',
                'history': deque(maxlen=max_history),
                'movement_score': 0,
                'last_position': None
            },
            'player2': {
                'position': 'right',
                'history': deque(maxlen=max_history),
                'movement_score': 0,
                'last_position': None
            }
        }
    
    def update(self, player_id: str, bbox: tuple, landmarks: List, confidence: float):
        """선수의 위치와 포즈 정보 업데이트"""
        player = self.players[player_id]
        current_center = ((bbox[0] + bbox[2])/2, (bbox[1] + bbox[3])/2)
        
        # 이동 점수 계산
        if player['last_position']:
            movement = np.linalg.norm(np.array(current_center) - np.array(player['last_position']))
            player['movement_score'] = movement
        
        player['last_position'] = current_center
        player['history'].append({
            'bbox': bbox,
            'landmarks': landmarks,
            'confidence': confidence,
            'center': current_center
        })
    
    def get_player_stats(self, player_id: str) -> Dict:
        """선수의 상세 통계 정보 반환"""
        player = self.players[player_id]
        if not player['history']:
            return {}
        
        recent_positions = [frame['center'] for frame in player['history']]
        movement_range = {
            'x': (min(p[0] for p in recent_positions), max(p[0] for p in recent_positions)),
            'y': (min(p[1] for p in recent_positions), max(p[1] for p in recent_positions))
        }
        
        return {
            'movement_score': player['movement_score'],
            'movement_range': movement_range,
            'avg_confidence': np.mean([frame['confidence'] for frame in player['history']])
        } 