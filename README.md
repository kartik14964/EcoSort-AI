# ♻️ EcoSort AI: Intelligent Waste Segregation & Sustainability Analytics Platform

EcoSort AI is a full-stack waste classification, recommendation, and sustainability metrics platform. It leverages a fine-tuned computer vision model quantized for CPU execution, a large multimodal AI model fallback for low-confidence detections, and custom dashboards to track compliance-ready ESG analytics.

---

## 🏗️ System Architecture & Data Flow

EcoSort features a hybrid architecture separating authorization concerns, backend business logic, AI inference, and interactive reporting:

```
                            ┌────────────────────────┐
                            │    Vite + React SPA    │  (Login Gateway - Port 5173)
                            │   (ecosort-auth)       │
                            └───────────┬────────────┘
                                        │ JWT Redirect (?token=...)
                                        ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Web Backend                     (Port 8000)  │
│                                                                               │
│   ┌────────────────────┐      ┌─────────────────────┐      ┌──────────────┐   │
│   │    Auth Router     ├─────►│  Database Connector ├─────►│ MongoDB Atlas│   │
│   │   (PyJWT/Bcrypt)   │      │ (Lazy PyMongo Repo) │      └──────────────┘   │
│   └────────────────────┘      └──────────▲──────────┘                         │
│                                          │                                    │
│   ┌────────────────────┐                 │                                    │
│   │     API Router     ├─────────────────┘                                    │
│   │ (Detection/Reports)│                                                      │
│   └──────────┬─────────┘                                                      │
│              │                                                                │
│              ▼                                                                │
│   ┌────────────────────────────────────────────────────────┐                  │
│   │                    AI Inference System                 │                  │
│   │                                                        │                  │
│   │  ┌───────────────────────┐      ┌───────────────────┐  │                  │
│   │  │     ONNX Runtime      │      │  Groq Vision API  │  │                  │
│   │  │ (YOLOv8 INT8, CPU)    ├─────►│ (Fallback LMM)    │  │                  │
│   │  └───────────────────────┘      └───────────────────┘  │                  │
│   └────────────────────────────────────────────────────────┘                  │
└──────────────────────────────────────▲────────────────────────────────────────┘
                                       │ HTTP REST Requests
                                       │ (Bearer Authentication)
                            ┌──────────┴────────────┐
                            │  Streamlit Dashboard  │  (Dashboard Pages - Port 8501)
                            │  (frontend/Home.py)   │
                            └───────────────────────┘
```

### Flow of Operations:
1. **User Authentication**: Users land on the **React Portal** (`ecosort-auth`), register/login, obtain a JWT, and are redirected to the **Streamlit Dashboard** with the token in the URL.
2. **Inference Pipeline**: Users upload an image or capture a webcam photo. The Streamlit server forwards the frame to the `/api/detect/image` backend.
3. **Dual-Model Inference**:
   * The **ONNX Engine** runs a CPU-quantized YOLOv8 object detector (`best_int8.onnx`).
   * If YOLO detects nothing or falls below `50%` confidence, the backend invokes the **Groq Vision Fallback** (`qwen/qwen3.6-27b`) to categorize the waste item.
4. **Data Aggregation**: Detections can be manually saved to **MongoDB** to compute real-time recycling rates and CO₂ metrics.
5. **Compliance Reporting**: Dynamic PDFs are generated via **ReportLab** incorporating cumulative carbon savings projections.

---

## 📁 Repository Structure

