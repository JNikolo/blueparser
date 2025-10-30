from DocTypeDetection import DrawingType
from parsers.StandarDetailsParser import StandardsDetailParser
from parsers.PumpStationParser import PumpStationParser
from extractors.TitleBlockExtractor import TitleBlockExtractor
from extractors.NotesExtractor import NotesExtractor
from extractors.SpecificationExtractor import SpecificationExtractor
from extractors.ReferenceExtractor import ReferenceExtractor
from extractors.TableExtractor import TableExtractor
from typing import List, Dict
from DocTypeDetection import classify_drawing
from Config import config


class DrawingParser:
    """
    Main parser that routes to appropriate specialized parser
    """
    
    def __init__(self):
        self.parsers = {
            DrawingType.STANDARDS_DETAIL: StandardsDetailParser(),
            DrawingType.PUMP_STATION: PumpStationParser(),
        }
        
        self.universal_extractors = [
            TitleBlockExtractor(),
            NotesExtractor(),
            SpecificationExtractor(),
            ReferenceExtractor(),
            TableExtractor()
        ]
    
    def parse(self, pdf_path: str, ocr_method: str = 'textract') -> Dict:
        """
        Main parsing method
        """
        # Step 1: OCR Extraction
        print(f"Extracting text using {ocr_method}...")
        if ocr_method == 'textract':
            ocr_results = self._extract_with_textract(pdf_path)
        else:
            ocr_results = self._extract_with_vision(pdf_path)

        text_items = ocr_results['text_items']
        full_text = ' '.join([item['text'] for item in text_items])
        
        # Step 2: Classify drawing
        print("Classifying drawing type...")
        classification = classify_drawing(full_text, text_items)
        
        print(f"Detected: {classification.drawing_type.value} "
              f"({classification.discipline.value})")
        
        # Step 3: Run universal extractors
        print("Running universal extractors...")
        universal_data = {}
        zones = self._identify_basic_zones(text_items)
        
        for extractor in self.universal_extractors:
            extractor_name = extractor.__class__.__name__.replace('Extractor', '').lower()
            try:
                universal_data[extractor_name] = extractor.extract(text_items, zones)
            except Exception as e:
                print(f"Warning: {extractor_name} failed: {e}")
                universal_data[extractor_name] = None
        
        # Step 4: Run specialized parser if available
        print("Running specialized parser...")
        specialized_data = {}
        
        if classification.drawing_type in self.parsers:
            parser = self.parsers[classification.drawing_type]
            try:
                specialized_data = parser.parse(text_items)
            except Exception as e:
                print(f"Warning: Specialized parser failed: {e}")
        
        # Step 5: Combine results
        result = {
            'classification': {
                'type': classification.drawing_type.value,
                'discipline': classification.discipline.value,
                'confidence': classification.confidence,
                'has_table': classification.has_table,
                'has_notes': classification.has_notes,
                'has_legend': classification.has_legend
            },
            'universal_data': universal_data,
            'specialized_data': specialized_data,
            'raw_ocr': ocr_results if self._include_raw() else None
        }
        
        return result
    
    def _identify_basic_zones(self, text_items: List[Dict]) -> Dict:
        """Basic zone identification for universal extractors"""
        page_height = max([item['bbox']['top'] + item['bbox'].get('height', 0) 
                          for item in text_items])
        
        zones = {
            'top': [item for item in text_items if item['bbox']['top'] < page_height * 0.15],
            'middle': [item for item in text_items if page_height * 0.15 <= item['bbox']['top'] <= page_height * 0.85],
            'bottom': [item for item in text_items if item['bbox']['top'] > page_height * 0.85]
        }
        
        return zones
    
    def _extract_with_textract(self, pdf_path: str) -> Dict:
        """
        Extract text using AWS Textract
        """

        import boto3
        from typing import BinaryIO
        
        textract = boto3.client(
            'textract',
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_DEFAULT_REGION
        )

        # Read PDF file
        with open(pdf_path, 'rb') as doc_file:
            doc_bytes = doc_file.read()
        
        # Call Textract
        try:
            response = textract.analyze_document(
                Document={'Bytes': doc_bytes},
                FeatureTypes=['TABLES', 'FORMS']
            )
        except Exception as e:
            print(f"Textract error: {e}")
            # Fallback to detect_document_text if analyze fails
            response = textract.detect_document_text(
                Document={'Bytes': doc_bytes}
            )
        
        # Parse response
        blocks = response.get('Blocks', [])
        
        text_items = []
        tables = []
        key_values = []
        
        # Process blocks
        block_map = {block['Id']: block for block in blocks}
        
        for block in blocks:
            block_type = block.get('BlockType')
            
            if block_type == 'LINE':
                # Extract line text with bounding box
                geometry = block.get('Geometry', {})
                bbox = geometry.get('BoundingBox', {})
                
                text_items.append({
                    'text': block.get('Text', ''),
                    'confidence': block.get('Confidence', 0),
                    'bbox': {
                        'left': bbox.get('Left', 0),
                        'top': bbox.get('Top', 0),
                        'width': bbox.get('Width', 0),
                        'height': bbox.get('Height', 0)
                    },
                    'page': block.get('Page', 1)
                })
            
            elif block_type == 'TABLE':
                # Parse table structure
                table_data = self._parse_textract_table(block, block_map)
                if table_data:
                    tables.append(table_data)
            
            elif block_type == 'KEY_VALUE_SET':
                # Extract key-value pairs
                if block.get('EntityTypes', [{}])[0] == 'KEY':
                    key_values.append(block)
        
        return {
            'text_items': text_items,
            'tables': tables,
            'key_values': key_values,
            'raw_response': response
        }
    
    def _parse_textract_table(self, table_block: Dict, block_map: Dict) -> Dict:
        """
        Parse Textract table block into structured format
        """
        relationships = table_block.get('Relationships', [])
        table_cells = []
        
        # Get all CELL blocks
        for relationship in relationships:
            if relationship.get('Type') == 'CHILD':
                for cell_id in relationship.get('Ids', []):
                    cell_block = block_map.get(cell_id)
                    if cell_block and cell_block.get('BlockType') == 'CELL':
                        table_cells.append(cell_block)
        
        if not table_cells:
            return None
        
        # Organize cells into rows and columns
        rows = {}
        for cell in table_cells:
            row_index = cell.get('RowIndex', 0)
            col_index = cell.get('ColumnIndex', 0)
            
            if row_index not in rows:
                rows[row_index] = {}
            
            # Get cell text
            cell_text = ''
            for relationship in cell.get('Relationships', []):
                if relationship.get('Type') == 'CHILD':
                    for word_id in relationship.get('Ids', []):
                        word_block = block_map.get(word_id)
                        if word_block and word_block.get('BlockType') == 'WORD':
                            cell_text += word_block.get('Text', '') + ' '
            
            rows[row_index][col_index] = cell_text.strip()
        
        # Convert to list format
        sorted_rows = sorted(rows.keys())
        table_data = []
        
        for row_idx in sorted_rows:
            row_data = []
            sorted_cols = sorted(rows[row_idx].keys())
            for col_idx in sorted_cols:
                row_data.append(rows[row_idx].get(col_idx, ''))
            table_data.append(row_data)
        
        if not table_data:
            return None
        
        return {
            'headers': table_data[0] if table_data else [],
            'rows': table_data[1:] if len(table_data) > 1 else [],
            'row_count': len(table_data) - 1,
            'column_count': len(table_data[0]) if table_data else 0
        }
    
    def _extract_with_vision(self, pdf_path: str) -> Dict:
        """
        Extract text using Google Cloud Vision API
        """
        from google.cloud import vision
        import io
        from pdf2image import convert_from_path
        import tempfile
        
        client = vision.ImageAnnotatorClient()
        
        # Convert PDF to images (Vision API works better with images)
        images = convert_from_path(pdf_path, dpi=300)
        
        all_text_items = []
        page_num = 1
        
        for image in images:
            # Save image to bytes
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                image.save(temp_file.name, 'PNG')
                
                with io.open(temp_file.name, 'rb') as image_file:
                    content = image_file.read()
            
            vision_image = vision.Image(content=content)
            
            # Perform text detection
            response = client.document_text_detection(image=vision_image)
            
            if response.error.message:
                raise Exception(f'Vision API error: {response.error.message}')
            
            # Parse response
            for page in response.full_text_annotation.pages:
                page_height = page.height
                page_width = page.width
                
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            # Combine word symbols into text
                            word_text = ''.join([
                                symbol.text for symbol in word.symbols
                            ])
                            
                            # Get bounding box (normalized)
                            vertices = word.bounding_box.vertices
                            
                            all_text_items.append({
                                'text': word_text,
                                'confidence': word.confidence,
                                'bbox': {
                                    'left': vertices[0].x / page_width if page_width > 0 else 0,
                                    'top': vertices[0].y / page_height if page_height > 0 else 0,
                                    'width': (vertices[1].x - vertices[0].x) / page_width if page_width > 0 else 0,
                                    'height': (vertices[2].y - vertices[0].y) / page_height if page_height > 0 else 0
                                },
                                'page': page_num
                            })
            
            page_num += 1
        
        return {
            'text_items': all_text_items,
            'tables': [],  # Vision API doesn't extract tables directly
            'key_values': [],
            'raw_response': None
        }
    
    def _include_raw(self) -> bool:
        """
        Determine whether to include raw OCR data in output
        Can be made configurable via environment variable or config file
        """
        import os
        return os.environ.get('INCLUDE_RAW_OCR', 'false').lower() == 'true'