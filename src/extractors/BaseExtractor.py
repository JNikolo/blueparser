from typing import List, Dict, Optional

class BaseExtractor:
    """Base class for all extractors"""
    
    def extract(self, text_items: List[Dict], zones: Dict) -> Dict:
        raise NotImplementedError
