import re
from typing import List, Dict
from extractors.TitleBlockExtractor import TitleBlockExtractor
from extractors.NotesExtractor import NotesExtractor
from extractors.SpecificationExtractor import SpecificationExtractor
from extractors.ReferenceExtractor import ReferenceExtractor

class PumpStationParser:
    """Parser for pump station drawings"""
    
    def __init__(self):
        self.title_extractor = TitleBlockExtractor()
        self.notes_extractor = NotesExtractor()
        self.spec_extractor = SpecificationExtractor()
        self.ref_extractor = ReferenceExtractor()
    
    def parse(self, text_items: List[Dict]) -> Dict:
        zones = self._identify_zones(text_items)
        
        return {
            'document_type': 'pump_station',
            'title_block': self.title_extractor.extract(text_items, zones),
            'pump_data': self._extract_pump_data(text_items, zones),
            'components': self._extract_components(text_items, zones),
            'elevations': self._extract_elevations(text_items, zones),
            'notes': self.notes_extractor.extract(text_items, zones),
            'specifications': self.spec_extractor.extract(text_items, zones),
            'references': self.ref_extractor.extract(text_items, zones)
        }
    
    def _identify_zones(self, text_items: List[Dict]) -> Dict:
        """
        Identify different zones in pump station drawing
        """
        zones = {
            'key_section': [],      # Numbered KEY items (1-55)
            'pump_data_box': [],    # PUMP STATION DATA box
            'elevation_labels': [], # Control elevation markers
            'title_block': [],      # Bottom area
            'general': []           # Everything else
        }
        
        # Calculate page dimensions
        max_x = max([item['bbox']['left'] + item['bbox'].get('width', 0) 
                    for item in text_items])
        max_y = max([item['bbox']['top'] + item['bbox'].get('height', 0) 
                    for item in text_items])
        
        for item in text_items:
            text = item['text'].strip()
            bbox = item['bbox']
            
            # KEY section - typically top-left, numbered items
            if re.match(r'^\d+\.\s+', text) or text == 'KEY:':
                zones['key_section'].append(item)
            
            # PUMP STATION DATA - typically right side
            elif bbox['left'] > max_x * 0.65:  # Right 35%
                if any(keyword in text.upper() for keyword in 
                      ['PUMP', 'GPM', 'HP', 'TDH', 'VOLTS', 'AMPS', 'RPM', 
                       'MODEL', 'SERIAL', 'DESIGN', 'STATIC HEAD']):
                    zones['pump_data_box'].append(item)
                else:
                    zones['general'].append(item)
            
            # Elevation labels
            elif 'EL' in text.upper() or 'ELEVATION' in text.upper():
                if any(keyword in text.upper() for keyword in 
                      ['ALARM', 'LAG', 'LEAD', 'OVERRIDE', 'BOTTOM', 
                       'TOP', 'INVERT', 'LWL']):
                    zones['elevation_labels'].append(item)
                else:
                    zones['general'].append(item)
            
            # Title block - bottom 15%
            elif bbox['top'] > max_y * 0.85:
                zones['title_block'].append(item)
            
            else:
                zones['general'].append(item)
        
        return zones
    
    def _extract_pump_data(self, text_items: List[Dict], zones: Dict) -> Dict:
        """
        Extract pump specifications from PUMP STATION DATA box
        """
        pump_data = {
            'model': None,
            'serial_number': None,
            'design_capacity_gpm': None,
            'design_tdh': None,
            'horsepower': None,
            'phase': None,
            'impeller_number': None,
            'impeller_diameter': None,
            'voltage': None,
            'amperage': None,
            'shut_off_head': None,
            'speed_rpm': None,
            'static_head': None,
            'wetwell_volume_gallons': None,
            'wetwell_diameter': None
        }
        
        # Combine text from pump data zone
        pump_text_items = zones.get('pump_data_box', [])
        if not pump_text_items:
            # Fallback: search all text
            pump_text_items = text_items
        
        full_text = ' '.join([item['text'] for item in pump_text_items])
        
        # Pattern matching for each field
        patterns = {
            'model': [
                r'PUMP MODEL[:\s]+([A-Z0-9\s-]+?)(?:\n|$)',
                r'MODEL[:\s]+([A-Z0-9\s-]+?)(?:\n|$)'
            ],
            'serial_number': [
                r'PUMP SERIAL NO[.:\s]+([A-Z0-9-]+)',
                r'SERIAL NO[.:\s]+([A-Z0-9-]+)'
            ],
            'design_capacity_gpm': [
                r'DESIGN CAPACITY[:\s]+(\d+)\s*GPM',
                r'PUMP DESIGN POINT[:\s]+(\d+)\s*GPM',
                r'(\d+)\s*GPM\s*@'
            ],
            'design_tdh': [
                r'(\d+)\s*TDH',
                r'@\s*(\d+)\s*TDH',
                r'GPM\s*@\s*(\d+)'
            ],
            'horsepower': [
                r'PUMP H\.?P\.?[:\s]+(\d+\.?\d*)',
                r'(\d+\.?\d*)\s*HP',
                r'(\d+\.?\d*)\s*PHASE'  # Sometimes HP is before PHASE
            ],
            'phase': [
                r'(\d+)\s*PHASE',
                r'PHASE[:\s]+(\d+)'
            ],
            'impeller_number': [
                r'PUMP IMP\.? NO[.:\s/]+([A-Z0-9-]+)',
                r'IMP\.?\s*NO[.:\s]+([A-Z0-9-]+)'
            ],
            'impeller_diameter': [
                r'IMP\.?[:\s/]+([0-9.]+)\s*(?:DIA|")',
                r'DIA[.:\s]+([0-9.]+)'
            ],
            'voltage': [
                r'PUMP VOLTS[:\s]+(\d+)',
                r'(\d+)\s*VOLTS',
                r'(\d+)V'
            ],
            'amperage': [
                r'(\d+\.?\d*)\s*AMPS',
                r'AMPS[:\s]+(\d+\.?\d*)'
            ],
            'shut_off_head': [
                r'SHUT[- ]OFF HEAD[:\s]+(\d+)',
                r'SHUT[- ]OFF[:\s]+(\d+)\s*FT'
            ],
            'speed_rpm': [
                r'PUMP SPEED[:\s]+(\d+)\s*RPM',
                r'(\d+)\s*RPM'
            ],
            'static_head': [
                r'STATIC HEAD[:\s]+(\d+)',
                r'STATIC[:\s]+(\d+)\s*FT'
            ],
            'wetwell_volume_gallons': [
                r'WET WELL VOLUME[:\s]+(\d+)\s*GALLONS',
                r'VOLUME[:\s]+(\d+)\s*GAL'
            ],
            'wetwell_diameter': [
                r'(\d+)\s*FT\.?\s*DIA',
                r'(\d+)[\'"]?\s*DIA\.?\s*WETWELL',
                r'DIA\.?\s*WETWELL[:\s]+(\d+)'
            ]
        }
        
        # Extract each field
        for field, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    # Clean up extracted value
                    if value and not value.isspace():
                        pump_data[field] = value
                        break  # Found match, move to next field
        
        # Special handling for horsepower (might be before PHASE)
        if pump_data['horsepower'] and pump_data['phase']:
            # Check if we accidentally captured phase number as HP
            if pump_data['horsepower'] == pump_data['phase']:
                # Try to find HP separately
                hp_match = re.search(r'(\d+\.?\d*)\s*HP', full_text, re.IGNORECASE)
                if hp_match:
                    pump_data['horsepower'] = hp_match.group(1)
        
        return pump_data
    
    def _extract_components(self, text_items: List[Dict], zones: Dict) -> List[Dict]:
        """
        Extract component list from KEY section
        """
        components = []
        
        key_items = zones.get('key_section', [])
        
        # Sort by vertical position (top to bottom)
        sorted_items = sorted(key_items, key=lambda x: x['bbox']['top'])
        
        # Group items that are close together (same component description)
        current_component = None
        current_text_parts = []
        last_y = None
        
        for item in sorted_items:
            text = item['text'].strip()
            current_y = item['bbox']['top']
            
            # Check if this is a new numbered item
            item_match = re.match(r'^(\d+)\.\s+(.+)', text)
            
            if item_match:
                # Save previous component if exists
                if current_component and current_text_parts:
                    full_description = ' '.join(current_text_parts)
                    component = self._parse_component_description(
                        current_component, full_description
                    )
                    components.append(component)
                
                # Start new component
                current_component = item_match.group(1)
                current_text_parts = [item_match.group(2)]
                last_y = current_y
            
            elif current_component and last_y and abs(current_y - last_y) < 0.02:
                # Continuation of previous line (within 2% of page height)
                current_text_parts.append(text)
                last_y = current_y
            
            elif 'KEY' in text.upper():
                # Skip "KEY:" header
                continue
        
        # Don't forget the last component
        if current_component and current_text_parts:
            full_description = ' '.join(current_text_parts)
            component = self._parse_component_description(
                current_component, full_description
            )
            components.append(component)
        
        return components
    
    def _parse_component_description(self, item_number: str, 
                                    description: str) -> Dict:
        """
        Parse a single component description to extract details
        """
        component = {
            'item_number': item_number,
            'description': description,
            'size': None,
            'size_variable': False,
            'material': None,
            'type': None,
            'quantity': None,
            'manufacturer': None
        }
        
        # Extract size
        # Pattern: __" (variable size)
        if '__"' in description or '_ _"' in description:
            component['size_variable'] = True
            component['size'] = 'Variable'
        else:
            # Fixed size: 4", 1/2", 6", etc.
            size_match = re.search(r'(\d+\.?\d*(?:/\d+)?)["\']', description)
            if size_match:
                component['size'] = size_match.group(1) + '"'
        
        # Extract material abbreviations
        materials = []
        material_map = {
            'FG': 'Flanged',
            'DI': 'Ductile Iron',
            'SS': 'Stainless Steel',
            '316L SS': '316L Stainless Steel',
            '316 SS': '316 Stainless Steel',
            'PVC': 'PVC',
            'HDPE': 'HDPE',
            'PE': 'Polyethylene',
            'PVCC': 'PVCC',
            'MJ': 'Mechanical Joint',
            'BRASS': 'Brass',
            'ALUMINUM': 'Aluminum',
            'GALV': 'Galvanized'
        }
        
        for abbr, full_name in material_map.items():
            if abbr in description.upper():
                materials.append(full_name)
        
        component['material'] = ', '.join(materials) if materials else None
        
        # Extract component type
        type_keywords = {
            'PUMP': 'Pump',
            'VALVE': 'Valve',
            'GATE VALVE': 'Gate Valve',
            'BALL VALVE': 'Ball Valve',
            'CHECK VALVE': 'Check Valve',
            'PLUG VALVE': 'Plug Valve',
            'BEND': 'Bend/Elbow',
            'ELBOW': 'Elbow',
            'TEE': 'Tee',
            'REDUCER': 'Reducer',
            'FLANGE': 'Flange',
            'NIPPLE': 'Nipple',
            'COUPLING': 'Coupling',
            'BUSHING': 'Bushing',
            'PIPE': 'Pipe',
            'GAUGE': 'Gauge',
            'TRANSMITTER': 'Transmitter',
            'TRANSDUCER': 'Transducer',
            'FLOAT SWITCH': 'Float Switch',
            'HATCH': 'Hatch',
            'SUPPORT': 'Support',
            'BOLT': 'Bolt',
            'CABLE': 'Cable',
            'RAIL': 'Rail'
        }
        
        for keyword, type_name in type_keywords.items():
            if keyword in description.upper():
                component['type'] = type_name
                break
        
        # Extract quantity
        qty_patterns = [
            r'\((\d+)\s*REQ\.?\)',
            r'\((\d+)\s*REQUIRED\)',
            r'(\d+)\s*REQ\.?',
            r'QTY[:\s]+(\d+)'
        ]
        
        for pattern in qty_patterns:
            qty_match = re.search(pattern, description, re.IGNORECASE)
            if qty_match:
                component['quantity'] = qty_match.group(1)
                break
        
        if not component['quantity']:
            component['quantity'] = '1'  # Default to 1 if not specified
        
        # Extract manufacturer (if mentioned)
        manufacturer_patterns = [
            r'HYDROMATIC',
            r'MANUFACTURER',
            r'MFR'
        ]
        
        for pattern in manufacturer_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                mfr_match = re.search(r'([A-Z][A-Z\s]+)(?:OR|,|\()', description)
                if mfr_match:
                    component['manufacturer'] = mfr_match.group(1).strip()
                break
        
        return component
    
    def _extract_elevations(self, text_items: List[Dict], zones: Dict) -> Dict:
        """
        Extract control elevation settings
        """
        elevations = {
            'top_el': None,
            'high_high_alarm_el': None,
            'high_alarm_el': None,
            'override_on_el': None,
            'lag_on_el': None,
            'lead_on_el': None,
            'override_off_el': None,
            'all_pumps_off_el': None,
            'bottom_el': None,
            'invert_el': None,
            'drop_invert_el': None,
            'low_water_level': None
        }
        
        # Combine elevation zone text
        elevation_items = zones.get('elevation_labels', [])
        if not elevation_items:
            # Fallback: search all text
            elevation_items = text_items
        
        full_text = ' '.join([item['text'] for item in elevation_items])
        
        # Patterns for each elevation type
        patterns = {
            'top_el': [
                r'TOP EL\.?[:\s]+([\d.]+)',
                r'TOP ELEVATION[:\s]+([\d.]+)'
            ],
            'high_high_alarm_el': [
                r'HI[/\s]*HI ALARM EL\.?[:\s]+([\d.]+|__)',
                r'HIGH[/\s]*HIGH ALARM EL\.?[:\s]+([\d.]+|__)',
                r'H[/]?H ALARM[:\s]+([\d.]+|__)'
            ],
            'high_alarm_el': [
                r'HIGH ALARM EL\.?[:\s]+([\d.]+|__)',
                r'HIGH ALARM[:\s]+([\d.]+|__)',
                r'HI ALARM[:\s]+([\d.]+|__)'
            ],
            'override_on_el': [
                r'OVERRIDE ON EL\.?[:\s]+([\d.]+|__)',
                r'OVERRIDE ON[:\s]+([\d.]+|__)'
            ],
            'lag_on_el': [
                r'LAG ON EL\.?[:\s]+([\d.]+|__)',
                r'LAG ON[:\s]+([\d.]+|__)'
            ],
            'lead_on_el': [
                r'LEAD ON EL\.?[:\s]+([\d.]+|__)',
                r'LEAD ON[:\s]+([\d.]+|__)'
            ],
            'override_off_el': [
                r'OVERRIDE OFF EL\.?[:\s]+([\d.]+|__)',
                r'OVERRIDE OFF[:\s]+([\d.]+|__)'
            ],
            'all_pumps_off_el': [
                r'ALL PUMPS OFF EL\.?[:\s]+([\d.]+|__)',
                r'PUMPS OFF EL\.?[:\s]+([\d.]+|__)',
                r'PUMPS OFF[:\s]+([\d.]+|__)'
            ],
            'bottom_el': [
                r'BOTTOM EL\.?[:\s]+([\d.]+|__)',
                r'BOTTOM ELEVATION[:\s]+([\d.]+|__)'
            ],
            'invert_el': [
                r'INVERT EL\.?[:\s]+([\d.]+|__)',
                r'INV EL\.?[:\s]+([\d.]+|__)',
                r'INVERT ELEVATION[:\s]+([\d.]+|__)'
            ],
            'drop_invert_el': [
                r'DROP INVERT EL\.?[:\s]+([\d.]+|__)',
                r'DROP INV EL\.?[:\s]+([\d.]+|__)'
            ],
            'low_water_level': [
                r'LWL[:\s]+([\d.]+)',
                r'LOW WATER LEVEL[:\s]+([\d.]+)'
            ]
        }
        
        # Extract each elevation
        for field, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    # Keep '__' as placeholder for to-be-determined values
                    elevations[field] = value if value != '__' else 'TBD'
                    break
        
        return elevations