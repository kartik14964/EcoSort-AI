import json
import logging
import os
import threading
import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000/api")
TOKEN_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".ecosort_token")

REQUEST_TIMEOUT_SECONDS = 90

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


def _ping_backend_background():
    """Fires a non-blocking background request to wake up the Render service immediately on app load."""
    try:
        requests.get("https://ecosort-backend-yz6m.onrender.com/health", timeout=3)
    except Exception:
        pass


def _post_once(url: str, payload: dict, status_placeholder, timeout: int = REQUEST_TIMEOUT_SECONDS):
    """Send exactly one request. No retries, no backoff — if it fails, it fails."""
    status_placeholder.info("⏳ Connecting to server, please wait...")
    try:
        resp = requests.post(url, json=payload, timeout=(15, timeout))
        logger.info("Auth request completed with status %s", resp.status_code)
        return resp, None
    except requests.exceptions.RequestException as exc:
        logger.warning("Auth request failed: %s", exc)
        return None, f"Could not reach the server: {exc}"


def check_auth():
    if "token" not in st.session_state or not st.session_state.token:
        st.session_state.token = _load_token()

    if st.session_state.token:
        return True

    # Fire a background thread to wake up Render the exact moment the login page loads
    if "woke_up" not in st.session_state:
        st.session_state.woke_up = True
        threading.Thread(target=_ping_backend_background, daemon=True).start()

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown(
        "<h1 style='text-align: center; color: #0f172a; font-weight: 700;"
        " letter-spacing: -1px;'>EcoSort Secure Gateway</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: #64748b; font-size:"
        " 1.1rem;'>Your private sustainability dashboard.</p>",
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
                password = st.text_input(
                    "Password", type="password", placeholder="••••••••"
                )
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button(
                    "Log In to Dashboard", use_container_width=True
                )

                if submit:
                    status_placeholder = st.empty()
                    resp, err = _post_once(
                        f"{API_BASE_URL}/auth/login",
                        {"username": username, "password": password},
                        status_placeholder,
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
                            st.error(
                                "Unexpected response from server. Please try again."
                            )
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
                new_username = st.text_input(
                    "Choose Username", placeholder="e.g. jane_doe"
                )
                new_password = st.text_input(
                    "Choose Password", type="password", placeholder="••••••••", autocomplete="new-password"
                )
                st.markdown("<br>", unsafe_allow_html=True)
                submit_reg = st.form_submit_button(
                    "Register New Account", use_container_width=True
                )

                if submit_reg:
                    status_placeholder = st.empty()
                    resp, err = _post_once(
                        f"{API_BASE_URL}/auth/register",
                        {"username": new_username, "password": new_password},
                        status_placeholder,
                    )
                    status_placeholder.empty()

                    if err:
                        st.error(err)
                    elif resp.status_code == 200:
                        try:
                            token = resp.json()["access_token"]
                            st.session_state.token = token
                            _save_token(token)
                            st.success(
                                "Registration successful! Logging you in..."
                            )
                            st.rerun()
                        except (ValueError, KeyError):
                            st.error(
                                "Unexpected response from server. Please try again."
                            )
                    else:
                        content_type = resp.headers.get("content-type", "")
                        if "application/json" in content_type:
                            detail = resp.json().get(
                                "detail", "Registration failed."
                            )
                        else:
                            detail = f"Registration failed (status {resp.status_code}). Please try again."
                        st.error(detail)

    st.stop()


def get_auth_headers():
    return (
        {"Authorization": f"Bearer {st.session_state.token}"}
        if st.session_state.token
        else {}
    )


def logout():
    st.session_state.token = None
    _clear_token()
    st.rerun()