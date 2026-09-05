import streamlit as st
from app_utils import inject_css
from ai_services import AIAssistantService
from auth_utils import check_auth, render_sidebar_footer, get_current_user

# ✅ Must be first Streamlit call
st.set_page_config(page_title="EcoSort AI - Assistant", page_icon="🤖", layout="wide", initial_sidebar_state="expanded" if st.session_state.get("authenticated", False) else "collapsed")
inject_css()

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

# Suggested questions
st.markdown("---")
st.markdown("### 💡 Quick Questions")
col1, col2, col3 = st.columns(3)
quick_prompt = None

if col1.button("🌍 What is my carbon offset?"):
    quick_prompt = "What is my carbon offset?"
if col2.button("♻️ What is my recycling rate?"):
    quick_prompt = "What is my recycling rate?"
if col3.button("🥤 How much plastic did I recycle?"):
    quick_prompt = "How much plastic did I recycle?"

# React to user input
if prompt := st.chat_input("What is your recycling question?") or quick_prompt:
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Thinking..."):
        try:
            # Call the Groq model
            assistant = AIAssistantService()
            response = assistant.answer_query(st.session_state.messages)
            
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(response)
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            st.error(f"Failed to get response from AI: {e}")


# Render the universal sidebar footer (Logout) at the very bottom
render_sidebar_footer()
