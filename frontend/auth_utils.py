import streamlit as st
import requests
import os
import json
import time

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
            requests.get(health_url, timeout=3)
        except Exception:
            pass


def _post_with_retry(url: str, payload: dict, status_placeholder, max_attempts: int = 6):
    """
    POST with retries to survive a cold-starting backend.
    Render's free tier returns fast 502s while booting (not slow timeouts),
    so we retry with short waits instead of one long timeout.
    Returns (response_or_None, error_message_or_None).
    """
    wait_times = [0, 3, 5, 8, 10, 15]  # seconds between attempts

    for attempt in range(max_attempts):
        if attempt > 0:
            status_placeholder.info(
                f"⏳ Server is waking up, please wait... (attempt {attempt + 1} of {max_attempts})"
            )
            time.sleep(wait_times[attempt])

        try:
            resp = requests.post(url, json=payload, timeout=20)
        except requests.exceptions.RequestException:
            continue  # connection failed entirely, try again

        # 502/503/504 mean the proxy is up but the app isn't ready yet - retry
        if resp.status_code in (502, 503, 504):
            continue

        # Any other response (200, 401, 400, etc.) is a real answer - stop retrying
        return resp, None

    return None, "The server didn't wake up in time. Please try again in a moment."


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
                    status_placeholder = st.empty()
                    resp, err = _post_with_retry(
                        f"{API_BASE_URL}/auth/login",
                        {"username": username, "password": password},
                        status_placeholder
                    )
                    status_placeholder.empty()

                    if err:
                        st.error(err)
                    elif resp.status_code == 200:
                        try:
                            token = resp.json()["access_token"]
                            st.session_state.token = token
                            _save_token(token)
                            st.rerun()
                        except (ValueError, KeyError):
                            st.error("Unexpected response from server. Please try again.")
                    else:
                        content_type = resp.headers.get("content-type", "")
                        if "application/json" in content_type:
                            detail = resp.json().get("detail", "Login failed.")
                        else:
                            detail = f"Login failed (status {resp.status_code}). Please try again."
                        st.error(detail)

        with tab2:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("register_form"):
                new_username = st.text_input("Choose Username", placeholder="e.g. jane_doe")
                new_password = st.text_input("Choose Password", type="password", placeholder="••••••••")
                st.markdown("<br>", unsafe_allow_html=True)
                submit_reg = st.form_submit_button("Register New Account", width="stretch")

                if submit_reg:
                    status_placeholder = st.empty()
                    resp, err = _post_with_retry(
                        f"{API_BASE_URL}/auth/register",
                        {"username": new_username, "password": new_password},
                        status_placeholder
                    )
                    status_placeholder.empty()

                    if err:
                        st.error(err)
                    elif resp.status_code == 200:
                        try:
                            token = resp.json()["access_token"]
                            st.session_state.token = token
                            _save_token(token)
                            st.success("Registration successful! Logging you in...")
                            st.rerun()
                        except (ValueError, KeyError):
                            st.error("Unexpected response from server. Please try again.")
                    else:
                        content_type = resp.headers.get("content-type", "")
                        if "application/json" in content_type:
                            detail = resp.json().get("detail", "Registration failed.")
                        else:
                            detail = f"Registration failed (status {resp.status_code}). Please try again."
                        st.error(detail)

    st.stop()


def get_auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def logout():
    st.session_state.token = None
    _clear_token()
    st.rerun()