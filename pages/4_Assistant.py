import streamlit as st
from ai_services import AIAssistantService
from auth_utils import check_auth, get_current_user

# ✅ Must be first Streamlit call
st.set_page_config(page_title="EcoSort AI - Assistant", page_icon="🤖", layout="wide")

check_auth()

st.title("🤖 AI Sustainability Assistant")
st.write("Ask questions about recycling, local regulations, or how to reduce your carbon footprint.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("What is your recycling question?"):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Thinking..."):
        try:
            # Call the Groq model
            assistant = AIAssistantService()
            response = assistant.get_response(prompt)
            
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(response)
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            st.error(f"Failed to get response from AI: {e}")
