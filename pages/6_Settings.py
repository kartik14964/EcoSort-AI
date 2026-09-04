import streamlit as st
from utils import inject_css
from auth_utils import check_auth
from database import Repository
from utils import settings

st.set_page_config(page_title="EcoSort AI - Settings", page_icon="⚙️", layout="wide")
inject_css()
check_auth()

st.title("⚙️ Settings")
st.write("Configure your EcoSort AI experience.")

try:
    settings_doc = Repository.get_settings()
    co2_factors = settings_doc.get("co2_factors", settings.CO2_SAVINGS_FACTORS)
except Exception:
    co2_factors = settings.CO2_SAVINGS_FACTORS.copy()

st.markdown("---")
st.subheader("Carbon Offset Factors (kg CO₂ per item)")
st.write("Adjust the estimated carbon savings for each material category.")

# Create columns for factors
cols = st.columns(3)
new_factors = {}
for i, (category, current_val) in enumerate(co2_factors.items()):
    with cols[i % 3]:
        new_factors[category] = st.number_input(
            f"{category}", 
            value=float(current_val), 
            step=0.1, 
            min_value=0.0, 
            format="%.3f"
        )

st.markdown("---")
if st.button("💾 Save All Settings"):
    try:
        Repository.update_settings({
            "co2_factors": new_factors
        })
        st.success("Settings saved successfully!")
    except Exception as e:
        st.error(f"Failed to save settings: {e}")
