import streamlit as st
import pandas as pd
import requests
import os


from frontend.auth_utils import check_auth, get_auth_headers

# Page Setup
st.set_page_config(page_title="EcoSort AI - Scan History", page_icon="📜", layout="wide")

# CSS
def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "..", "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# Enforce Authentication
check_auth()

API_URL = "http://localhost:8000/api"

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

# Sidebar Filters
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
    
    # Format dates
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['Formatted Time'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Rearrange columns for display
    display_df = df[[
        '_id', 'Formatted Time', 'object_name', 'category', 
        'confidence', 'bin_color', 'carbon_saved_kg'
    ]].copy()
    
    display_df.columns = [
        'ID', 'Timestamp', 'Object Name', 'Category', 
        'Confidence', 'Bin Color', 'Carbon Saved (kg)'
    ]
    
    # Display table
    st.dataframe(display_df, width="stretch", hide_index=True)
    
    # Inspection Expanders
    st.subheader("🔍 Deep Inspection Panel")
    st.write("Select a logged item to view its details, disposal recommendations, and annotated capture.")
    
    # Let user select one of the recent 20 records to inspect
    inspect_list = [f"{r['object_name']} ({r['category']}) - {r['timestamp']}" for r in records[:20]]
    selected_inspect = st.selectbox("Choose item to inspect", inspect_list)
    
    if selected_inspect:
        idx = inspect_list.index(selected_inspect)
        item = records[idx]
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"""
            <div class="pro-card" style="padding: 24px;">
                <h3 style="color: #0f172a; margin-top: 0; font-size: 1.5rem;">{item['object_name']} Details</h3>
                <table style="width: 100%; font-size: 0.95rem; border-collapse: collapse; margin-top: 16px;">
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Category:</td><td style="color: #0f172a;">{item['category']}</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Scan Timestamp:</td><td style="color: #0f172a;">{item['timestamp']}</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Confidence:</td><td style="color: #0f172a;">{item['confidence']*100:.1f}%</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Bin Designation:</td><td style="color: #10b981; font-weight: 500;">{item['bin_color']}</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Carbon Reduction:</td><td style="color: #0f172a;">{item['carbon_saved_kg']} kg CO₂</td></tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Disposal Instructions:</td><td style="color: #0f172a;">{item['disposal_method']}</td></tr>
                    <tr><td style="padding: 12px 0; font-weight: 600; color: #64748b;">Special Instructions:</td><td style="color: #ef4444;">{item['special_instructions']}</td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown("### Annotated Capture")
            img_path = item.get("image_path")
            if img_path and os.path.exists(img_path):
                st.image(img_path, caption=f"Annotated scan for record ID: {item['_id']}", width="stretch")
            else:
                st.info("No annotated image file found for this record (e.g. video frame scan or image cleanup triggered).")
