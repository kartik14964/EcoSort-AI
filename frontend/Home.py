import streamlit as st
import requests
import os
from datetime import datetime

from frontend.auth_utils import check_auth, get_auth_headers, logout
# Page Configuration
st.set_page_config(
    page_title="EcoSort AI - Sustainability Analytics",
    page_icon="E",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Custom CSS
def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# Enforce Authentication
check_auth()

if st.sidebar.button("Logout"):
    logout()

# API Base URL
API_URL = os.environ.get("API_URL", "http://localhost:8000/api")

def get_dashboard_summary():
    try:
        response = requests.get(f"{API_URL}/analytics/summary?days=30", headers=get_auth_headers(), timeout=10)
        if response.status_code == 200:
            return response.json()
        st.error(f"Could not load dashboard summary (status {response.status_code}).")
    except Exception as e:
        st.error(f"Cannot connect to backend: {e}")
    return {"total_detections": 0, "recycling_rate_percent": 0.0, "carbon_saved_kg": 0.0, "average_confidence": 0.0}

# Helper function to get recent detections
def get_recent_detections(limit=5):
    try:
        response = requests.get(f"{API_URL}/detections?limit={limit}", headers=get_auth_headers(), timeout=10)
        if response.status_code == 200:
            return response.json()
        st.error(f"Could not load recent detections (status {response.status_code}).")
    except Exception as e:
        st.error(f"Cannot connect to backend: {e}")
    return []

# Title Banner
st.markdown("""
<div class="hero-banner">
    <div style="font-size: 3rem; margin-bottom: 1rem;">♻️</div>
    <h1>EcoSort Analytics</h1>
    <p style="font-size: 1.05rem; margin: 0; font-weight: 500; opacity: 0.95;">
        Intelligent waste sorting, cleaner reporting, and measurable sustainability impact.
    </p>
</div>
""", unsafe_allow_html=True)

# Fetch current metrics
summary = get_dashboard_summary()

# KPI Metric Cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="pro-card">
        <div class="metric-title">Today's Scans</div>
        <div class="metric-value">{summary['total_detections']}</div>
        <div class="metric-subtitle">Total waste items identified</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="pro-card">
        <div class="metric-title">Recycling Rate</div>
        <div class="metric-value">{summary['recycling_rate_percent']}%</div>
        <div class="metric-subtitle">Target rate: 80.0%</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="pro-card">
        <div class="metric-title">Carbon Offsets</div>
        <div class="metric-value">{summary['carbon_saved_kg']} kg</div>
        <div class="metric-subtitle">Estimated CO₂ saved</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="pro-card">
        <div class="metric-title">Detection Accuracy</div>
        <div class="metric-value">{summary['average_confidence'] * 100:.1f}%</div>
        <div class="metric-subtitle">Average confidence score</div>
    </div>
    """, unsafe_allow_html=True)

# Main Grid Layout
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Platform Overview")
    st.markdown("""
        EcoSort AI represents the next generation of environmental engineering. By integrating a fast, on-device **ONNX 
        computer vision model** with an **AI vision fallback** for uncertain cases, we enable facility managers, corporate 
        headquarters, and city departments to track recycling efficiency, prevent contamination, and estimate carbon 
        offsets in real-time.
        
        ### Core Capabilities
        - **Real-Time CV Inference**: Detect glass, plastics, metals, paper, organic food scraps, e-waste, and hazardous batteries using an optimized ONNX model.
        - **AI Vision Fallback**: When the primary model is uncertain, a large multimodal AI model steps in to classify ambiguous items.
        - **Disposal Recommendation Engine**: Provide dynamic instructions on rinse cycles, correct containment bins, and local recovery centers.
        - **Carbon Offset Projections**: Track absolute greenhouse gas mitigation metrics backed by standard emission data models.
        - **Interactive Analytics**: Generate insights, trends, distribution charts, and printable compliance-ready PDF reports.
        """)
    
    st.info("💡 **Quick Start:** Head over to the **Detection** tab in the sidebar to scan waste items via Webcam feed, image, or video upload.")

with right_col:
    st.subheader("Recent Detections")
    recent_items = get_recent_detections(5)
    
    if recent_items:
        for item in recent_items:
            # Parse time
            ts = item.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts).strftime("%H:%M:%S")
                except ValueError:
                    pass
            elif isinstance(ts, datetime):
                ts = ts.strftime("%H:%M:%S")
                
            st.markdown(f"""
            <div class="history-item">
                <div class="history-header">
                    <strong class="history-title">{item.get('object_name')}</strong>
                    <span class="history-time">{ts}</span>
                </div>
                <div class="history-tags">
                    {item.get('category')} &bull; {item.get('bin_color')}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.write("No scan events logged today.")

# Sidebar branding footer
st.sidebar.markdown("---")
st.sidebar.markdown("<p style='text-align: center; color: #6b7280; font-size: 0.8rem;'>EcoSort AI © 2026<br/>Developed for Portfolio Demo</p>", unsafe_allow_html=True)
