from typing import List, Dict
from extractors.TitleBlockExtractor import TitleBlockExtractor
from extractors.NotesExtractor import NotesExtractor
from extractors.SpecificationExtractor import SpecificationExtractor
from extractors.ReferenceExtractor import ReferenceExtractor
from extractors.TableExtractor import TableExtractor
import re

class StandardsDetailParser:
    """Parser for standards/detail drawings like your sanitary sewer doc"""
    
    def __init__(self):
        self.title_extractor = TitleBlockExtractor()
        self.notes_extractor = NotesExtractor()
        self.table_extractor = TableExtractor()
        self.spec_extractor = SpecificationExtractor()
        self.ref_extractor = ReferenceExtractor()
    
    def parse(self, text_items: List[Dict]) -> Dict:
        """Parse standards detail drawing"""
        
        zones = self._identify_zones(text_items)
        
        result = {
            'document_type': 'standards_detail',
            'title_block': self.title_extractor.extract(text_items, zones),
            'tables': self.table_extractor.extract(text_items, zones),
            'notes': self.notes_extractor.extract(text_items, zones),
            'specifications': self.spec_extractor.extract(text_items, zones),
            'references': self.ref_extractor.extract(text_items, zones),
            'requirements': self._extract_requirements(text_items, zones)
        }
        
        return result
    
    def _identify_zones(self, text_items: List[Dict]) -> Dict:
        """Identify different zones in the drawing"""
        zones = {
            'title': [],
            'table_area': [],
            'notes_area': [],
            'diagram_area': []
        }
        
        for item in text_items:
            bbox = item['bbox']
            
            # Bottom area is usually title/notes
            if bbox['top'] > 0.85:
                zones['title'].append(item)
            # Check for table indicators
            elif 'minimum' in item['text'].lower() or 'ft' in item['text'].lower():
                zones['table_area'].append(item)
            # Notes usually have numbered items
            elif re.match(r'\(\d+\)', item['text']):
                zones['notes_area'].append(item)
            else:
                zones['diagram_area'].append(item)
        
        return zones
    
    def _extract_requirements(self, text_items: List[Dict], zones: Dict) -> List[Dict]:
        """Extract specific requirements (separations, minimums, etc.)"""
        requirements = []
        
        full_text = ' '.join([item['text'] for item in text_items])
        
        # Pattern: "X minimum" or "X ft. minimum"
        min_reqs = re.findall(
            r'(\d+\.?\d*)\s*(ft|feet|in|inch|inches)?\s*(?:is\s+the\s+)?minimum',
            full_text,
            re.IGNORECASE
        )
        
        for value, unit in min_reqs:
            requirements.append({
                'type': 'minimum',
                'value': value,
                'unit': unit if unit else 'unspecified',
                'context': self._get_context(full_text, f"{value} minimum", 100)
            })
        
        # Pattern: "X preferred"
        pref_reqs = re.findall(
            r'(\d+\.?\d*)\s*(ft|feet|in|inch)?\s*preferred',
            full_text,
            re.IGNORECASE
        )
        
        for value, unit in pref_reqs:
            requirements.append({
                'type': 'preferred',
                'value': value,
                'unit': unit if unit else 'unspecified',
                'context': self._get_context(full_text, f"{value} preferred", 100)
            })
        
        return requirements
    
    def _get_context(self, text: str, term: str, window: int) -> str:
        idx = text.find(term)
        if idx == -1:
            return ""
        start = max(0, idx - window)
        end = min(len(text), idx + len(term) + window)
        return text[start:end].strip()