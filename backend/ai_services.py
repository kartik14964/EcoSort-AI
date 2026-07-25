import os
import cv2
import numpy as np
from ultralytics import YOLO
from backend.utils import settings
from backend.utils import setup_logger

logger = setup_logger("detector_service")

# Class maps from YOLO/COCO to EcoSort waste categories
COCO_TO_WASTE_MAP = {
    # Plastic
    "bottle":       "Plastic",
    "cup":          "Plastic",
    "bowl":         "Plastic",
    "toothbrush":   "Plastic",
    "frisbee":      "Plastic",   # usually plastic
    "vase":         "Plastic",

    # Glass
    "wine glass":   "Green-glass",

    # Metal
    "fork":         "Metal",
    "knife":        "Metal",
    "spoon":        "Metal",
    "scissors":     "Metal",
    "sink":         "Metal",

    # Paper / Cardboard
    "book":         "Paper",
    "kite":         "Paper",

    # Organic
    "banana":       "Biological",
    "apple":        "Biological",
    "orange":       "Biological",
    "broccoli":     "Biological",
    "carrot":       "Biological",
    "sandwich":     "Biological",
    "hot dog":      "Biological",
    "pizza":        "Biological",
    "donut":        "Biological",
    "cake":         "Biological",

    # E-Waste
    "laptop":       "E-Waste",
    "mouse":        "E-Waste",
    "keyboard":     "E-Waste",
    "cell phone":   "E-Waste",
    "microwave":    "E-Waste",
    "oven":         "E-Waste",
    "refrigerator": "E-Waste",
    "hair drier":   "E-Waste",
    "remote":       "E-Waste",
    "tv":           "E-Waste",
    "clock":        "E-Waste",

    # Clothes / Textiles
    "tie":          "Clothes",
    "backpack":     "Clothes",
    "handbag":      "Clothes",
    "suitcase":     "Clothes",
    "umbrella":     "Clothes",

    # Trash (non-recyclable or ambiguous)
    "toaster":      "Trash",
    "teddy bear":   "Trash",
    "sports ball":  "Trash",
    "skateboard":   "Trash",
    "surfboard":    "Trash",
    "skis":         "Trash",
    "snowboard":    "Trash",
    "baseball bat": "Trash",
    "baseball glove": "Trash",
    "tennis racket": "Trash",
    "bench":        "Trash",
    "potted plant": "Biological",
}


