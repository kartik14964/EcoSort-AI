from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class SettingsUpdate(BaseModel):
    detection_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    camera_source: Optional[str] = None
    co2_factors: Optional[Dict[str, float]] = None

class DetectionCreate(BaseModel):
    object_name: str
    confidence: float
    category: str
    disposal_method: str
    recycling_possibility: float
    bin_color: str
    special_instructions: Optional[str] = None
    carbon_saved_kg: float
    image_path: Optional[str] = ""

class DetectionResponse(BaseModel):
    id: str = Field(alias="_id")
    timestamp: datetime
    object_name: str
    confidence: float
    category: str
    disposal_method: str
    recycling_possibility: float
    bin_color: str
    special_instructions: Optional[str] = None
    carbon_saved_kg: float
    image_path: Optional[str] = ""

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AnalyticsSummaryResponse(BaseModel):
    total_detections: int
    recycling_rate_percent: float
    carbon_saved_kg: float
    average_confidence: float

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    suggested_actions: Optional[List[str]] = None

class ReportGenerateRequest(BaseModel):
    timeframe_days: int = Field(default=30, ge=1, le=365)

class ReportGenerateResponse(BaseModel):
    report_id: str
    pdf_url: str
    summary: str

# ----------------- Auth Schemas -----------------
class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserInDB(BaseModel):
    username: str
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str
