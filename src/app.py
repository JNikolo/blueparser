from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import uuid
from datetime import datetime
from Config import config

from DrawingParser import DrawingParser
from DrawingValidator import DrawingValidator

app = FastAPI(
    title="BlueParser API",
    description="API for parsing and analyzing engineering drawings",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
parser = DrawingParser()
validator = DrawingValidator()

# Setup paths
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def cleanup_file(file_path: Path):
    """Background task to cleanup uploaded files"""
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        print(f"Error cleaning up {file_path}: {e}")


@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "online",
        "service": "BlueParser API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/parse")
async def parse_drawing(
    file: UploadFile = File(...),
    ocr_method: str = "textract",
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Parse an engineering drawing PDF and return results
    
    - **file**: PDF file to parse
    - **ocr_method**: OCR method to use ('textract' or 'vision')
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Validate OCR method
    if ocr_method not in ['textract', 'vision']:
        raise HTTPException(status_code=400, detail="OCR method must be 'textract' or 'vision'")
    
    # Generate unique filename for temporary storage
    temp_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = UPLOAD_DIR / temp_filename
    
    try:
        # Save uploaded file temporarily
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    try:
        # Parse the drawing
        result = parser.parse(str(file_path), ocr_method=ocr_method)
        
        # Validate the result
        validation = validator.validate(result)
        
        # Transform to LLM-friendly format
        llm_friendly_result = _transform_for_llm(result, validation, file.filename)
        
        # Schedule cleanup of uploaded file
        background_tasks.add_task(cleanup_file, file_path)
        
        return JSONResponse(content=llm_friendly_result)
        
    except Exception as e:
        # Cleanup on error
        background_tasks.add_task(cleanup_file, file_path)
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")


def _transform_for_llm(result: dict, validation, filename: str) -> dict:
    """
    Transform parser output into an LLM-friendly format with:
    - Natural language summaries
    - Clear hierarchical structure
    - Contextual information
    - Easy-to-query format
    """
    classification = result.get('classification', {})
    universal_data = result.get('universal_data', {})
    specialized_data = result.get('specialized_data', {})
    
    # Build natural language summary
    drawing_type = classification.get('type', 'unknown').replace('_', ' ').title()
    discipline = classification.get('discipline', 'unknown').title()
    
    summary_parts = [
        f"This is a {drawing_type} drawing from the {discipline} discipline."
    ]
    
    if classification.get('has_table'):
        summary_parts.append("It contains tabular data.")
    if classification.get('has_notes'):
        summary_parts.append("It includes construction notes and specifications.")
    if classification.get('has_legend'):
        summary_parts.append("It has a legend or symbol key.")
    
    # Extract title block info
    titleblock = universal_data.get('titleblock', {})
    if titleblock:
        if titleblock.get('drawing_number'):
            summary_parts.append(f"Drawing number: {titleblock['drawing_number']}.")
        if titleblock.get('drawing_title'):
            summary_parts.append(f"Title: {titleblock['drawing_title']}.")
    
    # Process notes into structured format
    notes_data = universal_data.get('notes', [])
    structured_notes = {
        'numbered_notes': [],
        'general_notes': [],
        'count': len(notes_data)
    }
    
    for note in notes_data:
        note_entry = {
            'content': note.get('content', ''),
            'type': note.get('type', 'general')
        }
        if note.get('number'):
            note_entry['number'] = note['number']
            structured_notes['numbered_notes'].append(note_entry)
        else:
            structured_notes['general_notes'].append(note_entry)
    
    # Process specifications into grouped format
    specs_data = universal_data.get('specification', [])
    specifications = {
        'measurements': [],
        'materials': [],
        'standards': [],
        'count': len(specs_data)
    }
    
    for spec in specs_data:
        if spec.get('type') == 'measurement':
            specifications['measurements'].append({
                'value': spec.get('value'),
                'unit': spec.get('unit'),
                'context': spec.get('context', ''),
                'full_text': f"{spec.get('value')}{spec.get('unit')} - {spec.get('context', '')}"
            })
        elif spec.get('type') == 'material':
            specifications['materials'].append({
                'material': spec.get('material'),
                'specification': spec.get('specification', ''),
                'context': spec.get('context', '')
            })
        elif spec.get('type') == 'standard':
            specifications['standards'].append({
                'standard': spec.get('standard'),
                'context': spec.get('context', '')
            })
    
    # Process references
    references = universal_data.get('reference', [])
    structured_references = []
    for ref in references:
        structured_references.append({
            'type': ref.get('type', 'unknown'),
            'reference': ref.get('reference', ''),
            'context': ref.get('context', '')
        })
    
    # Process tables
    tables = universal_data.get('table', [])
    structured_tables = []
    for table in tables:
        structured_tables.append({
            'headers': table.get('headers', []),
            'rows': table.get('rows', []),
            'row_count': len(table.get('rows', [])),
            'column_count': len(table.get('headers', []))
        })
    
    # Build the LLM-friendly response
    llm_response = {
        'document_summary': {
            'filename': filename,
            'drawing_type': drawing_type,
            'discipline': discipline,
            'confidence': classification.get('confidence', 0),
            'processing_timestamp': datetime.now().isoformat(),
            'natural_language_summary': ' '.join(summary_parts)
        },
        'drawing_information': {
            'drawing_number': titleblock.get('drawing_number'),
            'title': titleblock.get('drawing_title'),
            'date': titleblock.get('date'),
            'scale': titleblock.get('scale'),
            'revision': titleblock.get('revision'),
            'sheet_number': titleblock.get('sheet_number')
        },
        'construction_notes': structured_notes,
        'specifications': specifications,
        'references': {
            'items': structured_references,
            'count': len(structured_references)
        },
        'tables': {
            'items': structured_tables,
            'count': len(structured_tables)
        },
        'specialized_content': specialized_data,
        'validation': {
            'is_valid': validation.is_valid,
            'errors': validation.errors if validation.errors else [],
            'warnings': validation.warnings if validation.warnings else [],
            'error_count': len(validation.errors) if validation.errors else 0,
            'warning_count': len(validation.warnings) if validation.warnings else 0
        },
        'query_tips': {
            'description': 'Tips for querying this data with an LLM',
            'tips': [
                'Ask about specific measurements or dimensions',
                'Query construction requirements and standards',
                'Request summaries of notes or specifications',
                'Ask about drawing metadata (number, date, revision)',
                'Inquire about materials or equipment specifications',
                'Ask for clarification on technical references'
            ]
        }
    }
    
    return llm_response


@app.get("/health")
async def health_check():
    """
    Detailed health check
    """
    return {
        "status": "healthy",
        "components": {
            "parser": "ready",
            "validator": "ready"
        },
        "storage": {
            "upload_dir": str(UPLOAD_DIR)
        },
        "timestamp": datetime.now().isoformat()
    }
