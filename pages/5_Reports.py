import streamlit as st
import pandas as pd
from auth_utils import check_auth, get_current_user
from database import Repository
from datetime import datetime

st.set_page_config(page_title="EcoSort AI - Reports", page_icon="📄", layout="wide")
check_auth()

st.title("📄 Generate Reports")
st.write("Export your sustainability data for compliance and reporting.")

if st.button("Generate CSV Report"):
    try:
        username = get_current_user()
        filters = {}
        if username != "anonymous":
            filters["username"] = username
            
        detections = Repository.get_detections(filters=filters, limit=1000)
        if detections:
            df = pd.DataFrame(detections)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"ecosort_report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
            st.success("Report generated successfully!")
        else:
            st.warning("No data available to generate a report.")
    except Exception as e:
        st.error(f"Failed to generate report: {e}")
