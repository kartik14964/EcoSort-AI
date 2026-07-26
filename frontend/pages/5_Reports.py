import streamlit as st
import requests
from frontend.auth_utils import check_auth, get_auth_headers
import os

# Page Setup
st.set_page_config(page_title="EcoSort AI - Reports", page_icon="🖨️", layout="wide")

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

st.title("🖨️ ESG & Compliance Report Generator")
st.write("Generate compliance-ready PDF reports on corporate material redirection rates and greenhouse gas mitigations.")

st.markdown("""
<div class="pro-card">
    <h3 style="color: #1e3a8a; margin-top: 0;">Report Configuration</h3>
    <p style="color: #9ca3af; font-size: 0.95rem;">
        Specify the historical timeframe scope for your sustainability performance auditing. 
        The generated PDF will contain executive highlights, material distribution metrics, and carbon mitigation offsets.
    </p>
</div>
""", unsafe_allow_html=True)

# Selection Form
timeframe_days = st.slider("Select Audit Timeframe (Days)", min_value=1, max_value=365, value=30)

if st.button("Generate Performance PDF", type="primary"):
    with st.spinner("Compiling database records and calculating carbon factors..."):
        pdf_bytes = None
        filename = None
        try:
            response = requests.post(
                f"{API_URL}/reports/generate",
                json={"timeframe_days": timeframe_days},
                timeout=30,
                headers=get_auth_headers()
            )
            if response.status_code == 200:
                filename = response.json()["report_id"]
                download_resp = requests.get(
                    f"{API_URL}/reports/download/{filename}",
                    headers=get_auth_headers(),
                    timeout=30
                )
                if download_resp.status_code == 200:
                    pdf_bytes = download_resp.content
                else:
                    st.error(f"Could not download report (status {download_resp.status_code}).")
            else:
                st.error(f"Report generation failed (status {response.status_code}): {response.text}")
        except Exception as e:
            st.error(f"Cannot connect to backend: {e}")

        if pdf_bytes and filename:
            st.success("Report successfully generated!")

            st.download_button(
                label="📥 Download PDF Report",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                width="stretch"
            )

            st.info(
                f"📄 **Report Details:**\n"
                f"- **Filename:** `{filename}`\n"
                f"- **Scope:** Last {timeframe_days} days\n"
                f"- **Design:** Letter Standard, Corporate ESG Styled Layout"
            )
        else:
            st.error("Could not generate report. Please try again or check the system logs.")