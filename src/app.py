from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional, List
import shutil
import uuid
from datetime import datetime
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from enum import Enum

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

# Store batch job status
batch_jobs = {}

# Batch processing status enum
class BatchStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

# Thread pool for batch processing
executor = ThreadPoolExecutor(max_workers=4)


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


def process_single_file(file_path: Path, filename: str, ocr_method: str, request_id: str) -> dict:
    """
    Process a single file (used by batch processing)
    """
    try:
        # Parse the drawing
        result = parser.parse(str(file_path), ocr_method=ocr_method)
        
        # Validate
        validation = validator.validate(result)
        
        # Add validation results
        result['validation'] = {
            'is_valid': validation.is_valid,
            'errors': validation.errors,
            'warnings': validation.warnings
        }
        
        # Add metadata
        result['metadata'] = {
            'request_id': request_id,
            'filename': filename,
            'ocr_method': ocr_method,
            'processed_at': datetime.now().isoformat()
        }
        
        # Store result
        processing_results[request_id] = result
        
        return {
            'request_id': request_id,
            'filename': filename,
            'status': 'success',
            'is_valid': validation.is_valid,
            'errors': validation.errors,
            'warnings': validation.warnings
        }
        
    except Exception as e:
        return {
            'request_id': request_id,
            'filename': filename,
            'status': 'failed',
            'error': str(e)
        }
    finally:
        # Cleanup file
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            print(f"Error cleaning up {file_path}: {e}")


async def process_batch_files(batch_id: str, file_paths: List[tuple], ocr_method: str):
    """
    Process multiple files in the background
    """
    batch_jobs[batch_id]['status'] = BatchStatus.PROCESSING
    batch_jobs[batch_id]['started_at'] = datetime.now().isoformat()
    
    results = []
    total = len(file_paths)
    processed = 0
    failed = 0
    
    # Process files using thread pool
    loop = asyncio.get_event_loop()
    
    for file_path, filename, request_id in file_paths:
        result = await loop.run_in_executor(
            executor,
            process_single_file,
            file_path,
            filename,
            ocr_method,
            request_id
        )
        results.append(result)
        processed += 1
        
        if result['status'] == 'failed':
            failed += 1
        
        # Update progress
        batch_jobs[batch_id]['progress'] = {
            'total': total,
            'processed': processed,
            'succeeded': processed - failed,
            'failed': failed
        }
    
    # Determine final status
    if failed == 0:
        final_status = BatchStatus.COMPLETED
    elif failed == total:
        final_status = BatchStatus.FAILED
    else:
        final_status = BatchStatus.PARTIAL
    
    batch_jobs[batch_id]['status'] = final_status
    batch_jobs[batch_id]['results'] = results
    batch_jobs[batch_id]['completed_at'] = datetime.now().isoformat()


