from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import re

class DrawingType(Enum):
    PUMP_STATION = "pump_station"
    STANDARDS_DETAIL = "standards_detail"
    PIPING_DIAGRAM = "piping_diagram"
    FLOOR_PLAN = "floor_plan"
    SITE_PLAN = "site_plan"
    SPECIFICATION_TABLE = "specification_table"
    UNKNOWN = "unknown"

class DrawingDiscipline(Enum):
    MECHANICAL = "mechanical"
    CIVIL = "civil"
    ELECTRICAL = "electrical"
    STRUCTURAL = "structural"
    PLUMBING = "plumbing"
    UNKNOWN = "unknown"

@dataclass
class DrawingClassification:
    drawing_type: DrawingType
    discipline: DrawingDiscipline
    has_table: bool
    has_notes: bool
    has_legend: bool
    has_specifications: bool
    confidence: float

def classify_drawing(ocr_text: str, text_items: List[Dict]) -> DrawingClassification:
    """
    Determine what type of drawing this is based on content
    """
    text_upper = ocr_text.upper()
    
    # Keyword detection
    keywords = {
        DrawingType.PUMP_STATION: ['PUMP STATION', 'PUMP', 'WETWELL', 'GPM', 'TDH'],
        DrawingType.STANDARDS_DETAIL: ['STANDARD DETAIL', 'ACCORDANCE WITH', 'MINIMUM', 'SEPARATION'],
        DrawingType.PIPING_DIAGRAM: ['P&ID', 'PIPING', 'VALVE', 'FLOW'],
        DrawingType.FLOOR_PLAN: ['FLOOR PLAN', 'ROOM', 'ELEVATION', 'LEVEL'],
        DrawingType.SITE_PLAN: ['SITE PLAN', 'PROPERTY LINE', 'LOT', 'SETBACK'],
        DrawingType.SPECIFICATION_TABLE: ['SPECIFICATION', 'REQUIREMENT', 'TABLE']
    }
    
    discipline_keywords = {
        DrawingDiscipline.MECHANICAL: ['MECHANICAL', 'HVAC', 'PUMP', 'VALVE', 'GPM'],
        DrawingDiscipline.CIVIL: ['CIVIL', 'SEWER', 'STORM', 'WATER MAIN', 'UTILITY'],
        DrawingDiscipline.ELECTRICAL: ['ELECTRICAL', 'PANEL', 'CIRCUIT', 'VOLTAGE'],
        DrawingDiscipline.STRUCTURAL: ['STRUCTURAL', 'BEAM', 'COLUMN', 'FOUNDATION'],
        DrawingDiscipline.PLUMBING: ['PLUMBING', 'SANITARY', 'WASTE', 'FIXTURE']
    }
    
    # Score each type
    type_scores = {}
    for draw_type, kws in keywords.items():
        score = sum(1 for kw in kws if kw in text_upper)
        type_scores[draw_type] = score
    
    detected_type = max(type_scores, key=type_scores.get)
    if type_scores[detected_type] == 0:
        detected_type = DrawingType.UNKNOWN
    
    # Detect discipline
    disc_scores = {}
    for disc, kws in discipline_keywords.items():
        score = sum(1 for kw in kws if kw in text_upper)
        disc_scores[disc] = score
    
    detected_disc = max(disc_scores, key=disc_scores.get)
    if disc_scores[detected_disc] == 0:
        detected_disc = DrawingDiscipline.UNKNOWN
    
    # Detect structural elements
    has_table = 'TABLE' in text_upper or detect_table_structure(text_items)
    has_notes = 'NOTE' in text_upper or 'NOTES:' in text_upper
    has_legend = 'LEGEND' in text_upper or 'KEY:' in text_upper
    has_specifications = bool(re.search(r'SPEC|SPECIFICATION|REQUIREMENT', text_upper))
    
    return DrawingClassification(
        drawing_type=detected_type,
        discipline=detected_disc,
        has_table=has_table,
        has_notes=has_notes,
        has_legend=has_legend,
        has_specifications=has_specifications,
        confidence=type_scores[detected_type] / 10  # Normalize
    )

def detect_table_structure(text_items: List[Dict]) -> bool:
    """
    Detect if text is arranged in a table-like structure
    """
    # Check for aligned columns (similar x-coordinates)
    x_coords = [item['bbox']['left'] for item in text_items]
    
    # Count how many items share similar x-coordinates (within 5% tolerance)
    from collections import Counter
    x_rounded = [round(x, 1) for x in x_coords]
    counts = Counter(x_rounded)
    
    # If multiple items share x-coordinates, likely a table
    return any(count > 3 for count in counts.values())