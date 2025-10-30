from extractors.BaseExtractor import BaseExtractor
from typing import List, Dict, Optional
import re

class TitleBlockExtractor(BaseExtractor):
    """Extract standard title block information"""
    
    def extract(self, text_items: List[Dict], zones: Dict) -> Dict:
        # Title blocks are typically in bottom-right or bottom area
        bottom_items = [
            item for item in text_items 
            if item['bbox']['top'] > 0.85  # Bottom 15%
        ]
        
        full_text = ' '.join([item['text'] for item in bottom_items])
        
        return {
            'drawing_number': self._extract_drawing_number(full_text),
            'drawing_title': self._extract_title(full_text),
            'date': self._extract_date(full_text),
            'scale': self._extract_scale(full_text),
            'revision': self._extract_revision(full_text),
            'sheet_number': self._extract_sheet(full_text)
        }
    
    def _extract_drawing_number(self, text: str) -> Optional[str]:
        patterns = [
            r'DWG[.\s#-]*([A-Z0-9-]+)',
            r'DRAWING[.\s#-]*([A-Z0-9-]+)',
            r'NO\.[.\s]*([A-Z0-9-]+)',
            r'([A-Z]-\d+)',  # C-16, M-1, etc.
            r'SHEET[.\s#-]*([A-Z0-9-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_title(self, text: str) -> Optional[str]:
        # Look for common title patterns
        patterns = [
            r'TITLE[:\s]+([^\n]+)',
            r'^([A-Z\s]+DETAIL[S]?)',
            r'^([A-Z\s]+PLAN)',
            r'^([A-Z\s]+DIAGRAM)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        
        # If no pattern, take the longest ALL CAPS line
        lines = text.split('\n')
        caps_lines = [line for line in lines if line.isupper() and len(line) > 10]
        return caps_lines[0] if caps_lines else None
    
    def _extract_date(self, text: str) -> Optional[str]:
        patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
            r'DATE[:\s]+([^\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_scale(self, text: str) -> Optional[str]:
        patterns = [
            r'SCALE[:\s]+([^\n,]+)',
            r'(\d+:\d+)',
            r'(NTS|N\.T\.S\.)',  # Not to scale
            r'(1/\d+"?\s*=\s*\d+\'?-?\d*"?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_revision(self, text: str) -> Optional[str]:
        patterns = [
            r'REV[.:\s]+([A-Z0-9]+)',
            r'REVISION[:\s]+([A-Z0-9]+)',
            r'\bREV\s+([A-Z0-9])\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_sheet(self, text: str) -> Optional[str]:
        patterns = [
            r'SHEET[:\s]+(\d+)\s+OF\s+(\d+)',
            r'(\d+)\s+OF\s+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} of {match.group(2)}"
        return None