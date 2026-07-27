import streamlit as st
import requests
import os
import json
import time
import threading

API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000/api")
TOKEN_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".ecosort_token")

# Render free-tier cold starts commonly take 30-60s, sometimes more
# (especially if the app opens a DB connection on startup). Retry on a
# time budget instead of a fixed number of attempts, so we don't give
# up right before the backend finishes booting.
WAKE_TOTAL_BUDGET_SECONDS = 100
REQUEST_TIMEOUT_SECONDS = 15
POLL_INTERVAL_SECONDS = 3


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
    """Fire-and-forget background ping to start waking a sleeping
    backend the instant the page loads, without blocking the render."""
    if "backend_wake_started" in st.session_state:
        return
    st.session_state.backend_wake_started = True

    def _ping():
        health_url = API_BASE_URL.replace("/api", "/health")
        try:
            requests.get(health_url, timeout=REQUEST_TIMEOUT_SECONDS)
        except Exception:
            pass

    threading.Thread(target=_ping, daemon=True).start()


def _post_with_retry(url: str, payload: dict, status_placeholder, total_budget: int = WAKE_TOTAL_BUDGET_SECONDS):
    """
    POST with retries to survive a cold-starting backend.
    Retries on a TIME BUDGET (not a fixed attempt count) so a slow
    cold start doesn't get cut off early. Keeps polling every few
    seconds until either a real response comes back or the budget
    runs out.
    Returns (response_or_None, error_message_or_None).
    """
    start = time.time()
    attempt = 0

    while time.time() - start < total_budget:
        attempt += 1
        elapsed = int(time.time() - start)

        if attempt > 1:
            status_placeholder.info(
                f"⏳ Server is waking up, please wait... ({elapsed}s elapsed)"
            )

        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.RequestException:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        # 502/503/504 mean the proxy is up but the app isn't ready yet - retry
        if resp.status_code in (502, 503, 504):
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        # Any other response (200, 401, 400, etc.) is a real answer - stop retrying
        return resp, None

    return None, "The server is taking a bit longer than usual to wake up. Please try logging in again — it should be ready now."


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