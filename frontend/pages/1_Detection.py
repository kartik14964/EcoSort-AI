import streamlit as st
import requests
from frontend.auth_utils import check_auth, get_auth_headers
import os
import base64

# Page Setup
st.set_page_config(page_title="EcoSort AI - Waste Detection", page_icon="📷", layout="wide")

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


def filter_by_confidence(detections, threshold):
    """Keep the UI consistent with the selected detection control."""
    return [item for item in detections if float(item.get("confidence", 0)) >= threshold]

def save_to_db(detections, key):
    """Render Save button and call /detections/save on click."""
    if st.button("💾 Save to Database", key=key):
        try:
            save_resp = requests.post(
                f"{API_URL}/detections/save",
                json={"detections": detections},
                headers=get_auth_headers(),
                timeout=10
            )
            if save_resp.status_code == 200:
                st.success(f"✅ Saved {save_resp.json()['count']} item(s) to database!")
            else:
                st.error(f"Save failed: {save_resp.text}")
        except Exception as e:
            st.error(f"Save error: {e}")

def render_detections(detections, conf_thresh):
    """Render detection cards for image/webcam results."""
    st.caption(f"Showing {len(detections)} item(s) at or above {conf_thresh:.0%} confidence.")
    if not detections:
        st.warning("No target materials identified above the threshold.")
        return
    for det in detections:
        st.markdown(f"""
        <div class="pro-card" style="padding: 20px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 12px;">
                <strong style="font-size: 1.1rem; color: #0f172a;">{det['object_name']}</strong>
                <span style="background: #ecfdf5; color: #10b981; border: 1px solid #a7f3d0; padding: 4px 10px; border-radius: 99px; font-size: 0.75rem; font-weight: 600;">
                    Confidence: {det['confidence']*100:.1f}%
                </span>
            </div>
            <div style="font-size: 0.9rem; color: #334155; line-height: 1.6;">
                <div style="display: grid; grid-template-columns: 120px 1fr; margin-bottom: 4px;">
                    <strong style="color:#64748b;">Category:</strong>
                    <span>{det['category']}</span>
                </div>
                <div style="display: grid; grid-template-columns: 120px 1fr; margin-bottom: 4px;">
                    <strong style="color:#64748b;">Disposal Bin:</strong>
                    <span style="color: #ea580c; font-weight: 500;">{det['bin_color']}</span>
                </div>
                <div style="display: grid; grid-template-columns: 120px 1fr; margin-bottom: 4px;">
                    <strong style="color:#64748b;">Instructions:</strong>
                    <span>{det['disposal_method']}</span>
                </div>
                {f'<div style="display: grid; grid-template-columns: 120px 1fr; margin-bottom: 4px;"><strong style="color:#64748b;">Special Note:</strong> <span style="color: #ef4444;">{det["special_instructions"]}</span></div>' if det.get('special_instructions') else ''}
                <div style="display: grid; grid-template-columns: 120px 1fr; margin-bottom: 4px;">
                    <strong style="color:#64748b;">Carbon Offset:</strong>
                    <span style="color: #10b981; font-weight: 600;">{det['carbon_saved_kg']} kg CO₂</span>
                </div>
            </div>
            <div style="margin-top: 16px; pt-3; border-top: 1px dashed #e2e8f0;">
                <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 6px; font-weight: 500;">Recycling Feasibility</div>
        """, unsafe_allow_html=True)
        st.progress(float(det['recycling_possibility']))
        st.markdown("</div>", unsafe_allow_html=True)

st.title("📷 Material Classifier & Segregator")
st.write("Upload an image, snap a photo, or process a video file to analyze its recycling footprint.")

# Sidebar Configuration
st.sidebar.subheader("Detection Controls")

try:
    settings_resp = requests.get(f"{API_URL}/settings", headers=get_auth_headers())
    if settings_resp.status_code == 200:
        saved_threshold = float(settings_resp.json().get("detection_threshold", 0.25))
    else:
        saved_threshold = 0.25
except Exception:
    saved_threshold = 0.25

conf_thresh = st.sidebar.slider(
    "Confidence Threshold",
    min_value=0.0,
    max_value=1.0,
    value=saved_threshold,
    step=0.05
)
st.sidebar.caption(f"Only detections at or above {conf_thresh:.0%} are shown.")

mode = st.radio("Choose Input Method", ["Image Upload", "Webcam Snap"], horizontal=True)

# ── IMAGE UPLOAD ──────────────────────────────────────────────────────────────
if mode == "Image Upload":
    uploaded_file = st.file_uploader("Select JPG or PNG image...", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        st.write("Processing image...")

        res_data = None
        try:
            uploaded_file.seek(0)
            files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
            response = requests.post(
                f"{API_URL}/detect/image?threshold={conf_thresh}",
                files=files, timeout=120, headers=get_auth_headers()
            )
            if response.status_code == 200:
                res_data = response.json()
            else:
                st.error(f"Detection failed: {response.text}")
        except Exception as e:
            st.error(f"API Connection Error: {e}")

        if res_data:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("Annotated Frame")
                img_data = base64.b64decode(res_data["annotated_image_b64"])
                st.image(img_data, width="stretch")
                st.download_button(
                    label="⬇️ Download Annotated Image",
                    data=img_data,
                    file_name="ecosort_annotated.jpg",
                    mime="image/jpeg",
                    key="download_image"
                )

            with col2:
                st.subheader("Classification & Recommendations")
                detections = filter_by_confidence(res_data.get("detections", []), conf_thresh)
                render_detections(detections, conf_thresh)

            if detections:
                with col1:
                    save_to_db(detections, key="save_image")

# ── WEBCAM SNAP ───────────────────────────────────────────────────────────────
elif mode == "Webcam Snap":
    webcam_img = st.camera_input("Snap a photo of the waste item")

    if webcam_img is not None:
        st.write("Analyzing camera snapshot...")

        res_data = None
        try:
            webcam_img.seek(0)
            files = {"file": ("webcam.jpg", webcam_img, "image/jpeg")}
            response = requests.post(
                f"{API_URL}/detect/image?threshold={conf_thresh}",
                files=files, timeout=120, headers=get_auth_headers()
            )
            if response.status_code == 200:
                res_data = response.json()
            else:
                st.error(f"Detection failed: {response.text}")
        except Exception as e:
            st.error(f"API Connection Error: {e}")

        if res_data:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("Annotated Capture")
                img_data = base64.b64decode(res_data["annotated_image_b64"])
                st.image(img_data, width="stretch")
                st.download_button(
                    label="⬇️ Download Annotated Image",
                    data=img_data,
                    file_name="ecosort_webcam.jpg",
                    mime="image/jpeg",
                    key="download_webcam"
                )

            with col2:
                st.subheader("Classification & Recommendations")
                detections = filter_by_confidence(res_data.get("detections", []), conf_thresh)
                render_detections(detections, conf_thresh)

            if detections:
                with col1:
                    save_to_db(detections, key="save_webcam")