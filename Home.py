import streamlit as st
from utils import inject_css
import os
from datetime import datetime

# ✅ Must be absolute first Streamlit call
st.set_page_config(
    page_title="EcoSort AI - Home",
    page_icon="E",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_css()

from auth_utils import check_auth, get_current_user, logout
from database import Repository

# ✅ Auth check — redirects to React if no token
check_auth()



# Load CSS
def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# Sidebar
if st.sidebar.button("Logout"):
    logout()
st.sidebar.markdown("---")
st.sidebar.markdown(
    "<p style='text-align: center; color: #6b7280; font-size: 0.8rem;'>EcoSort AI © 2026</p>",
    unsafe_allow_html=True
)

def get_dashboard_summary():
    try:
        username = get_current_user()
        return Repository.get_analytics_summary(days=30, username=username if username != "anonymous" else None)
    except Exception as e:
        st.error(f"Cannot load dashboard: {e}")
        return {
            "total_detections": 0,
            "recycling_rate_percent": 0.0,
            "carbon_saved_kg": 0.0,
            "average_confidence": 0.0
        }

def get_recent_detections(limit=5):
    try:
        username = get_current_user()
        filters = {}
        if username != "anonymous":
            filters["username"] = username
        return Repository.get_detections(filters=filters, limit=limit)
    except Exception as e:
        st.error(f"Cannot load detections: {e}")
        return []

# Hero Banner
st.markdown("""
<div class="hero-banner">
    <div style="font-size: 3rem; margin-bottom: 1rem;">♻️</div>
    <h1>EcoSort Analytics</h1>
    <p style="font-size: 1.05rem; margin: 0; font-weight: 500; opacity: 0.95;">
        Intelligent waste sorting, cleaner reporting, and measurable sustainability impact.
    </p>
</div>
""", unsafe_allow_html=True)

# KPI Cards
summary = get_dashboard_summary()
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="pro-card">
        <div class="metric-title">Last 30 Days</div>
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

# Main Grid
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("Platform Overview")
    st.markdown("""
        EcoSort AI represents the next generation of environmental engineering. By integrating a fast, on-device **ONNX
        computer vision model** with an **AI vision fallback** for uncertain cases, we enable facility managers, corporate
        headquarters, and city departments to track recycling efficiency, prevent contamination, and estimate carbon
        offsets in real-time.

        ### Core Capabilities
        - **Real-Time CV Inference**: Detect glass, plastics, metals, paper, organic food scraps, e-waste, and hazardous batteries.
        - **AI Vision Fallback**: When the primary model is uncertain, a large multimodal AI model steps in.
        - **Disposal Recommendation Engine**: Dynamic instructions on correct containment bins and local recovery centers.
        - **Carbon Offset Projections**: Track greenhouse gas mitigation metrics backed by standard emission data models.
        - **Interactive Analytics**: Generate insights, trends, distribution charts, and printable PDF reports.
    """)
    st.info("💡 **Quick Start:** Head over to the **Detection** tab in the sidebar to scan waste items.")

with right_col:
    st.subheader("Recent Detections")
    recent_items = get_recent_detections(5)

    if recent_items:
        for item in recent_items:
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
