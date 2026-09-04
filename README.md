# 🌍 EcoSort AI

EcoSort AI is an intelligent waste classification and sustainability analytics platform. It leverages advanced computer vision and multi-modal AI to analyze waste items, categorize them into standard recycling groups, and track your personal or organizational carbon footprint offset.

## ✨ Key Features
- **📸 Smart Waste Detection:** Snap a photo or upload an image. EcoSort uses either a blazing-fast local ONNX object detection model or Groq's high-accuracy Cloud Vision AI to classify waste across 12 distinct categories.
- **📊 Sustainability Analytics:** Track your recycling efficiency, daily scanning volumes, and cumulative carbon savings (kg CO₂) via interactive Plotly dashboards.
- **🤖 AI Sustainability Assistant:** A built-in Groq-powered chatbot that analyzes your historical data to answer questions like *"How much CO₂ did I save this week?"* or *"What is the proper way to dispose of a battery?"*
- **📜 Automated Reporting:** Generate and export historical logs as CSV reports for compliance or personal tracking.
- **⚙️ Fully Configurable:** Easily configure AI vision preferences and fine-tune carbon offset factors per waste category directly from the Settings UI.

## 🛠️ Tech Stack
- **Frontend / UI:** Streamlit (Native Python UI, fully responsive layout)
- **Computer Vision (Local):** YOLO-based object detection via ONNX Runtime
- **Cloud Vision & LLM:** Groq API (Llama 3.2 Vision / Qwen multimodal architectures)
- **Database:** MongoDB Atlas (Cloud database for storing users, detections, and settings)
- **Data Visualization:** Pandas & Plotly Express

## 🚀 Local Setup

### 1. Prerequisites
Ensure you have Python 3.9+ installed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
*(Note: We use `opencv-python-headless` to avoid missing UI library errors on servers).*

### 3. Environment Variables
Create a `.env` file in the root directory with your API keys:
```env
MONGO_URI="mongodb+srv://<username>:<password>@cluster0...mongodb.net/?appName=Cluster0"
GROQ_API_KEY="gsk_..."
```

### 4. Run the Application
Start the Streamlit server:
```bash
streamlit run Home.py
```
Open `http://localhost:8501` in your browser.

## 📦 Deployment Guide

EcoSort is architected to be perfectly deployable on **Streamlit Community Cloud** or **Hugging Face Spaces**. 

1. **Push to GitHub**: Commit your code and push it to a public or private repository.
2. **Deploy**:
   - For **Streamlit Cloud**: Connect your repository at [share.streamlit.io](https://share.streamlit.io/). Set the main file to `Home.py`.
   - For **Hugging Face Spaces**: Create a new Streamlit Space and upload your repository files.
3. **Secrets**: Navigate to the Settings -> Secrets section of your hosting provider and add your `MONGO_URI` and `GROQ_API_KEY` exactly as they appear in your `.env` file.

## 📂 Project Structure
```text
ecosort/
├── Home.py                  # Main entry point and authentication router
├── pages/                   # Auto-generated Streamlit Sidebar Navigation
│   ├── 1_Detection.py       # Computer Vision & Waste Classification UI
│   ├── 2_Analytics.py       # Interactive Plotly Dashboards
│   ├── 3_History.py         # Tabular view of past scans
│   ├── 4_Assistant.py       # Groq AI Chatbot interface
│   ├── 5_Reports.py         # CSV Export functionality
│   └── 6_Settings.py        # Carbon factor and AI configuration
├── ai_services.py           # Core logic for ONNX inference and Groq classification
├── database.py              # MongoDB connection and schema definitions
├── auth_utils.py            # User login, registration, and session management
├── utils.py                 # Core settings, constants, and logging
├── style.css                # Custom UI styling applied globally
└── model/                   
    └── best_int8.onnx       # Local optimized YOLO model
```
