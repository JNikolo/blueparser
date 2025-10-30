from extractors.BaseExtractor import BaseExtractor
from typing import List, Dict
import re


class SpecificationExtractor(BaseExtractor):
    """Extract specifications, requirements, and measurements"""
    
    def extract(self, text_items: List[Dict], zones: Dict) -> List[Dict]:
        specifications = []
        
        full_text = ' '.join([item['text'] for item in text_items])
        
        # Extract measurements with units
        measurements = re.findall(
            r'(\d+\.?\d*)\s*(ft|feet|in|inch|inches|mm|cm|m|"|\'|min|max|minimum|maximum)',
            full_text,
            re.IGNORECASE
        )
        
        for value, unit in measurements:
            specifications.append({
                'type': 'measurement',
                'value': value,
                'unit': unit,
                'context': self._get_context(full_text, f"{value} {unit}")
            })
        
        # Extract material specifications
        materials = re.findall(
            r'\b(PVC|SS|DI|HDPE|PE|FG|316L?|STEEL|IRON|ALUMINUM|BRASS|COPPER)\b',
            full_text
        )
        
        for material in set(materials):
            specifications.append({
                'type': 'material',
                'value': material,
                'context': self._get_context(full_text, material)
            })
        
        # Extract standards/codes
        standards = re.findall(
            r'(ASTM|ANSI|API|ASME|AWS|IEEE|NFPA|IBC|UBC|ACI|PVC|AWWA)\s*[A-Z]?[-\s]?\d+[.\d]*',
            full_text,
            re.IGNORECASE
        )
        
        for standard in standards:
            specifications.append({
                'type': 'standard',
                'value': standard,
                'context': self._get_context(full_text, standard)
            })
        
        return specifications
    
    def _get_context(self, text: str, term: str, window: int = 50) -> str:
        """Get surrounding text for context"""
        idx = text.find(term)
        if idx == -1:
            return ""
        
        start = max(0, idx - window)
        end = min(len(text), idx + len(term) + window)
        return text[start:end].strip()