from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional
import shutil
import uuid
from datetime import datetime
import json

from DrawingParser import DrawingParser
from DrawingValidator import DrawingValidator
from DataExporter import DataExporter

app = FastAPI(
    title="BlueParser API",
    description="API for parsing and analyzing engineering drawings",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
parser = DrawingParser()
validator = DrawingValidator()
exporter = DataExporter()

# Setup paths
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Store processing results
processing_results = {}


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
    Parse an engineering drawing PDF
    
    - **file**: PDF file to parse
    - **ocr_method**: OCR method to use ('textract' or 'vision')
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Validate OCR method
    if ocr_method not in ['textract', 'vision']:
        raise HTTPException(status_code=400, detail="OCR method must be 'textract' or 'vision'")
    
    # Generate unique ID for this request
    request_id = str(uuid.uuid4())
    
    # Save uploaded file
    file_path = UPLOAD_DIR / f"{request_id}_{file.filename}"
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    try:
        # Parse the drawing
        result = parser.parse(str(file_path), ocr_method=ocr_method)
        
        # Validate the result
        validation = validator.validate(result)
        
        # Add validation results to response
        result['validation'] = {
            'is_valid': validation.is_valid,
            'errors': validation.errors,
            'warnings': validation.warnings
        }
        
        # Add metadata
        result['metadata'] = {
            'request_id': request_id,
            'filename': file.filename,
            'ocr_method': ocr_method,
            'processed_at': datetime.now().isoformat()
        }
        
        # Store result
        processing_results[request_id] = result
        
        # Schedule cleanup of uploaded file
        background_tasks.add_task(cleanup_file, file_path)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        # Cleanup on error
        background_tasks.add_task(cleanup_file, file_path)
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")


@app.post("/parse-and-export")
async def parse_and_export(
    file: UploadFile = File(...),
    ocr_method: str = "textract",
    export_format: str = "json",
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Parse a drawing and export to specified format
    
    - **file**: PDF file to parse
    - **ocr_method**: OCR method to use ('textract' or 'vision')
    - **export_format**: Export format ('json', 'csv', or 'excel')
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Validate export format
    if export_format not in ['json', 'csv', 'excel']:
        raise HTTPException(status_code=400, detail="Export format must be 'json', 'csv', or 'excel'")
    
    # Generate unique ID
    request_id = str(uuid.uuid4())
    
    # Save uploaded file
    file_path = UPLOAD_DIR / f"{request_id}_{file.filename}"
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    try:
        # Parse the drawing
        result = parser.parse(str(file_path), ocr_method=ocr_method)
        
        # Validate
        validation = validator.validate(result)
        result['validation'] = {
            'is_valid': validation.is_valid,
            'errors': validation.errors,
            'warnings': validation.warnings
        }
        
        # Export based on format
        base_name = Path(file.filename).stem
        
        if export_format == 'json':
            output_file = OUTPUT_DIR / f"{request_id}_{base_name}.json"
            exporter.to_json(result, output_file)
            media_type = "application/json"
            
        elif export_format == 'csv':
            output_file = OUTPUT_DIR / f"{request_id}_{base_name}.csv"
            exporter.to_csv(result, output_file)
            media_type = "text/csv"
            
        else:  # excel
            output_file = OUTPUT_DIR / f"{request_id}_{base_name}.xlsx"
            exporter.to_excel(result, output_file)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_file, file_path)
        background_tasks.add_task(cleanup_file, output_file)
        
        return FileResponse(
            path=output_file,
            media_type=media_type,
            filename=output_file.name
        )
        
    except Exception as e:
        background_tasks.add_task(cleanup_file, file_path)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/result/{request_id}")
async def get_result(request_id: str):
    """
    Retrieve a previously processed result by request ID
    """
    if request_id not in processing_results:
        raise HTTPException(status_code=404, detail="Result not found")
    
    return JSONResponse(content=processing_results[request_id])


@app.get("/export/{request_id}")
async def export_result(
    request_id: str,
    format: str = "json",
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Export a previously processed result
    
    - **request_id**: ID from previous parse request
    - **format**: Export format ('json', 'csv', or 'excel')
    """
    if request_id not in processing_results:
        raise HTTPException(status_code=404, detail="Result not found")
    
    if format not in ['json', 'csv', 'excel']:
        raise HTTPException(status_code=400, detail="Format must be 'json', 'csv', or 'excel'")
    
    result = processing_results[request_id]
    filename = result['metadata']['filename']
    base_name = Path(filename).stem
    
    try:
        if format == 'json':
            output_file = OUTPUT_DIR / f"{request_id}_{base_name}.json"
            exporter.to_json(result, output_file)
            media_type = "application/json"
            
        elif format == 'csv':
            output_file = OUTPUT_DIR / f"{request_id}_{base_name}.csv"
            exporter.to_csv(result, output_file)
            media_type = "text/csv"
            
        else:  # excel
            output_file = OUTPUT_DIR / f"{request_id}_{base_name}.xlsx"
            exporter.to_excel(result, output_file)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
        background_tasks.add_task(cleanup_file, output_file)
        
        return FileResponse(
            path=output_file,
            media_type=media_type,
            filename=output_file.name
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.delete("/result/{request_id}")
async def delete_result(request_id: str):
    """
    Delete a stored result
    """
    if request_id not in processing_results:
        raise HTTPException(status_code=404, detail="Result not found")
    
    del processing_results[request_id]
    
    return {"message": "Result deleted successfully", "request_id": request_id}


@app.get("/health")
async def health_check():
    """
    Detailed health check
    """
    return {
        "status": "healthy",
        "components": {
            "parser": "ready",
            "validator": "ready",
            "exporter": "ready"
        },
        "storage": {
            "upload_dir": str(UPLOAD_DIR),
            "output_dir": str(OUTPUT_DIR),
            "cached_results": len(processing_results)
        },
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
