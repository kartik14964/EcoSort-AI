import streamlit as st
import requests
import os

st.set_page_config(page_title="EcoSort AI - Assistant", page_icon="💬", layout="wide")

from frontend.auth_utils import check_auth, get_auth_headers
check_auth()

API_URL = os.environ.get("API_URL", "http://localhost:8000/api")

def load_css():
    css_file = os.path.join(os.path.dirname(__file__), "..", "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

st.title("💬 AI Sustainability Assistant")
st.write("Ask natural language questions about your recycling rates, waste volumes, carbon offsets, and trends.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I am your EcoSort Sustainability Assistant. Ask me anything about your waste metrics!"}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

st.write("💡 **Quick Questions:**")
col1, col2, col3, col4 = st.columns(4)
suggestions = [
    "How much plastic was detected this week?",
    "What is our recycling rate?",
    "How much CO2 did we save?",
    "Which waste category is increasing?"
]

selected_suggestion = None
with col1:
    if st.button(suggestions[0], width="stretch"):
        selected_suggestion = suggestions[0]
with col2:
    if st.button(suggestions[1], width="stretch"):
        selected_suggestion = suggestions[1]
with col3:
    if st.button(suggestions[2], width="stretch"):
        selected_suggestion = suggestions[2]
with col4:
    if st.button(suggestions[3], width="stretch"):
        selected_suggestion = suggestions[3]

user_input = st.chat_input("Ask a sustainability question...")
query = selected_suggestion or user_input

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    with st.spinner("Analyzing data logs..."):
        reply = None
        try:
            response = requests.post(
                f"{API_URL}/chatbot",
                json={"message": query},
                timeout=10,
                headers=get_auth_headers()
            )
            if response.status_code == 200:
                reply = response.json()["reply"]
            else:
                reply = f"⚠️ Could not process that (status {response.status_code})."
        except Exception as e:
            reply = f"⚠️ Cannot connect to backend: {e}"

    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.write(reply)
    st.rerun()