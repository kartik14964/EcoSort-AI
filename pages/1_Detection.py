import streamlit as st
from app_utils import inject_css
import os
import base64

# ✅ Must be first Streamlit call
st.set_page_config(page_title="EcoSort AI - Waste Detection", page_icon="📷", layout="wide", initial_sidebar_state="expanded" if st.session_state.get("authenticated", False) else "collapsed")
inject_css()

from auth_utils import check_auth, render_sidebar_footer, get_current_user
from database import Repository
from ai_services import detector_service, RecommendationEngine
from app_utils import settings
import cv2
import numpy as np

# ✅ Auth check — redirects to React if no token
check_auth()

# Load CSS
def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "..", "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()


def filter_by_confidence(detections, threshold):
    return [item for item in detections if float(item.get("confidence", 0)) >= threshold]


def save_to_db(detections, key):
    if st.button("💾 Save to Database", key=key):
        try:
            username = get_current_user()
            count = 0
            for det in detections:
                det_copy = det.copy()
                det_copy["username"] = username if username != "anonymous" else "anonymous"
                Repository.insert_detection(det_copy)
                count += 1
            st.success(f"✅ Saved {count} item(s) to database!")
        except Exception as e:
            st.error(f"Save error: {e}")


def render_detections(detections, conf_thresh):
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
                    <span style="color: #10b981; font-weight: 600;">{det.get('carbon_saved_kg', 0.0)} kg CO₂</span>
                </div>
            </div>
            <div style="margin-top: 16px; border-top: 1px dashed #e2e8f0;">
                <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 6px; font-weight: 500;">Recycling Feasibility</div>
        """, unsafe_allow_html=True)
        st.progress(float(det['recycling_possibility']))
        st.markdown("</div></div>", unsafe_allow_html=True)


st.title("📷 Material Classifier & Segregator")
st.write("Upload an image or snap a photo to analyze its recycling footprint.")

# Sidebar
st.sidebar.subheader("Detection Controls")

try:
    settings_doc = Repository.get_settings()
    db_threshold = float(settings_doc.get("detection_threshold", 0.25))
except Exception:
    db_threshold = 0.25

saved_threshold = st.sidebar.slider(
    "Confidence Threshold", 
    min_value=0.05, 
    max_value=1.00, 
    value=db_threshold, 
    step=0.05, 
    help="Lower this if the local AI model is missing objects."
)

st.sidebar.subheader("AI Processing Mode")
processing_mode = st.sidebar.radio(
    "Select Mode", 
    ["🧠 Smart Mode (Advanced AI)", "⚡ Fast Mode (Local AI)"],
    index=1,
    help="Smart Mode uses advanced AI for maximum accuracy (Recommended). Fast Mode runs locally but only recognizes 12 basic categories."
)
force_ai = "Smart Mode" in processing_mode
allow_fallback = False # Strictly isolate them so it's not confusing

mode = st.radio("Choose Input Method", ["Image Upload", "Webcam Snap"], horizontal=True)

# ── IMAGE UPLOAD ──────────────────────────────────────────────────────────────
if mode == "Image Upload":
    uploaded_file = st.file_uploader("Select JPG or PNG image...", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        st.write("Processing image...")
        res_data = None
        try:
            file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
            image = cv2.imdecode(file_bytes, 1)
            temp_path = "temp_upload.jpg"
            cv2.imwrite(temp_path, image)
            
            annotated_img, raw_detections = detector_service.detect_objects(temp_path, threshold=saved_threshold, force_groq=force_ai, allow_fallback=allow_fallback)
            
            settings_doc = Repository.get_settings()
            co2_factors = settings_doc.get("co2_factors", settings.CO2_SAVINGS_FACTORS)
            
            enriched = []
            for det in raw_detections:
                rec = RecommendationEngine.get_recommendation(det["object_name"], det["category"])
                det.update(rec)
                det["carbon_saved_kg"] = co2_factors.get(det["category"], 0.0)
                enriched.append(det)
                
            _, buffer = cv2.imencode('.jpg', annotated_img)
            res_data = {
                "annotated_image_b64": base64.b64encode(buffer).decode('utf-8'),
                "detections": enriched
            }
        except Exception as e:
            st.error(f"Processing Error: {e}")

        if res_data:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("Annotated Frame")
                img_data = base64.b64decode(res_data["annotated_image_b64"])
                st.image(img_data, width="stretch")
                st.download_button(
                    label="Download Annotated Image",
                    data=img_data,
                    file_name="annotated_image.jpg",
                    mime="image/jpeg",
                    use_container_width=True
                )
            with col2:
                st.subheader("Classification & Recommendations")
                detections = filter_by_confidence(res_data.get("detections", []), saved_threshold)
                render_detections(detections, saved_threshold)

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
            file_bytes = np.asarray(bytearray(webcam_img.read()), dtype=np.uint8)
            image = cv2.imdecode(file_bytes, 1)
            temp_path = "temp_webcam.jpg"
            cv2.imwrite(temp_path, image)
            
            annotated_img, raw_detections = detector_service.detect_objects(temp_path, threshold=saved_threshold, force_groq=force_ai, allow_fallback=allow_fallback)
            
            settings_doc = Repository.get_settings()
            co2_factors = settings_doc.get("co2_factors", settings.CO2_SAVINGS_FACTORS)
            
            enriched = []
            for det in raw_detections:
                rec = RecommendationEngine.get_recommendation(det["object_name"], det["category"])
                det.update(rec)
                det["carbon_saved_kg"] = co2_factors.get(det["category"], 0.0)
                enriched.append(det)
                
            _, buffer = cv2.imencode('.jpg', annotated_img)
            res_data = {
                "annotated_image_b64": base64.b64encode(buffer).decode('utf-8'),
                "detections": enriched
            }
        except Exception as e:
            st.error(f"Processing Error: {e}")

        if res_data:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("Annotated Capture")
                img_data = base64.b64decode(res_data["annotated_image_b64"])
                st.image(img_data, width="stretch")
                st.download_button(
                    label="Download Annotated Capture",
                    data=img_data,
                    file_name="annotated_capture.jpg",
                    mime="image/jpeg",
                    use_container_width=True
                )
            with col2:
                st.subheader("Classification & Recommendations")
                detections = filter_by_confidence(res_data.get("detections", []), saved_threshold)
                render_detections(detections, saved_threshold)

            if detections:
                with col1:
                    save_to_db(detections, key="save_webcam")


# Render the universal sidebar footer (Logout) at the very bottom
render_sidebar_footer()
