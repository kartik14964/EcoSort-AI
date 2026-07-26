import os
import cv2
import json
import base64
import numpy as np
import onnxruntime as ort
from backend.utils import settings
from backend.utils import setup_logger
import gc

logger = setup_logger("detector_service")


class GroqClassifier:
    VALID_CATEGORIES = {
        "Plastic", "Paper", "Metal", "Brown-glass", "Green-glass",
        "White-glass", "Biological", "Battery", "Cardboard",
        "Clothes", "Shoes", "Trash"
    }

    def __init__(self, api_key: str):
        try:
            from groq import Groq
            self.client = Groq(api_key=api_key)
            self.model_name = "qwen/qwen3.6-27b"
            self.available = True
            logger.info("Groq Vision classifier loaded.")
        except Exception as e:
            logger.warning(f"Groq not available: {e}")
            self.available = False

    def classify(self, image_path: str) -> dict:
        if not self.available:
            return {"category": "Trash", "confidence": 0.0}
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")

            ext = image_path.lower().split(".")[-1]
            mime = "image/png" if ext == "png" else "image/jpeg"

            prompt = """You are a waste classification expert for a sustainability app.
Classify this waste item into exactly one of these categories:
Plastic, Paper, Metal, Brown-glass, Green-glass, White-glass,
Biological, Battery, Cardboard, Clothes, Shoes, Trash

Rules:
- Brown-glass = brown/amber glass bottles or jars
- Green-glass = green glass bottles or jars
- White-glass = clear/transparent glass bottles or jars
- Biological = food waste, organic matter, plants
- Battery = any battery type
- Cardboard = cardboard boxes, packaging
- Clothes = clothing, fabric items
- Shoes = footwear
- Trash = non-recyclable or ambiguous items (styrofoam, ceramics, mixed materials)

Respond with JSON only: {"category": "category_name", "confidence": 0.95}"""

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}}
                    ]
                }],
                response_format={"type": "json_object"}
            )

            text = response.choices[0].message.content.strip()
            result = json.loads(text)

            if result.get("category") not in self.VALID_CATEGORIES:
                result["category"] = "Trash"

            logger.info(f"Groq result: {result['category']} ({result.get('confidence', 0):.2f})")
            return result

        except Exception as e:
            logger.error(f"Groq classification failed: {e}")
            return {"category": "Trash", "confidence": 0.0}


def preprocess_image(image: np.ndarray, input_size: int = 416):
    h, w = image.shape[:2]
    scale = min(input_size / h, input_size / w)
    new_h, new_w = int(h * scale), int(w * scale)
    resized = cv2.resize(image, (new_w, new_h))
    padded = np.full((input_size, input_size, 3), 114, dtype=np.uint8)
    pad_top = (input_size - new_h) // 2
    pad_left = (input_size - new_w) // 2
    padded[pad_top:pad_top+new_h, pad_left:pad_left+new_w] = resized
    img = padded[:, :, ::-1].astype(np.float32) / 255.0
    img = img.transpose(2, 0, 1)
    img = np.expand_dims(img, axis=0)
    return img, scale, pad_left, pad_top


def nms(boxes, scores, iou_threshold=0.45):
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    return keep


