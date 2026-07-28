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
    """Explicitly wakes up Render, handling cold-start SSL/TCP drops."""
    health_url = API_BASE_URL.replace("/api", "/health")
    
    status_placeholder.info("⏳ Connecting to backend service...")
    
    # Try an initial quick check
    try:
        resp = requests.get(health_url, timeout=5)
        if resp.status_code == 200:
            return True
    except Exception:
        pass  # Expected if sleeping

    status_placeholder.info("⏳ Server is waking up from sleep. This takes about 30–50 seconds...")
    
    # Render cold starts require patience with connection retries
    for attempt in range(1, 16):  # 15 attempts * 4 seconds = 60 seconds
        try:
            # Using a session or clean request to clear stale socket states
            resp = requests.get(health_url, timeout=10, headers={"Cache-Control": "no-cache"})
            if resp.status_code == 200:
                return True
        except requests.exceptions.SSLError:
            # SSL handshake failed because container is still booting its web proxy
            logger.info("SSL handshake waiting for Render container to initialize (attempt %s)", attempt)
        except requests.exceptions.ConnectionError:
            # Connection refused/reset because port isn't open yet
            logger.info("Connection waiting for Render service to bind port (attempt %s)", attempt)
        except Exception as e:
            logger.info("Wake-up attempt %s encountered: %s", attempt, e)
            
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