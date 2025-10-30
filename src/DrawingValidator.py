from typing import Dict, List

class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.is_valid = True
    
    def add_error(self, message: str):
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        self.warnings.append(message)

class DrawingValidator:
    """Validate extracted data"""
    
    @staticmethod
    def validate(extracted_data: Dict) -> ValidationResult:
        result = ValidationResult()
        
        # Check for title block
        if not extracted_data.get('universal_data', {}).get('titleblock'):
            result.add_warning("No title block information found")
        
        # Check for drawing number
        title_block = extracted_data.get('universal_data', {}).get('titleblock', {})
        if not title_block.get('drawing_number'):
            result.add_error("Missing drawing number")
        
        # Check for scale
        if not title_block.get('scale'):
            result.add_warning("No scale information found")
        
        # Validate measurements
        specs = extracted_data.get('universal_data', {}).get('specification', [])
        for spec in specs:
            if spec.get('type') == 'measurement':
                try:
                    float(spec.get('value', ''))
                except ValueError:
                    result.add_error(f"Invalid measurement value: {spec.get('value')}")
        
        return result