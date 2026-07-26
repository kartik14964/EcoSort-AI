from backend.schemas import *
import os
import cv2
import uuid
import base64
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Query, HTTPException, status, Depends
from fastapi.responses import FileResponse
import gc
from backend.database import Repository
from backend.ai_services import detector_service
from backend.ai_services import RecommendationEngine
from backend.ai_services import AIAssistantService
from backend.utils import ReportGenerator
from backend.utils import settings
from backend.utils import setup_logger
from backend.auth import get_current_user

logger = setup_logger("api_routes")
router = APIRouter()

@router.get("/settings")
def get_settings(current_user: str = Depends(get_current_user)):
    """Retrieve current system configuration and emission factors."""
    return Repository.get_settings()

@router.put("/settings")
def update_settings(payload: SettingsUpdate, current_user: str = Depends(get_current_user)):
    """Modify system thresholds, camera sources, and carbon factors."""
    update_data = {}
    if payload.detection_threshold is not None:
        update_data["detection_threshold"] = payload.detection_threshold
    if payload.camera_source is not None:
        update_data["camera_source"] = payload.camera_source
    if payload.co2_factors is not None:
        update_data["co2_factors"] = payload.co2_factors
        
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid settings fields provided for update.")
        
    return Repository.update_settings(update_data)

@router.post("/detect/image")
async def detect_image(file: UploadFile = File(...), threshold: Optional[float] = Query(None, ge=0.0, le=1.0), current_user: str = Depends(get_current_user)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png"]:
        raise HTTPException(status_code=400, detail="Only JPG, JPEG, and PNG images are supported.")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    temp_filename = f"upload_{uuid.uuid4()}{ext}"
    temp_path = os.path.join(settings.UPLOAD_DIR, temp_filename)

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(temp_path, "wb") as f:
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
        del contents
        gc.collect()

        logger.info(f"Saved: {temp_path}, size: {os.path.getsize(temp_path)} bytes")

        test_read = cv2.imread(temp_path)
        if test_read is None:
            raise HTTPException(status_code=400, detail="Could not decode image. Try JPG or PNG.")
        del test_read
        gc.collect()

        sys_settings = Repository.get_settings()
        co2_factors = sys_settings.get("co2_factors", settings.CO2_SAVINGS_FACTORS)
        if threshold is None:
            threshold = sys_settings.get("detection_threshold", settings.DETECTION_THRESHOLD)
        threshold = float(threshold)

        logger.info(f"Running detection with threshold: {threshold}")
        annotated_img, detections = detector_service.detect_objects(temp_path, threshold)
        detections = [det for det in detections if float(det["confidence"]) >= threshold]
        logger.info(f"Detection complete. Found {len(detections)} items.")

        saved_detections = []
        for det in detections:
            rec = RecommendationEngine.get_recommendation(det["object_name"], det["category"])
            factor = co2_factors.get(det["category"], 0.1)
            det["disposal_method"] = rec["disposal_method"]
            det["recycling_possibility"] = rec["recycling_possibility"]
            det["bin_color"] = rec["bin_color"]
            det["special_instructions"] = rec.get("special_instructions", "")
            det["carbon_saved_kg"] = round(factor * 0.25, 3)
            det["image_path"] = ""
            saved_detections.append(det)

        success, buffer = cv2.imencode('.jpg', annotated_img)
        del annotated_img
        gc.collect()

        if not success or buffer is None:
            raise HTTPException(status_code=500, detail="Failed to encode image.")

        img_base64 = base64.b64encode(buffer).decode('utf-8')
        del buffer
        gc.collect()

        return {
            "detections": saved_detections,
            "annotated_image_b64": img_base64,
            "annotated_image_path": ""
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Full error:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Image detection failed: {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        gc.collect()
        
@router.get("/detections")
def get_detections(
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: str = Depends(get_current_user)
):
    """Fetch recent waste detections with optional category filtering."""
    filters = {"username": current_user}
    if category:
        filters["category"] = category
        
    results = Repository.get_detections(filters=filters, limit=limit)
    
    # Convert ObjectIds to strings
    for r in results:
        if "_id" in r:
            r["_id"] = str(r["_id"])
    return results

@router.get("/analytics/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(days: int = Query(30, ge=1, le=365), current_user: str = Depends(get_current_user)):
    """Retrieve summarized KPIs for home page metrics cards."""
    return Repository.get_analytics_summary(days=days, username=current_user)

@router.post("/chatbot", response_model=ChatResponse)
def run_chatbot(payload: ChatRequest, current_user: str = Depends(get_current_user)):
    """Ask natural language analytical questions about waste and sustainability trends."""
    reply = AIAssistantService.answer_query(payload.message)
    # Provide helpful contextual suggestions
    actions = [
        "How much plastic was detected this week?",
        "What is our recycling rate?",
        "How much CO2 did we save?",
        "Which waste category is increasing?"
    ]
    return ChatResponse(reply=reply, suggested_actions=actions)

@router.post("/reports/generate", response_model=ReportGenerateResponse)
def generate_report(payload: ReportGenerateRequest, current_user: str = Depends(get_current_user)):
    """Generate a high-quality PDF report for download."""
    try:
        pdf_path = ReportGenerator.generate_pdf(payload.timeframe_days)
        filename = os.path.basename(pdf_path)
        return ReportGenerateResponse(
            report_id=filename,
            pdf_url=f"/api/reports/download/{filename}",
            summary=f"Successfully generated a {payload.timeframe_days}-day sustainability report."
        )
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}")

@router.get("/reports/download/{filename}")
def download_report(filename: str, current_user: str = Depends(get_current_user)):
    """Serve generated PDF reports for user download."""
    safe_name = os.path.basename(filename)
    filepath = os.path.join(settings.REPORTS_DIR, safe_name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Requested report PDF file does not exist.")
    return FileResponse(filepath, media_type="application/pdf", filename=safe_name)


@router.post("/detections/save")
async def save_detections(payload: dict, current_user: str = Depends(get_current_user)):
    """Explicitly save pre-detected items to the database."""
    detections = payload.get("detections", [])
    if not detections:
        raise HTTPException(status_code=400, detail="No detections provided.")
    
    sys_settings = Repository.get_settings()
    co2_factors = sys_settings.get("co2_factors", settings.CO2_SAVINGS_FACTORS)
    
    saved = []
    for det in detections:
        rec = RecommendationEngine.get_recommendation(det["object_name"], det["category"])
        factor = co2_factors.get(det["category"], 0.1)
        carbon_saved = round(factor * 0.25, 3)
        
        db_record = {
            "username": current_user,
            "timestamp": datetime.utcnow(),
            "object_name": det["object_name"],
            "confidence": float(det["confidence"]),
            "category": det["category"],
            "disposal_method": rec["disposal_method"],
            "recycling_possibility": rec["recycling_possibility"],
            "bin_color": rec["bin_color"],
            "special_instructions": rec.get("special_instructions", ""),
            "carbon_saved_kg": carbon_saved,
            "image_path": det.get("image_path", "")
        }
        saved_rec = Repository.insert_detection(db_record)
        if saved_rec:
            saved_rec["_id"] = str(saved_rec["_id"])
            saved.append(saved_rec)
    
    return {"saved": saved, "count": len(saved)}