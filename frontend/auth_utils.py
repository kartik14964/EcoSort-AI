import streamlit as st
import requests
import os
import json

API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000/api")
TOKEN_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".ecosort_token")

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
def _wake_backend():
    """Fire a silent, best-effort ping to wake a sleeping backend early."""
    if "backend_pinged" not in st.session_state:
        st.session_state.backend_pinged = True
        try:
            health_url = API_BASE_URL.replace("/api", "/health")
            requests.get(health_url, timeout=2)
        except Exception:
            pass  # don't block page load if this fails or is still booting


def check_auth():
    _wake_backend()

    if "token" not in st.session_state or not st.session_state.token:
        st.session_state.token = _load_token()

    if st.session_state.token:
        return True

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #0f172a; font-weight: 700; letter-spacing: -1px;'>EcoSort Secure Gateway</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.1rem;'>Your private sustainability dashboard.</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    _, col2, _ = st.columns([1, 1.5, 1])

    with col2:
        tab1, tab2 = st.tabs(["Log In", "Create Account"])

        with tab1:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="e.g. admin")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button("Log In to Dashboard", width="stretch")

                if submit:
                    try:
                        with st.spinner("Connecting... this can take up to a minute if the server was asleep."):
                            resp = requests.post(
                                f"{API_BASE_URL}/auth/login",
                                json={"username": username, "password": password},
                                timeout=90
                            )
                        if resp.status_code == 200:
                            token = resp.json()["access_token"]
                            st.session_state.token = token
                            _save_token(token)
                            st.rerun()
                        else:
                            try:
                                detail = resp.json().get("detail", "Login failed.")
                            except Exception:
                                detail = "Login failed. Please try again."
                            st.error(detail)
                    except Exception as e:
                        st.error(f"Cannot connect to backend: {e}. If the server was asleep, please wait a moment and try again.")

        with tab2:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("register_form"):
                new_username = st.text_input("Choose Username", placeholder="e.g. jane_doe")
                new_password = st.text_input("Choose Password", type="password", placeholder="••••••••")
                st.markdown("<br>", unsafe_allow_html=True)
                submit_reg = st.form_submit_button("Register New Account", width="stretch")

                if submit_reg:
                    try:
                        resp = requests.post(
                            f"{API_BASE_URL}/auth/register",
                            json={"username": new_username, "password": new_password}
                        )
                        if resp.status_code == 200:
                            token = resp.json()["access_token"]
                            st.session_state.token = token
                            _save_token(token)
                            st.success("Registration successful! Logging you in...")
                            st.rerun()
                        else:
                            st.error(resp.json().get("detail", "Registration failed."))
                    except Exception as e:
                        st.error(f"Cannot connect to backend: {e}")

    st.stop()


def get_auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def logout():
    st.session_state.token = None
    _clear_token()
    st.rerun()