@app.post("/batch/parse")
async def batch_parse(
    files: List[UploadFile] = File(...),
    ocr_method: str = "textract",
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Parse multiple engineering drawings in batch
    
    - **files**: List of PDF files to parse
    - **ocr_method**: OCR method to use ('textract' or 'vision')
    
    Returns a batch_id to track the processing status
    """
    # Validate OCR method
    if ocr_method not in ['textract', 'vision']:
        raise HTTPException(status_code=400, detail="OCR method must be 'textract' or 'vision'")
    
    # Validate files
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' is not a PDF. Only PDF files are supported"
            )
    
    # Generate batch ID
    batch_id = str(uuid.uuid4())
    
    # Save all uploaded files
    file_info = []
    try:
        for file in files:
            request_id = str(uuid.uuid4())
            file_path = UPLOAD_DIR / f"{request_id}_{file.filename}"
            
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            file_info.append((file_path, file.filename, request_id))
    
    except Exception as e:
        # Cleanup on error
        for file_path, _, _ in file_info:
            if file_path.exists():
                file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save files: {str(e)}")
    
    # Initialize batch job
    batch_jobs[batch_id] = {
        'batch_id': batch_id,
        'status': BatchStatus.QUEUED,
        'total_files': len(files),
        'ocr_method': ocr_method,
        'created_at': datetime.now().isoformat(),
        'progress': {
            'total': len(files),
            'processed': 0,
            'succeeded': 0,
            'failed': 0
        }
    }
    
    # Start background processing
    background_tasks.add_task(process_batch_files, batch_id, file_info, ocr_method)
    
    return {
        'batch_id': batch_id,
        'status': BatchStatus.QUEUED,
        'total_files': len(files),
        'message': 'Batch processing started'
    }


@app.get("/batch/{batch_id}")
async def get_batch_status(batch_id: str):
    """
    Get the status of a batch processing job
    """
    if batch_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Batch job not found")
    
    return JSONResponse(content=batch_jobs[batch_id])


@app.get("/batch/{batch_id}/results")
async def get_batch_results(batch_id: str):
    """
    Get detailed results from a completed batch job
    """
    if batch_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Batch job not found")
    
    job = batch_jobs[batch_id]
    
    if job['status'] not in [BatchStatus.COMPLETED, BatchStatus.PARTIAL]:
        raise HTTPException(
            status_code=400,
            detail=f"Batch job is {job['status']}. Results available only for completed or partial jobs."
        )
    
    # Compile full results
    results = []
    for item in job.get('results', []):
        if item['status'] == 'success' and item['request_id'] in processing_results:
            results.append(processing_results[item['request_id']])
        else:
            results.append(item)
    
    return {
        'batch_id': batch_id,
        'status': job['status'],
        'summary': job['progress'],
        'results': results
    }


@app.post("/batch/{batch_id}/export")
async def export_batch_results(
    batch_id: str,
    export_format: str = "json",
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Export all results from a batch job as a single file
    
    - **batch_id**: ID of the batch job
    - **export_format**: Export format ('json' only for batch)
    """
    if batch_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Batch job not found")
    
    job = batch_jobs[batch_id]
    
    if job['status'] not in [BatchStatus.COMPLETED, BatchStatus.PARTIAL]:
        raise HTTPException(
            status_code=400,
            detail=f"Batch job is {job['status']}. Export available only for completed or partial jobs."
        )
    
    if export_format != 'json':
        raise HTTPException(
            status_code=400,
            detail="Only 'json' format is supported for batch export"
        )
    
    # Compile all results
    all_results = {
        'batch_id': batch_id,
        'summary': {
            'total_files': job['total_files'],
            'status': job['status'],
            'progress': job['progress'],
            'created_at': job['created_at'],
            'completed_at': job.get('completed_at')
        },
        'files': []
    }
    
    for item in job.get('results', []):
        if item['status'] == 'success' and item['request_id'] in processing_results:
            all_results['files'].append(processing_results[item['request_id']])
        else:
            all_results['files'].append(item)
    
    # Save to file
    output_file = OUTPUT_DIR / f"batch_{batch_id}_results.json"
    
    try:
        with output_file.open('w') as f:
            json.dump(all_results, f, indent=2)
        
        background_tasks.add_task(cleanup_file, output_file)
        
        return FileResponse(
            path=output_file,
            media_type="application/json",
            filename=output_file.name
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.delete("/batch/{batch_id}")
async def delete_batch(batch_id: str):
    """
    Delete a batch job and all associated results
    """
    if batch_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Batch job not found")
    
    # Delete individual results
    job = batch_jobs[batch_id]
    if 'results' in job:
        for item in job['results']:
            if item['status'] == 'success' and item['request_id'] in processing_results:
                del processing_results[item['request_id']]
    
    # Delete batch job
    del batch_jobs[batch_id]
    
    return {"message": "Batch job deleted successfully", "batch_id": batch_id}


@app.get("/batch")
async def list_batch_jobs():
    """
    List all batch jobs
    """
    jobs_summary = []
    for batch_id, job in batch_jobs.items():
        jobs_summary.append({
            'batch_id': batch_id,
            'status': job['status'],
            'total_files': job['total_files'],
            'progress': job['progress'],
            'created_at': job['created_at']
        })
    
    return {'total_batches': len(jobs_summary), 'batches': jobs_summary}


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
            "cached_results": len(processing_results),
            "active_batch_jobs": len(batch_jobs)
        },
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
