import re
from typing import List, Dict
from extractors.BaseExtractor import BaseExtractor


class NotesExtractor(BaseExtractor):
    """Extract notes, disclaimers, and annotations"""
    
    def extract(self, text_items: List[Dict], zones: Dict) -> List[Dict]:
        notes = []
        
        full_text = ' '.join([item['text'] for item in text_items])
        
        # Pattern 1: Numbered notes (1), (2), (3)
        numbered_notes = re.findall(
            r'\((\d+)\)\s+([^\(]+?)(?=\(\d+\)|$)', 
            full_text, 
            re.DOTALL
        )
        
        for num, content in numbered_notes:
            notes.append({
                'type': 'numbered',
                'number': num,
                'content': content.strip()
            })
        
        # Pattern 2: NOTE: or NOTES:
        note_blocks = re.findall(
            r'NOTES?[:\s]+([^\n]+(?:\n(?!NOTE)[^\n]+)*)',
            full_text,
            re.IGNORECASE | re.MULTILINE
        )
        
        for note in note_blocks:
            notes.append({
                'type': 'general',
                'content': note.strip()
            })
        
        # Pattern 3: Disclaimers
        if 'DISCLAIMER' in full_text.upper():
            disclaimer_match = re.search(
                r'DISCLAIMER[:\s-]+([^\n]+(?:\n[^\n]+)*)',
                full_text,
                re.IGNORECASE
            )
            if disclaimer_match:
                notes.append({
                    'type': 'disclaimer',
                    'content': disclaimer_match.group(1).strip()
                })
        
        return notes