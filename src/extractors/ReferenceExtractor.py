import re
from typing import List, Dict
from extractors.BaseExtractor import BaseExtractor

class ReferenceExtractor(BaseExtractor):
    """Extract references to other drawings, codes, regulations"""
    
    def extract(self, text_items: List[Dict], zones: Dict) -> List[Dict]:
        references = []
        
        full_text = ' '.join([item['text'] for item in text_items])
        
        # Pattern: "See Drawing X"
        drawing_refs = re.findall(
            r'SEE\s+(DRAWING|DWG|SHEET|DETAIL)\s+([A-Z0-9-]+)',
            full_text,
            re.IGNORECASE
        )
        
        for ref_type, ref_id in drawing_refs:
            references.append({
                'type': 'drawing_reference',
                'reference_type': ref_type,
                'reference_id': ref_id
            })
        
        # Pattern: FAC Rule, Code references
        code_refs = re.findall(
            r'(F\.A\.C\.|FAC)\s+(RULE\s+)?(\d+-[\d.]+)',
            full_text,
            re.IGNORECASE
        )
        
        for prefix, _, code_num in code_refs:
            references.append({
                'type': 'regulation',
                'regulation_type': 'Florida Administrative Code',
                'code': code_num
            })
        
        # Pattern: "In accordance with"
        accordance_refs = re.findall(
            r'IN ACCORDANCE WITH\s+([^\n.]+)',
            full_text,
            re.IGNORECASE
        )
        
        for ref in accordance_refs:
            references.append({
                'type': 'standard_reference',
                'description': ref.strip()
            })
        
        return references