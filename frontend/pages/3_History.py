import streamlit as st
import pandas as pd
import requests
import os

st.set_page_config(page_title="EcoSort AI - Scan History", page_icon="📜", layout="wide")

from frontend.auth_utils import check_auth, get_auth_headers
check_auth()

API_URL = os.environ.get("API_URL", "http://localhost:8000/api")

def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "..", "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

def get_history_data(category=None):
    url = f"{API_URL}/detections?limit=1000"
    if category and category != "All":
        url += f"&category={category}"
    try:
        response = requests.get(url, timeout=10, headers=get_auth_headers())
        if response.status_code == 200:
            return response.json()
        st.error(f"Could not load history (status {response.status_code}).")
    except Exception as e:
        st.error(f"Cannot connect to backend: {e}")
    return []

st.title("📜 Detection History Logs")
st.write("Browse, filter, and inspect historical sorting events recorded by the platform.")

st.sidebar.subheader("Filter Logs")
categories = ["All", "Plastic", "Paper", "Metal", "Brown-glass", "Green-glass",
              "White-glass", "Biological", "Battery", "Cardboard", "Clothes",
              "Shoes", "E-Waste", "Trash"]
selected_category = st.sidebar.selectbox("Filter by Category", categories)

records = get_history_data(selected_category)

if not records:
    st.info("No recorded detection logs match the selected filters.")
else:
    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['Formatted Time'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    display_df = df[['_id', 'Formatted Time', 'object_name', 'category',
                      'confidence', 'bin_color', 'carbon_saved_kg']].copy()
    display_df.columns = ['ID', 'Timestamp', 'Object Name', 'Category',
                           'Confidence', 'Bin Color', 'Carbon Saved (kg)']
    st.dataframe(display_df, width="stretch", hide_index=True)

    st.subheader("🔍 Deep Inspection Panel")
    inspect_list = [f"{r['object_name']} ({r['category']}) - {r['timestamp']}" for r in records[:20]]
    selected_inspect = st.selectbox("Choose item to inspect", inspect_list)

    if selected_inspect:
        idx = inspect_list.index(selected_inspect)
        item = records[idx]
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"""
            <div class="pro-card" style="padding: 24px;">
                <h3 style="color: #0f172a; margin-top: 0;">{item['object_name']} Details</h3>
                <table style="width: 100%; font-size: 0.95rem; border-collapse: collapse; margin-top: 16px;">
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Category:</td><td>{item['category']}</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Timestamp:</td><td>{item['timestamp']}</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Confidence:</td><td>{item['confidence']*100:.1f}%</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Bin:</td><td style="color: #10b981;">{item['bin_color']}</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Carbon Saved:</td><td>{item['carbon_saved_kg']} kg CO₂</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Disposal:</td><td>{item['disposal_method']}</td></tr>
                    <tr><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Special Note:</td><td style="color: #ef4444;">{item['special_instructions']}</td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("### Annotated Capture")
            img_path = item.get("image_path")
            if img_path and os.path.exists(img_path):
                st.image(img_path, caption=f"Record ID: {item['_id']}", width="stretch")
            else:
                st.info("No annotated image found for this record.")