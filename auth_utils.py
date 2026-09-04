import streamlit as st
import bcrypt
from database import Repository

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def show_login_form():
    st.markdown("""
    <style>
    /* 1. Hide the sidebar completely for unauthenticated users */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    
    /* 2. Premium Animated Background just for Login */
    .stApp {
        background: 
            radial-gradient(circle at 10% 20%, rgba(31, 155, 98, 0.15), transparent 40%),
            radial-gradient(circle at 90% 80%, rgba(31, 155, 98, 0.1), transparent 40%),
            linear-gradient(135deg, #eefaf1 0%, #fbfefc 100%) !important;
        background-attachment: fixed !important;
    }
    
    /* 3. Push content down slightly for vertical centering */
    .block-container {
        padding-top: 10vh !important;
    }
    
    /* 4. Glassmorphism styling specifically targeting the login form container */
    div[data-testid="stForm"] {
        background: rgba(255, 255, 255, 0.6) !important;
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
        border: 1px solid rgba(255, 255, 255, 0.8) !important;
        border-radius: 24px !important;
        padding: 40px 32px !important;
        box-shadow: 0 20px 50px rgba(16, 42, 31, 0.08), 
                    inset 0 1px 0 rgba(255, 255, 255, 1) !important;
        transition: transform 0.3s ease, box-shadow 0.3s ease !important;
    }
    div[data-testid="stForm"]:hover {
        transform: translateY(-4px) !important;
        box-shadow: 0 30px 60px rgba(16, 42, 31, 0.12) !important;
    }

    /* Target the text inputs specifically inside the login form to look premium */
    div[data-testid="stForm"] input {
        background: rgba(255, 255, 255, 0.9) !important;
        border: 1px solid #dceee2 !important;
        padding: 14px 16px !important;
        border-radius: 12px !important;
        font-size: 1rem !important;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.02) !important;
    }
    div[data-testid="stForm"] input:focus {
        border-color: #1f9b62 !important;
        box-shadow: 0 0 0 4px rgba(31, 155, 98, 0.15) !important;
    }
    
    /* Style the main primary button */
    div[data-testid="stForm"] button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #178a55 0%, #126b44 100%) !important;
        color: white !important;
        border: none !important;
        padding: 12px !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        letter-spacing: 0.5px !important;
        margin-top: 15px !important;
        box-shadow: 0 10px 20px rgba(18, 107, 68, 0.25) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 15px 30px rgba(18, 107, 68, 0.35) !important;
    }
    
    /* Registration Expander Styling */
    div[data-testid="stExpander"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        margin-top: 20px !important;
    }
    div[data-testid="stExpander"] > details {
        border: 1px dashed rgba(31, 155, 98, 0.4) !important;
        border-radius: 16px !important;
        background: rgba(255, 255, 255, 0.4) !important;
    }
    </style>
    
    <div style='text-align: center; margin-bottom: 2rem;'>
        <div style="font-size: 4rem; line-height: 1; margin-bottom: 12px; filter: drop-shadow(0 10px 15px rgba(31,155,98,0.3)); animation: float 6s ease-in-out infinite;">♻️</div>
        <h1 style='color: #103b27; font-weight: 800; font-size: 2.8rem; letter-spacing: -1.5px; margin-bottom: 8px;'>EcoSort AI</h1>
        <p style='color: #5f7868; font-size: 1.1rem; font-weight: 500;'>Intelligent waste tracking & sustainability analytics</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login", use_container_width=True)
            
            if submit_button:
                if not username or not password:
                    st.error("Please enter both username and password")
                    return
                
                try:
                    user_data = Repository.get_user_by_username(username)
                except RuntimeError as e:
                    st.error(f"Database error: {e}")
                    return
                
                if user_data and verify_password(password, user_data.get("hashed_password", "")):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Incorrect username or password")

        with st.expander("Register New User"):
            with st.form("register_form"):
                new_username = st.text_input("New Username")
                new_password = st.text_input("New Password", type="password")
                register_button = st.form_submit_button("Register", use_container_width=True)
                
                if register_button:
                    if not new_username or not new_password:
                        st.error("Please fill in all fields")
                    else:
                        existing = Repository.get_user_by_username(new_username)
                        if existing:
                            st.error("Username already exists")
                        else:
                            hashed = hash_password(new_password)
                            Repository.create_user({
                                "username": new_username, 
                                "hashed_password": hashed
                            })
                            st.success("Registered successfully! You can now login.")

def check_auth():
    if not st.session_state.get("authenticated", False):
        show_login_form()
        st.stop()
    return True

def get_current_user():
    return st.session_state.get("username", "anonymous")

def logout():
    st.session_state.clear()
    st.rerun()