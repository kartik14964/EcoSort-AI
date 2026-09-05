import streamlit as st
from utils import inject_css
import pandas as pd
from auth_utils import check_auth, render_sidebar_footer, get_current_user
from database import Repository

st.set_page_config(page_title="EcoSort AI - History", page_icon="📜", layout="wide")
inject_css()
check_auth()

st.title("📜 Detection History")
st.write("View your past waste scans and recycling history.")

try:
    username = get_current_user()
    filters = {}
    if username != "anonymous":
        filters["username"] = username
        
    detections = Repository.get_detections(filters=filters, limit=100)
    if detections:
        df = pd.DataFrame(detections)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Select columns to display
        display_cols = ["timestamp", "object_name", "category", "confidence", "bin_color", "carbon_saved_kg"]
        existing_cols = [col for col in display_cols if col in df.columns]
        
        st.dataframe(df[existing_cols], width='stretch')
    else:
        st.info("No history found. Try scanning some items first!")
except Exception as e:
    st.error(f"Failed to load history: {e}")


# Render the universal sidebar footer (Logout) at the very bottom
render_sidebar_footer()
