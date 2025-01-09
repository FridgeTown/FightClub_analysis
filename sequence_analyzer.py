from collections import deque
import numpy as np
from typing import List, Dict

class SequenceAnalyzer:
    def __init__(self, sequence_length=10):
        self.sequence_length = sequence_length
        self.sequence_buffer = deque(maxlen=sequence_length)
        self.combo_patterns = {
            'double_cross': {'moves': ['cross', 'cross'], 'timeframe': 1.0},
            'cross_hook': {'moves': ['cross', 'hook'], 'timeframe': 1.0},
            'hook_cross': {'moves': ['hook', 'cross'], 'timeframe': 1.0}
        }
        
    def add_move(self, move_type: str, timestamp: float, player_id: str):
        """새로운 동작을 시퀀스에 추가"""
        self.sequence_buffer.append({
            'move': move_type,
            'time': timestamp,
            'player': player_id
        })
    
    def detect_combos(self) -> List[Dict]:
        """콤보 동작 감지"""
        if len(self.sequence_buffer) < 2:
            return []
        
        detected_combos = []
        moves = list(self.sequence_buffer)
        
        for i in range(len(moves)-1):
            for combo_name, pattern in self.combo_patterns.items():
                if (moves[i]['move'] == pattern['moves'][0] and 
                    moves[i+1]['move'] == pattern['moves'][1] and
                    moves[i+1]['time'] - moves[i]['time'] <= pattern['timeframe'] and
                    moves[i]['player'] == moves[i+1]['player']):
                    
                    detected_combos.append({
                        'type': combo_name,
                        'player': moves[i]['player'],
                        'time': moves[i+1]['time']
                    })
        
        return detected_combos 