# ♻️ EcoSort AI: Intelligent Waste Segregation & Sustainability Analytics Platform

EcoSort AI is a full-stack, production-grade Computer Vision and ESG compliance platform designed to detect waste streams in real time. The platform classifies objects into disposal categories, provides instant segregation recommendations, calculates carbon footprint offsets, and builds compliance-ready PDF reports.

## 🚀 Key Features

1. **Real-time Detection & Inference**: Processes live video feeds, uploaded images, and video files to label items with bounding boxes and confidence parameters.
2. **Disposal Recommendation Engine**: Delivers material-specific guidelines (e.g., rinse instructions, bin color assignments, scrap metal drop-off directions).
3. **ESG & Sustainability Analytics**: Aggregates statistics for total scanned items, recycling percentage, and carbon reduction metrics.
4. **Interactive BI Dashboard**: Features custom Plotly visualization panels for daily volume metrics, material composition shares, and cumulative carbon savings.
5. **AI Sustainability Assistant**: Contains an analytical chatbot that queries database history to answer natural language queries (e.g., *"How much plastic did we save this week?"*).
6. **Robust Offline Capability**: Features an automatic fallback to an embedded local JSON database if MongoDB is unreachable, making it highly portable.

---

## 🏗️ Software Architecture

The platform follows clean, decoupled architectural patterns:

```
ecosort/
├── backend/
│   ├── api/          # RESTful routing layers & Pydantic validation schemas
│   ├── database/     # MongoDB connector & local database repository
│   ├── services/     # YOLOv8 CV engine, recommendations builder, NLP chatbot
│   ├── utils/        # System configs, structured logs, ReportLab PDF builder
│   └── main.py       # FastAPI entrance app
├── frontend/
│   ├── assets/       # Custom Glassmorphism styles (style.css)
│   ├── pages/        # Individual Streamlit pages (Detection, Analytics, History, Chat, Reports, Settings)
│   └── Home.py       # Streamlit landing page
├── models/           # YOLOv8 nano model location
├── reports/          # Temporary PDF reports cache

└── requirements.txt
```

---

## 🛠️ Tech Stack

- **Deep Learning / CV**: PyTorch, YOLOv8 (Ultralytics), OpenCV
- **Backend API**: FastAPI, Uvicorn, Pydantic v2
- **Frontend Dashboard**: Streamlit, Plotly, Pandas, NumPy
- **Database**: MongoDB (via `pymongo`) or Local JSON Database Fallback
- **Reporting**: ReportLab PDF Engine


---

## 🚦 Getting Started

### Local Startup

1. **Clone & Setup Environment**
   ```bash
   git clone https://github.com/your-username/ecosort.git
   cd ecosort
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Download a supported detection model**
   ```bash
   cd model
   yolo predict model=yolo26x.pt source=YOUR_IMAGE.jpg
   cd ..
   ```
   This downloads `model/yolo26x.pt`, the application's accuracy-first default model.
   Do not use the included legacy `best.pt`: it was serialized from an
   unpublished `ultralytics_bower` fork. To use another compatible checkpoint,
   set `YOLO_MODEL_PATH` in `.env`.

3. **Start Backend Service**
   ```bash
   python -m backend.main
   ```
   *The Swagger API docs will be hosted at [http://localhost:8000/docs](http://localhost:8000/docs).*

4. **Start Frontend Dashboard**
   ```bash
   streamlit run frontend/Home.py
   ```
   *Access the web app at [http://localhost:8501](http://localhost:8501).*

### Train the EcoSort waste detector

The standard YOLO model detects general objects, not mixed waste. The included
training setup converts the official TACO detection annotations into EcoSort's
eight disposal classes. It downloads roughly 1,500 source images, so run it on
a stable connection:

```bash
chmod +x training/*.sh
./training/setup_taco.sh
./training/train_waste_model.sh
```

Before final training, add and label your own mixed-bin images—especially
e-waste—under the same eight classes. After training, configure
`YOLO_MODEL_PATH` in `.env` to the generated `best.pt` checkpoint.

---



---

## 📊 Carbon Offsets & Calculations

The carbon mitigation calculations use coefficients adapted from the **EPA WARM (Waste Reduction Model)**:

$$\text{CO}_2 \text{ Saved (kg)} = \sum (\text{Material Recycled (kg)} \times \text{CO}_2 \text{ Offset Factor})$$

### Default Factors (kg CO₂ Saved per kg Recycled):
- **Plastic**: `2.5`
- **Paper**: `1.5`
- **Metal**: `5.0`
- **Glass**: `0.8`
- **Organic (Compost)**: `0.5`
- **E-Waste**: `8.0`
