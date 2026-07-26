import streamlit as st
import requests
from frontend.auth_utils import check_auth, get_auth_headers
import os

# Page Setup
st.set_page_config(page_title="EcoSort AI - Settings", page_icon="⚙️", layout="wide")

# CSS
def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "..", "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# Enforce Authentication
check_auth()

API_URL = os.environ.get("API_URL", "http://localhost:8000/api")

def get_current_settings():
    try:
        response = requests.get(f"{API_URL}/settings", timeout=5, headers=get_auth_headers())
        if response.status_code == 200:
            return response.json()
        st.error(f"Could not load settings (status {response.status_code}).")
    except Exception as e:
        st.error(f"Cannot connect to backend: {e}")
    return {}

def save_system_settings(new_settings):
    try:
        response = requests.put(f"{API_URL}/settings", json=new_settings, timeout=5, headers=get_auth_headers())
        if response.status_code == 200:
            return True
        st.error(f"Save failed (status {response.status_code}): {response.text}")
        return False
    except Exception as e:
        st.error(f"Cannot connect to backend: {e}")
        return False

st.title("⚙️ System Configuration Settings")
st.write("Tune computer vision parameters and carbon offset emission factors.")

current_config = get_current_settings()

if not current_config:
    st.error("Failed to load settings configuration.")
else:
    # Build tabs
    tab1, tab2 = st.tabs(["CV Model Configuration", "Carbon Offsets Settings"])
    
    with tab1:
        st.subheader("Computer Vision & Device Settings")
        det_thresh = st.slider(
            "Global Confidence Threshold", 
            0.0, 1.0, 
            float(current_config.get("detection_threshold", 0.25)),
            0.05
        )
        cam_src = st.text_input(
            "Default Webcam Source Index", 
            str(current_config.get("camera_source", "0"))
        )
        
    with tab2:
        st.subheader("CO₂ Savings Emission Factors (kg saved per kg material)")
        st.write("Configure standard greenhouse gas offset models based on regional environmental frameworks.")
        
        current_factors = current_config.get("co2_factors", {})
        
        categories = ["Plastic", "Paper", "Metal", "Brown-glass", "Green-glass",
                      "White-glass", "Biological", "Battery", "Cardboard",
                      "Clothes", "Shoes", "E-Waste", "Trash"]
        
        new_factors = {}
        col1, col2 = st.columns(2)
        for i, cat in enumerate(categories):
            with (col1 if i % 2 == 0 else col2):
                new_factors[cat] = st.number_input(
                    f"{cat} (kg CO₂/kg)",
                    min_value=0.0,
                    value=float(current_factors.get(cat, 0.1))
                )
            
    st.markdown("---")
    if st.button("Save Settings", type="primary"):
        new_config = {
            "detection_threshold": det_thresh,
            "camera_source": cam_src,
            "co2_factors": new_factors
        }
        
        if save_system_settings(new_config):
            st.success("System configurations successfully saved!")
            st.rerun()
        else:
            st.error("Failed to update configurations.")