```
ecosort/
├── backend/                # FastAPI Application
│   ├── ai_services.py      # ONNX YOLO Runner + Groq LMM Fallback + Rule Chatbot
│   ├── auth.py             # JWT Token Security, Bcrypt Password Hashing
│   ├── database.py         # MongoDB Lazy Connector & Repository Queries
│   ├── main.py             # FastAPI entry point & CORS configuration
│   ├── routes.py           # REST Endpoint handlers (Detect, Settings, Reports)
│   ├── schemas.py          # Pydantic Request/Response Models
│   ├── utils.py            # Logger Setup, Base Settings, ReportLab PDF Generator
│   └── requirements.txt    # Backend dependencies
├── ecosort-auth/           # React Authentication Gateway (Vite SPA)
│   ├── src/
│   │   ├── App.jsx         # Authentication Form & Axios Redirections
│   │   └── main.jsx        # Client bootstrapper
│   └── package.json        # Frontend Node dependencies
├── frontend/               # Streamlit Dashboard UI
│   ├── pages/              # Sidebar Multipage Layout
│   │   ├── 1_Detection.py  # Image uploads, webcam snaps, & bin recommendations
│   │   ├── 2_Analytics.py  # Plotly interactive data visualizations
│   │   ├── 3_History.py    # Historical logs grid & deep inspection cards
│   │   ├── 4_Assistant.py  # Chat interface for sustainability queries
│   │   ├── 5_Reports.py    # Trigger ESG compliance PDF generator downloads
│   │   └── 6_Settings.py   # Edit confidence thresholds & CO2 coefficients
│   ├── Home.py             # App Main Entrance
│   ├── auth_utils.py       # Streamlit auth interception & bearer config
│   ├── style.css           # Glassmorphism visual styling overrides
│   └── requirements.txt    # Streamlit dependencies
├── model/
│   ├── best.onnx           # Compiled ONNX YOLO model
│   └── best_int8.onnx      # Quantized INT8 ONNX YOLO model (active runtime)
└── README.md               # Documentation
```

---

## 🛠️ Technology Stack

* **Machine Learning & CV**: ONNX Runtime (CPU execution), OpenCV, YOLOv8
* **Large Multimodal Fallback**: Groq API (`qwen/qwen3.6-27b` or similar vision model)
* **Backend Framework**: FastAPI (Uvicorn, Pydantic v2)
* **Primary Database**: MongoDB Atlas (via `pymongo`)
* **Dashboard Interface**: Streamlit, Plotly, Pandas, NumPy
* **Gateway Interface**: React (Vite, Axios, CSS3)
* **Document Compilation**: ReportLab PDF Engine

---

## 🚦 Getting Started

Follow these steps to run the complete EcoSort stack locally.

### Step 1: Run MongoDB
Ensure you have MongoDB running locally at `mongodb://localhost:27017` or obtain a MongoDB Atlas Connection String.

### Step 2: Configure Environment Variables
Create a `.env` file in the `backend/` directory:
```env
MONGO_URI=mongodb://localhost:27017  # Your MongoDB connection string
JWT_SECRET_KEY=generate-a-secure-secret-key-here
GROQ_API_KEY=your-groq-api-key-here  # Required for vision fallbacks
```

### Step 3: Run the FastAPI Backend
1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Start the FastAPI server:
   ```bash
   python main.py
   ```
   *The Swagger interactive documentation will be hosted at [http://localhost:8000/docs](http://localhost:8000/docs).*

### Step 4: Run the React Authentication Gateway
1. Open a new terminal and navigate to the `ecosort-auth/` directory:
   ```bash
   cd ecosort-auth
   npm install
   ```
2. Create a `.env` file in `ecosort-auth/` containing:
   ```env
   VITE_BACKEND_URL=http://localhost:8000/api
   VITE_DASHBOARD_URL=http://localhost:8501
   ```
3. Start the dev server:
   ```bash
   npm run dev
   ```
   *The login screen will be hosted at [http://localhost:5173](http://localhost:5173).*

### Step 5: Run the Streamlit Dashboard
1. Open a new terminal and navigate to the `frontend/` directory:
   ```bash
   cd frontend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Set backend configuration in terminal environment:
   ```bash
   export API_URL=http://localhost:8000/api
   export REACT_LOGIN_URL=http://localhost:5173
   ```
3. Start Streamlit:
   ```bash
   streamlit run Home.py
   ```
   *The main dashboard will boot up on [http://localhost:8501](http://localhost:8501).*

---

## 📊 Carbon Mitigation Calculations

Carbon savings estimations use coefficients representing **kg of CO₂ saved per kg of recycled material**, derived from EPA WARM (Waste Reduction Model) metrics:

$$\text{CO}_2 \text{ Saved (kg)} = \sum (\text{Material Recycled (kg)} \times \text{CO}_2 \text{ Offset Factor})$$

### Default Material Coefficients:
* **Metal**: `5.0`
* **E-Waste**: `4.0`
* **Plastic**: `2.5`
* **Paper / Cardboard**: `1.5`
* **Glass** (Brown, Green, White): `0.8`
* **Biological (Compost)**: `0.5`
* **General Trash**: `0.1`

*(Coefficients can be modified at runtime using the **Settings** page in the dashboard).*