class DetectionService:
    def __init__(self):
        self.model = None
        self.is_loaded = False
        self.load_model()

    def load_model(self):
        try:
            model_path = settings.YOLO_MODEL_PATH

            if not os.path.exists(model_path):
                raise FileNotFoundError(
                    f"Model not found at: {model_path}. Download an official model with "
                    "'cd model && yolo predict model=yolo26n.pt source=YOUR_IMAGE.jpg', "
                    "or set YOLO_MODEL_PATH to a compatible checkpoint."
                )

            logger.info(f"Loading YOLO model from: {model_path}")
            self.model = YOLO(model_path)
            self.is_loaded = True
            logger.info(f"Model loaded. Classes: {self.model.names}")

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.is_loaded = False

    def detect_objects(self, image_path: str, threshold: float = None):
        threshold = threshold if threshold is not None else settings.DETECTION_THRESHOLD
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image at {image_path}")

        if not self.is_loaded or self.model is None:
            raise RuntimeError("Detection model is not loaded. Check server logs for the load error.")

        return self._run_real_inference(image, threshold)

    def _run_real_inference(self, image: np.ndarray, threshold: float):
        try:
            results = self.model(image, conf=threshold)[0]
        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            return image.copy(), []

        annotated_image = image.copy()

        category_colors = {
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

        if results.boxes is None or len(results.boxes) == 0:
            return annotated_image, []

        qualifying_boxes = [box for box in results.boxes if float(box.conf[0]) >= threshold]
        if not qualifying_boxes:
            return annotated_image, []

        detections = []
        for box in qualifying_boxes:
            coords = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            name = self.model.names[int(box.cls[0])]
            object_name = " ".join(word.capitalize() for word in name.split(" "))

            category = COCO_TO_WASTE_MAP.get(name, object_name)
            detections.append({
                "object_name": object_name,
                "confidence": conf,
                "category": category,
                "box": coords,
            })

            color = category_colors.get(category, (255, 255, 255))
            x1, y1, x2, y2 = map(int, coords)
            cv2.rectangle(annotated_image, (x1, y1), (x2, y2), color, 3)
            label = f"{object_name} {conf:.2f}"
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(annotated_image, (x1, y1 - h - 12), (x1 + w + 6, y1), color, -1)
            cv2.putText(annotated_image, label, (x1 + 3, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

        return annotated_image, detections

detector_service = DetectionService()


import re
import pandas as pd
from datetime import datetime, timedelta
from backend.database import Repository

class AIAssistantService:
    @staticmethod
    def answer_query(message: str) -> str:
        msg = message.lower()
        
        # Load last 30 days of data for context
        start_date = datetime.utcnow() - timedelta(days=30)
        detections = Repository.get_detections(filters={"start_date": start_date}, limit=1000)
        
        if not detections:
            return "I don't see any recorded detections in the database yet. Start scanning items on the Detection page so I can analyze the sustainability footprint!"
            
        df = pd.DataFrame(detections)
        # Ensure timestamp is datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Helper variables
        total_items = len(df)
        recyclable_items = df[df['category'].isin(["Plastic", "Paper", "Metal", "Brown-glass", "Green-glass", "White-glass", "Cardboard"])]
        rec_rate = (len(recyclable_items) / total_items * 100) if total_items > 0 else 0
        total_co2 = df['carbon_saved_kg'].sum()
        
        # 1. Check for CO2/Carbon
        if "co2" in msg or "carbon" in msg or "greenhouse" in msg:
            return (
                f"We have prevented approximately **{total_co2:.2f} kg of CO₂ emissions** "
                f"from entering the atmosphere over the last 30 days. This was achieved by sorting and "
                f"recycling {len(recyclable_items)} items. That is equivalent to carbon sequestered by "
                f"roughly {total_co2 * 0.0165:.2f} trees growing for a decade!"
            )
            
        # 2. Check for Recycling rate
        if "recycling rate" in msg or "recyclability" in msg or "percent recyclable" in msg:
            return (
                f"The overall recycling rate is currently **{rec_rate:.1f}%**. Out of {total_items} total detected items, "
                f"{len(recyclable_items)} fall into highly recyclable categories (Plastic, Paper, Metal, Glass). "
                f"Our target is to exceed 80% through better segregation!"
            )
            
        # 3. Check for specific categories (Plastic, E-waste, Organic, etc.)
        for category in ["plastic", "paper", "metal", "brown-glass", "green-glass", "white-glass", "biological", "battery", "cardboard", "clothes", "shoes", "trash"]:
            if category in msg:
                cat_df = df[df['category'].str.lower() == category]
                cat_count = len(cat_df)
                cat_pct = (cat_count / total_items * 100) if total_items > 0 else 0
                cat_co2 = cat_df['carbon_saved_kg'].sum()
                
                # Check timeframe if specified
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
                    
                return (
                    f"A total of **{cat_count} {category} items** were detected {time_str}. "
                    f"This represents **{cat_pct:.1f}%** of all waste tracked. "
                    f"Sorting these {category} items saved **{cat_co2:.2f} kg of CO₂**."
                )

        # 4. Check for increasing trend or "which waste" is increasing
        if "increasing" in msg or "trend" in msg or "growth" in msg or "rising" in msg:
            # Group by category for last 2 weeks vs prior 2 weeks
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
                    return (
                        f"Analyzing trends from the last 2 weeks, **{fastest_growing}** waste is increasing "
                        f"fastest, showing a **+{growth_rate:.1f}% growth** compared to the preceding weeks. "
                        f"We should keep an eye on this category and review local recycling options."
                    )
                else:
                    # All categories decreased or stayed flat
                    top_category = df['category'].value_counts().idxmax()
                    return (
                        f"Waste levels have generally stabilized or decreased. However, **{top_category}** remains our "
                        f"highest volume category, representing {df['category'].value_counts().max() / total_items * 100:.1f}% of total waste."
                    )
                    
        # 5. General greeting/help
        if "hello" in msg or "hi " in msg or "hey" in msg or "help" in msg:
            return (
                "Hello! I am your EcoSort Sustainability Assistant. I can answer questions about "
                "our waste stats, carbon offsets, and trends. Try asking me:\n"
                "- *'How much plastic was detected this week?'*\n"
                "- *'What is our current recycling rate?'*\n"
                "- *'How much CO₂ did we save?'*\n"
                "- *'Which waste category is increasing?'*"
            )
            
        # Default fallback
        top_cat = df['category'].value_counts().idxmax()
        return (
            f"Over the last 30 days, we've logged **{total_items} items** across our platform. "
            f"The dominant waste category detected is **{top_cat}** ({df['category'].value_counts().max()} items). "
            f"Our recycling rate stands at **{rec_rate:.1f}%**, saving **{total_co2:.2f} kg of CO₂** in total. "
            f"Let me know if you need specific details on a category or timeframe!"
        )


from backend.utils import settings

class RecommendationEngine:
    # Comprehensive recommendations database for common items
    RECS_DATABASE = {
        "bottle": {
            "category": "Plastic",
            "disposal_method": "Rinse, crush, and place in Blue Recycling Bin.",
            "recycling_possibility": 0.95,
            "bin_color": "Blue",
            "special_instructions": "Remove the cap and recycle it separately if it is a different plastic type."
        },
        "plastic bottle": {
            "category": "Plastic",
            "disposal_method": "Rinse, crush, and place in Blue Recycling Bin.",
            "recycling_possibility": 0.95,
            "bin_color": "Blue",
            "special_instructions": "Remove the cap and recycle it separately."
        },
        "glass bottle": {
            "category": "Glass",
            "disposal_method": "Rinse and place in Green Glass Recycling Bin or General recycling.",
            "recycling_possibility": 0.98,
            "bin_color": "Green (Glass)",
            "special_instructions": "Do not break the glass. Remove metal or plastic caps first."
        },
        "cup": {
            "category": "Paper",
            "disposal_method": "Empty contents. Compost if uncoated paper; else place in landfill bin.",
            "recycling_possibility": 0.60,
            "bin_color": "Blue / Landfill",
            "special_instructions": "Many paper cups have a plastic lining (PE/PLA). Check compostable symbols."
        },
        "wine glass": {
            "category": "Glass",
            "disposal_method": "Discard in General Waste (Landfill) if broken, or Glass Recycle Bin if clean.",
            "recycling_possibility": 0.80,
            "bin_color": "Green / Grey",
            "special_instructions": "Drinking glass has a different melting point than container glass; avoid mixing in container recycling if possible."
        },
        "fork": {
            "category": "Metal",
            "disposal_method": "Wash and place in Scrap Metal Recycling or reuse.",
            "recycling_possibility": 0.90,
            "bin_color": "Blue (Scrap Metal)",
            "special_instructions": "Ensure it is clean of food residues."
        },
        "knife": {
            "category": "Metal",
            "disposal_method": "Wash and place in Scrap Metal Recycling.",
            "recycling_possibility": 0.90,
            "bin_color": "Blue (Scrap Metal)",
            "special_instructions": "Wrap sharp blades in cardboard to protect waste handlers."
        },
        "spoon": {
            "category": "Metal",
            "disposal_method": "Wash and place in Scrap Metal Recycling.",
            "recycling_possibility": 0.90,
            "bin_color": "Blue (Scrap Metal)",
            "special_instructions": "Ensure it is clean of food residues."
        },
        "banana": {
            "category": "Organic",
            "disposal_method": "Place in Green Organics / Compost Bin.",
            "recycling_possibility": 0.0,
            "bin_color": "Green (Organic)",
            "special_instructions": "Can be composted at home or placed in municipal organic collection."
        },
        "apple": {
            "category": "Organic",
            "disposal_method": "Place in Green Organics / Compost Bin.",
            "recycling_possibility": 0.0,
            "bin_color": "Green (Organic)",
            "special_instructions": "Compostable. Do not dispose of stickers/labels in compost."
        },
        "orange": {
            "category": "Organic",
            "disposal_method": "Place in Green Organics / Compost Bin.",
            "recycling_possibility": 0.0,
            "bin_color": "Green (Organic)",
            "special_instructions": "Citrus peels take slightly longer to decompose but are fully compostable."
        },
        "broccoli": {
            "category": "Organic",
            "disposal_method": "Place in Green Organics / Compost Bin.",
            "recycling_possibility": 0.0,
            "bin_color": "Green (Organic)",
            "special_instructions": "Compostable organic matter."
        },
        "carrot": {
            "category": "Organic",
            "disposal_method": "Place in Green Organics / Compost Bin.",
            "recycling_possibility": 0.0,
            "bin_color": "Green (Organic)",
            "special_instructions": "Compostable organic matter."
        },
        "sandwich": {
            "category": "Organic",
            "disposal_method": "Discard in Green Organic/Food Waste Bin.",
            "recycling_possibility": 0.0,
            "bin_color": "Green (Organic)",
            "special_instructions": "Ensure wrapping paper or plastic bags are removed."
        },
        "laptop": {
            "category": "E-Waste",
            "disposal_method": "Take to a certified Electronics Recycling Drop-off point.",
            "recycling_possibility": 0.85,
            "bin_color": "Orange (E-Waste)",
            "special_instructions": "Wipe hard drive before disposal. Do not place in normal household trash."
        },
        "mouse": {
            "category": "E-Waste",
            "disposal_method": "Drop off at E-waste disposal kiosk.",
            "recycling_possibility": 0.70,
            "bin_color": "Orange (E-Waste)",
            "special_instructions": "Remove alkaline or rechargeable batteries before disposal."
        },
        "keyboard": {
            "category": "E-Waste",
            "disposal_method": "Drop off at certified E-waste collector.",
            "recycling_possibility": 0.75,
            "bin_color": "Orange (E-Waste)",
            "special_instructions": "Wired/wireless keyboards contain recyclable circuit boards."
        },
        "cell phone": {
            "category": "E-Waste",
            "disposal_method": "Take to electronic retailer recycling station or local depot.",
            "recycling_possibility": 0.90,
            "bin_color": "Orange (E-Waste)",
            "special_instructions": "Factory reset device. Rechargeable Li-Ion battery must be handled carefully."
        },
        "microwave": {
            "category": "E-Waste",
            "disposal_method": "Take to electronic recycling depot or call city appliance pickup.",
            "recycling_possibility": 0.80,
            "bin_color": "Orange (E-Waste)",
            "special_instructions": "Contains heavy metal components and high voltage capacitors."
        },
        "oven": {
            "category": "E-Waste",
            "disposal_method": "Arrange municipal large appliance pickup or scrap metal merchant.",
            "recycling_possibility": 0.85,
            "bin_color": "Scrap / E-waste",
            "special_instructions": "Heavy appliance, requires special collection handling."
        },
        "refrigerator": {
            "category": "E-Waste",
            "disposal_method": "Arrange certified cooling appliance disposal pickup.",
            "recycling_possibility": 0.90,
            "bin_color": "Scrap / Special",
            "special_instructions": "Must be professionally drained of refrigerants (Freon/HCFCs) before recycling."
        },
        "book": {
            "category": "Paper",
            "disposal_method": "Donate if readable, or place in Blue Paper Recycling Bin.",
            "recycling_possibility": 0.95,
            "bin_color": "Blue",
            "special_instructions": "Remove plastic covers and spiral metal wires if possible."
        },
        "hair drier": {
            "category": "E-Waste",
            "disposal_method": "Take to E-waste drop-off box.",
            "recycling_possibility": 0.65,
            "bin_color": "Orange (E-Waste)",
            "special_instructions": "Contains copper coils and plastic housing."
        },
        "toothbrush": {
            "category": "Plastic",
            "disposal_method": "Place in General Waste (Landfill).",
            "recycling_possibility": 0.05,
            "bin_color": "Grey (Landfill)",
            "special_instructions": "Standard toothbrushes are composite materials and difficult to recycle. Consider bamboo alternatives."
        }
    }

    # Category defaults if specific item is not mapped
    CATEGORY_DEFAULTS = {
        "Plastic": {
            "disposal_method": "Empty, clean, dry, and place in Blue Recycling Bin.",
            "recycling_possibility": 0.80,
            "bin_color": "Blue",
            "special_instructions": "Check local resin identification codes (1 to 7)."
        },
        "Paper": {
            "disposal_method": "Place in Blue Recycling Bin or Green Waste if food soiled.",
            "recycling_possibility": 0.90,
            "bin_color": "Blue",
            "special_instructions": "Keep paper dry. Wet paper fibers decompose and clog recycling screens."
        },
        "Metal": {
            "disposal_method": "Rinse food container residue and place in Blue Recycling Bin.",
            "recycling_possibility": 0.95,
            "bin_color": "Blue",
            "special_instructions": "Infinitely recyclable. Aluminum and steel are highly valued."
        },
        "Brown-glass": {
            "disposal_method": "Rinse and place in Brown Glass Bin.",
            "recycling_possibility": 0.95,
            "bin_color": "Brown Glass",
            "special_instructions": "Color-sorted glass recycling."
        },
        "Green-glass": {
            "disposal_method": "Rinse and place in Green Glass Bin.",
            "recycling_possibility": 0.95,
            "bin_color": "Green Glass",
            "special_instructions": "Color-sorted glass recycling."
        },
        "White-glass": {
            "disposal_method": "Rinse and place in Clear/White Glass Bin.",
            "recycling_possibility": 0.95,
            "bin_color": "Clear Glass",
            "special_instructions": "Color-sorted glass recycling."
        },
        "Biological": {
            "disposal_method": "Place in Green Organics / Compost Bin.",
            "recycling_possibility": 0.0,
            "bin_color": "Green",
            "special_instructions": "Compostable organic matter."
        },
        "Battery": {
            "disposal_method": "Take to a dedicated battery recycling drop-off point.",
            "recycling_possibility": 0.90,
            "bin_color": "Red / Hazardous",
            "special_instructions": "Do not throw in normal household trash due to fire hazards."
        },
        "Cardboard": {
            "disposal_method": "Flatten and place in Paper/Cardboard Recycling Bin.",
            "recycling_possibility": 0.95,
            "bin_color": "Blue",
            "special_instructions": "Keep dry and free of heavy grease/food waste."
        },
        "Clothes": {
            "disposal_method": "Donate if usable, or drop off at textile recycling bins.",
            "recycling_possibility": 0.60,
            "bin_color": "Textile Bin",
            "special_instructions": "Ensure items are clean and dry."
        },
        "Shoes": {
            "disposal_method": "Donate if wearable, otherwise place in textile recycling.",
            "recycling_possibility": 0.40,
            "bin_color": "Textile Bin",
            "special_instructions": "Tie pairs together if donating."
        },
        "Trash": {
            "disposal_method": "Place in Grey Landfill Bin.",
            "recycling_possibility": 0.0,
            "bin_color": "Grey",
            "special_instructions": "Non-recyclable general waste."
        }
    }

    @classmethod
    def get_recommendation(cls, object_name: str, detected_category: str = "Other") -> dict:
        """
        Generate waste recommendation based on detected category.
        Since model outputs category names directly (Plastic, Brown-glass etc),
        we go straight to CATEGORY_DEFAULTS.
        """
        # Try exact category match first
        if detected_category in cls.CATEGORY_DEFAULTS:
            rec = cls.CATEGORY_DEFAULTS[detected_category].copy()
            rec["item_name"] = object_name
            rec["category"] = detected_category
            return rec

        # Try case-insensitive match
        for key in cls.CATEGORY_DEFAULTS:
            if key.lower() == detected_category.lower():
                rec = cls.CATEGORY_DEFAULTS[key].copy()
                rec["item_name"] = object_name
                rec["category"] = key
                return rec

        # Final fallback — Trash is always safe
        rec = cls.CATEGORY_DEFAULTS["Trash"].copy()
        rec["item_name"] = object_name
        rec["category"] = "Trash"
        return rec
