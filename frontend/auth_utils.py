import json
import logging
import os
import time
import requests
import streamlit as st

# Ensure the URL uses HTTPS to prevent browser security blocks
API_BASE_URL = os.environ.get("API_URL", "https://ecosort-backend-yz6m.onrender.com/api")
TOKEN_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".ecosort_token")

logger = logging.getLogger(__name__)

def _save_token(token: str):
    with open(TOKEN_CACHE_FILE, "w") as f:
        json.dump({"token": token}, f)

def _load_token() -> str | None:
    try:
        if os.path.exists(TOKEN_CACHE_FILE):
            with open(TOKEN_CACHE_FILE, "r") as f:
                return json.load(f).get("token")
    except Exception:
        return None
    return None

def _clear_token():
    if os.path.exists(TOKEN_CACHE_FILE):
        os.remove(TOKEN_CACHE_FILE)

def _wake_up_server(status_placeholder):
    """Pings the health endpoint to wake up Render cleanly with user feedback."""
    health_url = API_BASE_URL.replace("/api", "/health")
    
    # Quick check if already awake
    try:
        resp = requests.get(health_url, timeout=3)
        if resp.status_code == 200:
            return True
    except Exception:
        pass

    # If sleeping, show a friendly status and wait for it to boot
    status_placeholder.info("⏳ Waking up secure server from sleep (this takes about 30 seconds)...")
    
    for attempt in range(12):  # Try for up to 48 seconds
        try:
            resp = requests.get(health_url, timeout=5)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(4)
        
    return False

def check_auth():
    if "token" not in st.session_state or not st.session_state.token:
        st.session_state.token = _load_token()

    if st.session_state.token:
        return True

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown(
        "<h1 style='text-align: center; color: #0f172a; font-weight: 700; letter-spacing: -1px;'>EcoSort Secure Gateway</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: #64748b; font-size: 1.1rem;'>Your private sustainability dashboard.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    _, col2, _ = st.columns([1, 1.5, 1])

    with col2:
        tab1, tab2 = st.tabs(["Log In", "Create Account"])

        with tab1:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="e.g. admin")
                password = st.text_input("Password", type="password", placeholder="••••••••", autocomplete="off")
                submit = st.form_submit_button("Log In to Dashboard", use_container_width=True)

                if submit:
                    if not username or not password:
                        st.error("Please enter both username and password.")
                    else:
                        status_placeholder = st.empty()
                        
                        # 1. Ensure server is awake before hitting auth
                        is_awake = _wake_up_server(status_placeholder)
                        if not is_awake:
                            status_placeholder.error("❌ Server took too long to wake up. Please try again.")
                            st.stop()

                        # 2. Perform Login Request
                        status_placeholder.info("🚀 Authenticating...")
                        try:
                            resp = requests.post(
                                f"{API_BASE_URL}/auth/login",
                                json={"username": username, "password": password},
                                timeout=15
                            )
                            status_placeholder.empty()

                            if resp.status_code == 200:
                                token = resp.json().get("access_token")
                                if token:
                                    st.session_state.token = token
                                    _save_token(token)
                                    st.rerun()
                                else:
                                    st.error("❌ Authentication error: Token missing from response.")
                            else:
                                data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                                detail = data.get("detail", f"Login failed (status {resp.status_code}).")
                                st.error(f"❌ {detail}")
                        except Exception as e:
                            status_placeholder.empty()
                            st.error(f"❌ Connection error: {e}")

        with tab2:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("register_form"):
                new_username = st.text_input("Choose Username", placeholder="e.g. jane_doe")
                new_password = st.text_input("Choose Password", type="password", placeholder="••••••••", autocomplete="new-password")
                submit_reg = st.form_submit_button("Register New Account", use_container_width=True)

                if submit_reg:
                    if not new_username or not new_password:
                        st.error("Please choose a username and password.")
                    else:
                        status_placeholder = st.empty()
                        
                        is_awake = _wake_up_server(status_placeholder)
                        if not is_awake:
                            status_placeholder.error("❌ Server took too long to wake up. Please try again.")
                            st.stop()

                        status_placeholder.info("🚀 Registering account...")
                        try:
                            resp = requests.post(
                                f"{API_BASE_URL}/auth/register",
                                json={"username": new_username, "password": new_password},
                                timeout=15
                            )
                            status_placeholder.empty()

                            if resp.status_code == 200:
                                token = resp.json().get("access_token")
                                if token:
                                    st.session_state.token = token
                                    _save_token(token)
                                    st.success("Account created! Logging you in...")
                                    st.rerun()
                                else:
                                    st.error("❌ Registration error: Token missing from response.")
                            else:
                                data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
                                detail = data.get("detail", f"Registration failed (status {resp.status_code}).")
                                st.error(f"❌ {detail}")
                        except Exception as e:
                            status_placeholder.empty()
                            st.error(f"❌ Connection error: {e}")

    st.stop()

def get_auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

def logout():
    st.session_state.token = None
    _clear_token()
    st.rerun()