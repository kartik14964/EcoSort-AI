import time
import pymongo
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import certifi
from app_utils import settings
from app_utils import setup_logger

logger = setup_logger("database_connection")


class DatabaseConnection:
    def __init__(self):
        self.client = None
        self.db = None
        self.is_mock = False
        self.mode = "not_connected"
        self.status_message = "Storage connection has not been requested yet."
        self._last_attempt = 0.0
        # Do not connect during module import.  FastAPI imports every router
        # before it can answer even /health, and a cold Mongo connection can
        # otherwise make authentication wait behind startup work it does not
        # need.  ``ensure_connected`` opens the connection on the first route
        # that actually uses storage.

    @staticmethod
    def _normalize_mongo_uri(uri: str) -> str:
        if not uri or not uri.strip():
            raise RuntimeError("MONGO_URI is not set. Add it in Render's Environment tab.")

        normalized = uri.strip()

        if normalized.startswith("<") or normalized.endswith(">") or "<db_password>" in normalized:
            raise RuntimeError(
                "MONGO_URI still contains a placeholder value — set the real "
                "connection string in Render's Environment tab."
            )

        return normalized

    def connect(self, retries: int = 3, delay_seconds: float = 2.0):
        try:
            mongo_uri = self._normalize_mongo_uri(settings.MONGO_URI)
        except RuntimeError as e:
            logger.error(str(e))
            self.client = None
            self.db = None
            self.mode = "failed"
            self.status_message = str(e)
            return

        for attempt in range(1, retries + 1):
            try:
                self.client = pymongo.MongoClient(
                    mongo_uri,
                    serverSelectionTimeoutMS=8000,
                    appname="ecosort-ai",
                    tlsCAFile=certifi.where(),
                )
                self.client.admin.command("ping")
                self.db = self.client[settings.DB_NAME]
                self.is_mock = False
                self.mode = "mongodb"
                self.status_message = f"Connected to MongoDB database '{settings.DB_NAME}'."
                logger.info(f"Successfully connected to MongoDB (attempt {attempt}).")
                return
            except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
                logger.warning(f"MongoDB connection attempt {attempt}/{retries} failed: {e}")
                self.client = None
                self.db = None
                if attempt < retries:
                    time.sleep(delay_seconds)

        self.is_mock = False
        self.mode = "failed"
        self.status_message = "MongoDB connection failed after retries."
        logger.error("MongoDB connection failed after all retry attempts.")

    def ensure_connected(self):
        """Lazily retry the connection if a previous attempt failed,
        but don't let every request pay an 8s+ retry penalty."""
        if self.db is not None:
            return

        now = time.time()
        if self._last_attempt and (now - self._last_attempt) < 15:
            raise RuntimeError("Database temporarily unavailable, please retry shortly.")

        self._last_attempt = now
        self.connect(retries=1, delay_seconds=0)

        if self.db is None:
            raise RuntimeError("Database temporarily unavailable, please retry shortly.")


db_conn = DatabaseConnection()


from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId
from database import db_conn
from app_utils import settings
from app_utils import setup_logger

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
        db_conn.ensure_connected()
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
        db_conn.ensure_connected()
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
        db_conn.ensure_connected()
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
        db_conn.ensure_connected()
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
            results = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                results.append(doc)
            return results
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
        db_conn.ensure_connected()
        try:
            return db_conn.db.users.find_one({"username": username})
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    @classmethod
    def create_user(cls, user_data: dict) -> str:
        db_conn.ensure_connected()
        try:
            res = db_conn.db.users.insert_one(user_data)
            return str(res.inserted_id)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
