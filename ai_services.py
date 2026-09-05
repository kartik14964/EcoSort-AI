import os
import cv2
import json
import base64
import numpy as np
import onnxruntime as ort
import threading
from app_utils import settings
from app_utils import setup_logger
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
    Look at the image carefully and identify the main object.
    Then, classify this waste item into exactly one of these categories:
    Plastic, Paper, Metal, Brown-glass, Green-glass, White-glass,
    Biological, Battery, Cardboard, Clothes, Shoes, Trash

    Rules:
    - Brown-glass = brown/amber glass bottles or jars
    - Green-glass = green glass bottles or jars
    - White-glass = clear/transparent glass bottles or jars
    - Biological = food waste (e.g., orange peels, fruit, vegetables), organic matter, plants
    - Battery = any battery type
    - Cardboard = cardboard boxes, packaging
    - Clothes = clothing, fabric items
    - Shoes = footwear
    - Trash = non-recyclable or ambiguous items (styrofoam, ceramics, mixed materials)

    Think step-by-step about what the object is, its material, and which category it belongs to.
    Write your thought process inside <think>...</think> tags.
    After thinking, respond with ONLY a JSON object on the final line.
    
    Example:
    <think>
    The image shows a crumpled plastic water bottle. It is made of clear PET plastic. Therefore, the category is Plastic.
    </think>
    {"category": "Plastic", "confidence": 0.95}"""

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}}
                    ]
                }],
                temperature=0,
                max_tokens=2048,
            )

            text = response.choices[0].message.content.strip()

            import re
            text_clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            match = re.search(r'\{[^{}]*\}', text_clean, re.DOTALL) or re.search(r'\{[^{}]*\}', text, re.DOTALL)

            if not match:
                logger.warning(f"Groq returned no JSON object. Raw text: {text!r}")
                return {"category": "Trash", "confidence": 0.0}

            result = json.loads(match.group(0))

            raw_category = str(result.get("category", "")).strip()
            normalized = raw_category.replace(" ", "-").replace("_", "-")

            matched = None
            for valid in self.VALID_CATEGORIES:
                if normalized.lower() == valid.lower():
                    matched = valid
                    break

            result["category"] = matched if matched else "Trash"

            logger.info(f"Groq raw category: {raw_category!r} -> normalized: {result['category']}")
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

    def detect_objects(self, image_path: str, threshold: float = None, force_groq: bool = False, allow_fallback: bool = True):
        threshold = threshold if threshold is not None else settings.DETECTION_THRESHOLD

        if not force_groq:
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

        annotated_img = image.copy()
        detections = []
        
        if not force_groq:
            annotated_img, detections = self._run_real_inference(image, threshold)

        if self.groq and self.groq.available:
            needs_fallback = not detections or detections[0]["confidence"] < 0.8
            if force_groq or (allow_fallback and needs_fallback):
                logger.info("Using Groq Vision...")
                groq_result = self.groq.classify(image_path)
                category = groq_result["category"]
                conf = float(groq_result.get("confidence", 0.95))

                color = self.CATEGORY_COLORS.get(category, (255, 255, 255))

                cv2.rectangle(annotated_img, (10, 10), (w-10, h-10), color, 4)
                cv2.putText(annotated_img, f"{category} (AI Vision) {conf:.2f}", (20, 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                detections = [{
                    "object_name": category,
                    "confidence": conf,
                    "category": category,
                    "bbox": [10, 10, w-10, h-10],
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


class LazyDetectionService:
    """Create the ONNX session only when image detection is first requested.

    Importing API routes must stay cheap: login and health do not require the
    vision model, and eagerly loading it makes every cold start block auth.
    """

    def __init__(self):
        self._instance = None
        self._lock = threading.Lock()

    def _get_instance(self) -> DetectionService:
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    logger.info("Initializing ONNX detector on first detection request.")
                    self._instance = DetectionService()
        return self._instance

    def detect_objects(self, image_path: str, threshold: float = None, force_groq: bool = False, allow_fallback: bool = True):
        return self._get_instance().detect_objects(image_path, threshold, force_groq, allow_fallback)


detector_service = LazyDetectionService()


import pandas as pd
from datetime import datetime, timedelta
from database import Repository

class AIAssistantService:
    def __init__(self):
        try:
            from groq import Groq
            self.client = Groq(api_key=settings.GROQ_API_KEY)
            self.model_name = "groq/compound-mini"
            self.available = True
        except Exception as e:
            logger.warning(f"Groq not available for chat: {e}")
            self.available = False

    def answer_query(self, messages: list) -> str:
        if not self.available:
            return "I'm currently running in offline mode and cannot process complex queries. Please configure a Groq API key to activate my AI."

        # 1. Fetch user context
        start_date = datetime.utcnow() - timedelta(days=30)
        detections = Repository.get_detections(filters={"start_date": start_date}, limit=1000)
        
        system_prompt = "You are the EcoSort AI Sustainability Assistant. You help users understand their waste sorting habits, carbon footprint, and provide general recycling advice.\n\n"
        
        if not detections:
            system_prompt += "The user has not scanned any items yet. Encourage them to use the Detection tab to start tracking their waste."
        else:
            df = pd.DataFrame(detections)
            total_items = len(df)
            recyclable_items = df[df['category'].isin(["Plastic", "Paper", "Metal", "Brown-glass", "Green-glass", "White-glass", "Cardboard"])]
            rec_rate = (len(recyclable_items) / total_items * 100) if total_items > 0 else 0
            total_co2 = df['carbon_saved_kg'].sum()
            top_cat = df['category'].value_counts().idxmax()
            
            system_prompt += f"Here is the user's 30-day statistics:\n"
            system_prompt += f"- Total items scanned: {total_items}\n"
            system_prompt += f"- Total CO2 saved: {total_co2:.2f} kg\n"
            system_prompt += f"- Recycling rate: {rec_rate:.1f}%\n"
            system_prompt += f"- Most common waste: {top_cat}\n\n"
            system_prompt += "Use these statistics to give personalized answers if the user asks about their own data. Be friendly, concise, and professional."

        # 2. Build messages payload
        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            api_messages.append({"role": msg["role"], "content": msg["content"]})
            
        # 3. Call Groq
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=api_messages,
                temperature=0.7,
                max_tokens=800,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq chat failed: {e}")
            return f"I encountered an error trying to process your request: {str(e)}"


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
