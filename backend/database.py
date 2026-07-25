import pymongo
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import certifi
from backend.utils import settings
from backend.utils import setup_logger

logger = setup_logger("database_connection")


class DatabaseConnection:
    def __init__(self):
        self.client = None
        self.db = None
        self.is_mock = False
        self.mode = "initializing"
        self.status_message = "Initializing storage connection..."
        self.connect()

    @staticmethod
    def _normalize_mongo_uri(uri: str) -> str:
        if not uri:
            return "mongodb://127.0.0.1:27017"

        normalized = uri.strip()
        if not normalized:
            return "mongodb://127.0.0.1:27017"

        if normalized.startswith("<") or normalized.endswith(">"):
            return "mongodb+srv://kartikrawat14964_db_user:<db_password>@cluster0.evb5qua.mongodb.net/?appName=Cluster0"

        return normalized

    def connect(self):
        mongo_uri = self._normalize_mongo_uri(settings.MONGO_URI)
        try:
            self.client = pymongo.MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=2500,
                appname="ecosort-ai",
                tlsCAFile=certifi.where(),
            )
            self.client.admin.command("ping")
            self.db = self.client[settings.DB_NAME]
            self.is_mock = False
            self.mode = "mongodb"
            self.status_message = f"Connected to MongoDB database '{settings.DB_NAME}'."
            logger.info("Successfully connected to MongoDB.")
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            logger.error(f"MongoDB connection failed: {e}")
            self.is_mock = False
            self.mode = "failed"
            self.status_message = f"MongoDB connection failed: {e}"
            self.client = None
            self.db = None


db_conn = DatabaseConnection()


from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId
from backend.database import db_conn
from backend.utils import settings
from backend.utils import setup_logger

logger = setup_logger("database_repository")


class Repository:
    RECYCLABLE_CATEGORIES = ["Plastic", "Paper", "Metal", "Brown-glass", "Green-glass", "White-glass", "Cardboard"]

    @staticmethod
    def get_connection_status():
        return {
            "mode": db_conn.mode,
            "message": db_conn.status_message,
            "is_mock": db_conn.is_mock,
        }

    @staticmethod
    def get_settings():
        try:
            settings_doc = db_conn.db.settings.find_one({"_id": "default"})
            if not settings_doc:
                default_settings = {
                    "_id": "default",
                    "detection_threshold": settings.DETECTION_THRESHOLD,
                    "camera_source": "0",
                    "co2_factors": settings.CO2_SAVINGS_FACTORS
                }
                db_conn.db.settings.insert_one(default_settings)
                return default_settings
            return settings_doc
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            return {}

    @staticmethod
    def update_settings(new_settings):
        try:
            db_conn.db.settings.update_one(
                {"_id": "default"},
                {"$set": new_settings},
                upsert=True
            )
            return Repository.get_settings()
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return {}

    @staticmethod
    def insert_detection(detection):
        if "timestamp" not in detection:
            detection["timestamp"] = datetime.utcnow()
        if "_id" not in detection:
            detection["_id"] = ObjectId()

        try:
            res = db_conn.db.detections.insert_one(detection)
            detection["_id"] = res.inserted_id
            return detection
        except Exception as e:
            logger.error(f"Error inserting detection: {e}")
            return None

    @staticmethod
    def get_detections(filters=None, limit=100):
        filters = filters or {}

        query = {}
        if "username" in filters and filters["username"]:
            query["username"] = filters["username"]
        if "category" in filters and filters["category"]:
            query["category"] = filters["category"]
        if "start_date" in filters or "end_date" in filters:
            query["timestamp"] = {}
            if "start_date" in filters:
                query["timestamp"]["$gte"] = filters["start_date"]
            if "end_date" in filters:
                query["timestamp"]["$lte"] = filters["end_date"]

        try:
            cursor = db_conn.db.detections.find(query).sort("timestamp", -1).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"Error listing detections: {e}")
            return []

    @staticmethod
    def get_analytics_summary(days=30, username=None):
        start_date = datetime.utcnow() - timedelta(days=days)

        filters = {"start_date": start_date}
        if username:
            filters["username"] = username

        detections = Repository.get_detections(
            filters=filters,
            limit=10000
        )

        total_count = len(detections)
        recyclable_count = sum(1 for d in detections if d["category"] in Repository.RECYCLABLE_CATEGORIES)
        recycling_rate = (recyclable_count / total_count * 100) if total_count > 0 else 0
        total_carbon = sum(d.get("carbon_saved_kg", 0) for d in detections)
        avg_confidence = sum(d.get("confidence", 0) for d in detections) / total_count if total_count > 0 else 0

        return {
            "total_detections": total_count,
            "recycling_rate_percent": round(recycling_rate, 2),
            "carbon_saved_kg": round(total_carbon, 2),
            "average_confidence": round(avg_confidence, 2)
        }

    # ---------------- Auth / Users ----------------

    @classmethod
    def get_user_by_username(cls, username: str) -> Optional[dict]:
        try:
            return db_conn.db.users.find_one({"username": username})
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    @classmethod
    def create_user(cls, user_data: dict) -> str:
        try:
            res = db_conn.db.users.insert_one(user_data)
            return str(res.inserted_id)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None