class DetectionService:
    CLASS_NAMES = {
        0: 'battery', 1: 'biological', 2: 'brown-glass', 3: 'cardboard',
        4: 'clothes', 5: 'green-glass', 6: 'metal', 7: 'paper',
        8: 'plastic', 9: 'shoes', 10: 'trash', 11: 'white-glass'
    }

    CATEGORY_COLORS = {
        "Plastic":      (255, 165, 0),
        "Paper":        (0, 255, 255),
        "Metal":        (192, 192, 192),
        "Cardboard":    (200, 150, 50),
        "Brown-glass":  (101, 67, 33),
        "Green-glass":  (0, 200, 0),
        "White-glass":  (230, 230, 230),
        "Biological":   (34, 139, 34),
        "Battery":      (0, 0, 255),
        "Clothes":      (128, 0, 128),
        "Shoes":        (100, 100, 100),
        "Trash":        (80, 80, 80),
    }

    def __init__(self):
        self.session = None
        self.is_loaded = False
        self.groq = None
        self.load_model()
        if settings.GROQ_API_KEY:
            self.groq = GroqClassifier(settings.GROQ_API_KEY)
        else:
            logger.warning("GROQ_API_KEY not set — Groq fallback disabled.")

    def load_model(self):
        try:
            model_path = settings.YOLO_MODEL_PATH
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model not found at: {model_path}")

            logger.info(f"Loading ONNX model from: {model_path}")
            sess_options = ort.SessionOptions()
            sess_options.enable_cpu_mem_arena = False
            sess_options.enable_mem_pattern = False
            sess_options.enable_mem_reuse = False

            self.session = ort.InferenceSession(
                model_path,
                sess_options=sess_options,
                providers=["CPUExecutionProvider"]
            )
            self.input_name = self.session.get_inputs()[0].name
            self.is_loaded = True
            logger.info("ONNX model loaded successfully.")

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.is_loaded = False

    def detect_objects(self, image_path: str, threshold: float = None):
        threshold = threshold if threshold is not None else settings.DETECTION_THRESHOLD

        if not self.is_loaded or self.session is None:
            logger.warning("Session not available, reloading...")
            self.load_model()
        if not self.is_loaded or self.session is None:
            raise RuntimeError("Detection model failed to load.")

        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image at {image_path}")

        h, w = image.shape[:2]
        if max(h, w) > 640:
            scale = 640 / max(h, w)
            image = cv2.resize(image, (int(w * scale), int(h * scale)))

        annotated_img, detections = self._run_real_inference(image, threshold)

        if self.groq and self.groq.available:
            if not detections or detections[0]["confidence"] < 0.5:
                logger.info("ONNX low confidence — using Groq fallback...")
                groq_result = self.groq.classify(image_path)
                category = groq_result["category"]
                conf = float(groq_result.get("confidence", 0.85))

                h, w = image.shape[:2]
                color = self.CATEGORY_COLORS.get(category, (255, 255, 255))

                cv2.rectangle(annotated_img, (10, 10), (w-10, h-10), color, 4)
                label = f"{category} {conf:.2f} (AI)"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
                cv2.rectangle(annotated_img, (10, 10), (10+tw+10, 10+th+14), color, -1)
                cv2.putText(annotated_img, label, (15, 10+th+4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

                detections = [{
                    "object_name": category,
                    "confidence": conf,
                    "category": category,
                    "box": [10, 10, w-10, h-10],
                    "method": "Groq-AI"
                }]

        del image
        gc.collect()
        return annotated_img, detections

    def _run_real_inference(self, image: np.ndarray, threshold: float):
        input_tensor = outputs = boxes_xywh = class_scores = None
        try:
            input_tensor, scale, pad_left, pad_top = preprocess_image(image)
            outputs = self.session.run(None, {self.input_name: input_tensor})[0]
            outputs = outputs[0].T

            boxes_xywh = outputs[:, :4]
            class_scores = outputs[:, 4:]
            class_ids = np.argmax(class_scores, axis=1)
            confidences = np.max(class_scores, axis=1)

            mask = confidences >= threshold
            boxes_xywh = boxes_xywh[mask]
            class_ids = class_ids[mask]
            confidences = confidences[mask]

            MAX_CANDIDATES = 300
            if len(boxes_xywh) > MAX_CANDIDATES:
                top_idx = np.argsort(confidences)[-MAX_CANDIDATES:]
                boxes_xywh = boxes_xywh[top_idx]
                class_ids = class_ids[top_idx]
                confidences = confidences[top_idx]

            if len(boxes_xywh) == 0:
                return image.copy(), []

            x_c, y_c, w, h = boxes_xywh[:, 0], boxes_xywh[:, 1], boxes_xywh[:, 2], boxes_xywh[:, 3]
            x1 = (x_c - w / 2 - pad_left) / scale
            y1 = (y_c - h / 2 - pad_top) / scale
            x2 = (x_c + w / 2 - pad_left) / scale
            y2 = (y_c + h / 2 - pad_top) / scale
            boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

            keep = nms(boxes_xyxy, confidences, iou_threshold=0.45)

        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            return image.copy(), []
        finally:
            del input_tensor, outputs, boxes_xywh, class_scores
            gc.collect()

        annotated_image = image.copy()
        detections = []

        for i in keep:
            conf = float(confidences[i])
            name = self.CLASS_NAMES[int(class_ids[i])]
            category = "-".join(word.capitalize() for word in name.split("-"))

            coords = boxes_xyxy[i].tolist()
            detections.append({
                "object_name": category,
                "confidence": conf,
                "category": category,
                "box": coords,
                "method": "ONNX"
            })

            color = self.CATEGORY_COLORS.get(category, (255, 255, 255))
            x1, y1, x2, y2 = map(int, coords)
            cv2.rectangle(annotated_image, (x1, y1), (x2, y2), color, 3)
            label = f"{category} {conf:.2f}"
            (w_txt, h_txt), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(annotated_image, (x1, y1-h_txt-12), (x1+w_txt+6, y1), color, -1)
            cv2.putText(annotated_image, label, (x1+3, y1-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

        return annotated_image, detections


detector_service = DetectionService()


import pandas as pd
from datetime import datetime, timedelta
from backend.database import Repository

class AIAssistantService:
    @staticmethod
    def answer_query(message: str) -> str:
        msg = message.lower()
        start_date = datetime.utcnow() - timedelta(days=30)
        detections = Repository.get_detections(filters={"start_date": start_date}, limit=1000)

        if not detections:
            return "I don't see any recorded detections in the database yet. Start scanning items on the Detection page so I can analyze the sustainability footprint!"

        df = pd.DataFrame(detections)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        total_items = len(df)
        recyclable_items = df[df['category'].isin(["Plastic", "Paper", "Metal", "Brown-glass", "Green-glass", "White-glass", "Cardboard"])]
        rec_rate = (len(recyclable_items) / total_items * 100) if total_items > 0 else 0
        total_co2 = df['carbon_saved_kg'].sum()

        if "co2" in msg or "carbon" in msg or "greenhouse" in msg:
            return (f"We have prevented approximately **{total_co2:.2f} kg of CO₂ emissions** from entering the atmosphere over the last 30 days. This was achieved by sorting and recycling {len(recyclable_items)} items. That is equivalent to carbon sequestered by roughly {total_co2 * 0.0165:.2f} trees growing for a decade!")

        if "recycling rate" in msg or "recyclability" in msg or "percent recyclable" in msg:
            return (f"The overall recycling rate is currently **{rec_rate:.1f}%**. Out of {total_items} total detected items, {len(recyclable_items)} fall into highly recyclable categories (Plastic, Paper, Metal, Glass). Our target is to exceed 80% through better segregation!")

        for category in ["plastic", "paper", "metal", "brown-glass", "green-glass", "white-glass", "biological", "battery", "cardboard", "clothes", "shoes", "trash"]:
            if category in msg:
                cat_df = df[df['category'].str.lower() == category]
                cat_count = len(cat_df)
                cat_pct = (cat_count / total_items * 100) if total_items > 0 else 0
                cat_co2 = cat_df['carbon_saved_kg'].sum()
                time_str = "in the last 30 days"
                if "week" in msg:
                    one_week_ago = datetime.utcnow() - timedelta(days=7)
                    cat_week_df = cat_df[cat_df['timestamp'] >= one_week_ago]
                    cat_count = len(cat_week_df)
                    time_str = "this past week"
                    cat_co2 = cat_week_df['carbon_saved_kg'].sum()
                elif "today" in msg or "day" in msg and not "days" in msg:
                    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    cat_day_df = cat_df[cat_df['timestamp'] >= today_start]
                    cat_count = len(cat_day_df)
                    time_str = "today"
                    cat_co2 = cat_day_df['carbon_saved_kg'].sum()
                return (f"A total of **{cat_count} {category} items** were detected {time_str}. This represents **{cat_pct:.1f}%** of all waste tracked. Sorting these {category} items saved **{cat_co2:.2f} kg of CO₂**.")

        if "increasing" in msg or "trend" in msg or "growth" in msg or "rising" in msg:
            two_weeks_ago = datetime.utcnow() - timedelta(days=14)
            four_weeks_ago = datetime.utcnow() - timedelta(days=28)
            recent_df = df[df['timestamp'] >= two_weeks_ago]
            older_df = df[(df['timestamp'] >= four_weeks_ago) & (df['timestamp'] < two_weeks_ago)]
            recent_counts = recent_df['category'].value_counts()
            older_counts = older_df['category'].value_counts()
            trends = {}
            for cat in df['category'].unique():
                r_val = recent_counts.get(cat, 0)
                o_val = older_counts.get(cat, 0)
                if o_val > 0:
                    growth = ((r_val - o_val) / o_val) * 100
                else:
                    growth = 100.0 if r_val > 0 else 0
                trends[cat] = growth
            if trends:
                fastest_growing = max(trends, key=trends.get)
                growth_rate = trends[fastest_growing]
                if growth_rate > 0:
                    return (f"Analyzing trends from the last 2 weeks, **{fastest_growing}** waste is increasing fastest, showing a **+{growth_rate:.1f}% growth** compared to the preceding weeks.")
                else:
                    top_category = df['category'].value_counts().idxmax()
                    return (f"Waste levels have generally stabilized or decreased. However, **{top_category}** remains our highest volume category, representing {df['category'].value_counts().max() / total_items * 100:.1f}% of total waste.")

        if "hello" in msg or "hi " in msg or "hey" in msg or "help" in msg:
            return ("Hello! I am your EcoSort Sustainability Assistant. I can answer questions about our waste stats, carbon offsets, and trends. Try asking me:\n- *'How much plastic was detected this week?'*\n- *'What is our current recycling rate?'*\n- *'How much CO₂ did we save?'*\n- *'Which waste category is increasing?'*")

        top_cat = df['category'].value_counts().idxmax()
        return (f"Over the last 30 days, we've logged **{total_items} items** across our platform. The dominant waste category detected is **{top_cat}** ({df['category'].value_counts().max()} items). Our recycling rate stands at **{rec_rate:.1f}%**, saving **{total_co2:.2f} kg of CO₂** in total.")


class RecommendationEngine:
    CATEGORY_DEFAULTS = {
        "Plastic": {"disposal_method": "Empty, clean, dry, and place in Blue Recycling Bin.", "recycling_possibility": 0.80, "bin_color": "Blue", "special_instructions": "Check local resin identification codes (1 to 7)."},
        "Paper": {"disposal_method": "Place in Blue Recycling Bin or Green Waste if food soiled.", "recycling_possibility": 0.90, "bin_color": "Blue", "special_instructions": "Keep paper dry. Wet paper fibers decompose and clog recycling screens."},
        "Metal": {"disposal_method": "Rinse food container residue and place in Blue Recycling Bin.", "recycling_possibility": 0.95, "bin_color": "Blue", "special_instructions": "Infinitely recyclable. Aluminum and steel are highly valued."},
        "Brown-glass": {"disposal_method": "Rinse and place in Brown Glass Bin.", "recycling_possibility": 0.95, "bin_color": "Brown Glass", "special_instructions": "Color-sorted glass recycling."},
        "Green-glass": {"disposal_method": "Rinse and place in Green Glass Bin.", "recycling_possibility": 0.95, "bin_color": "Green Glass", "special_instructions": "Color-sorted glass recycling."},
        "White-glass": {"disposal_method": "Rinse and place in Clear/White Glass Bin.", "recycling_possibility": 0.95, "bin_color": "Clear Glass", "special_instructions": "Color-sorted glass recycling."},
        "Biological": {"disposal_method": "Place in Green Organics / Compost Bin.", "recycling_possibility": 0.0, "bin_color": "Green", "special_instructions": "Compostable organic matter."},
        "Battery": {"disposal_method": "Take to a dedicated battery recycling drop-off point.", "recycling_possibility": 0.90, "bin_color": "Red / Hazardous", "special_instructions": "Do not throw in normal household trash due to fire hazards."},
        "Cardboard": {"disposal_method": "Flatten and place in Paper/Cardboard Recycling Bin.", "recycling_possibility": 0.95, "bin_color": "Blue", "special_instructions": "Keep dry and free of heavy grease/food waste."},
        "Clothes": {"disposal_method": "Donate if usable, or drop off at textile recycling bins.", "recycling_possibility": 0.60, "bin_color": "Textile Bin", "special_instructions": "Ensure items are clean and dry."},
        "Shoes": {"disposal_method": "Donate if wearable, otherwise place in textile recycling.", "recycling_possibility": 0.40, "bin_color": "Textile Bin", "special_instructions": "Tie pairs together if donating."},
        "Trash": {"disposal_method": "Place in Grey Landfill Bin.", "recycling_possibility": 0.0, "bin_color": "Grey", "special_instructions": "Non-recyclable general waste."}
    }

    @classmethod
    def get_recommendation(cls, object_name: str, detected_category: str = "Other") -> dict:
        if detected_category in cls.CATEGORY_DEFAULTS:
            rec = cls.CATEGORY_DEFAULTS[detected_category].copy()
            rec["item_name"] = object_name
            rec["category"] = detected_category
            return rec
        for key in cls.CATEGORY_DEFAULTS:
            if key.lower() == detected_category.lower():
                rec = cls.CATEGORY_DEFAULTS[key].copy()
                rec["item_name"] = object_name
                rec["category"] = key
                return rec
        rec = cls.CATEGORY_DEFAULTS["Trash"].copy()
        rec["item_name"] = object_name
        rec["category"] = "Trash"
        return rec