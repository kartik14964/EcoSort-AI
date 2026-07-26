import streamlit as st
import requests
from frontend.auth_utils import check_auth, get_auth_headers
import os

# Page Setup
st.set_page_config(page_title="EcoSort AI - Chatbot Assistant", page_icon="💬", layout="wide")

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

st.title("💬 AI Sustainability Assistant")
st.write("Ask natural language questions about your recycling rates, waste volumes, carbon offsets, and trends.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I am your EcoSort Sustainability Assistant. I can help analyze your logged metrics and trends. Ask me anything or select one of the suggestions below!"}
    ]

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Suggestion Chips
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

# Chat input
user_input = st.chat_input("Ask a sustainability question...")

# Process input
query = selected_suggestion or user_input

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    with st.spinner("Analyzing data logs..."):
        reply = None
        try:
            response = requests.post(f"{API_URL}/chatbot", json={"message": query}, timeout=10, headers=get_auth_headers())
            if response.status_code == 200:
                reply = response.json()["reply"]
            else:
                reply = f"⚠️ Sorry, I couldn't process that (status {response.status_code}). Please try again."
        except Exception as e:
            reply = f"⚠️ Cannot connect to the backend right now: {e}"

    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.write(reply)
        st.rerun()