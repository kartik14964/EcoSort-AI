import streamlit as st
import requests
import os
import json
import logging
import time
import threading
from urllib.parse import urlsplit, urlunsplit

API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000/api")
TOKEN_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".ecosort_token")

# Render free-tier cold starts commonly take 30-60s, sometimes more
# (especially if the app opens a DB connection on startup). Retry on a
# time budget instead of a fixed number of attempts, so we don't give
# up right before the backend finishes booting.
WAKE_TOTAL_BUDGET_SECONDS = 150
REQUEST_TIMEOUT_SECONDS = 70
POLL_INTERVAL_SECONDS = 8

logger = logging.getLogger(__name__)

# This state intentionally lives outside Streamlit session state.  The warm-up
# request is shared by all sessions in this process, and the worker thread must
# not read or write Streamlit session state.
_backend_wake_lock = threading.Lock()
_backend_wake_complete = threading.Event()
_backend_wake_started = False
_backend_wake_error: str | None = None


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


def _health_url() -> str:
    """Return the backend health URL without modifying the hostname.

    ``str.replace('/api', '/health')`` also changes a hostname containing
    ``api``.  Build the URL from its parsed path instead.
    """
    parsed = urlsplit(API_BASE_URL)
    api_path = parsed.path.rstrip("/")
    health_path = f"{api_path[:-4]}/health" if api_path.endswith("/api") else "/health"
    return urlunsplit((parsed.scheme, parsed.netloc, health_path, "", ""))


def _wake_backend():
    """Start exactly one background health request for this process."""
    global _backend_wake_started, _backend_wake_error

    with _backend_wake_lock:
        if _backend_wake_started:
            return
        _backend_wake_started = True

        def _ping():
            global _backend_wake_error
            started = time.monotonic()
            try:
                response = requests.get(_health_url(), timeout=(15, REQUEST_TIMEOUT_SECONDS))
                response.raise_for_status()
                logger.info("Backend wake check completed in %.1fs", time.monotonic() - started)
            except requests.RequestException as exc:
                _backend_wake_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Backend wake check failed after %.1fs: %s",
                    time.monotonic() - started,
                    _backend_wake_error,
                )
            finally:
                _backend_wake_complete.set()

        threading.Thread(target=_ping, daemon=True, name="ecosort-backend-wake").start()


def _wait_for_backend_wake(status_placeholder) -> None:
    """Avoid racing an auth POST against the page-load cold-start request."""
    started = time.monotonic()
    while not _backend_wake_complete.wait(timeout=1):
        elapsed = int(time.monotonic() - started)
        status_placeholder.info(f"⏳ Server is waking up, please wait... ({elapsed}s elapsed)")

    if _backend_wake_error:
        # The auth request below remains the source of truth.  This log line is
        # essential when a Render proxy or egress path differs from local curl.
        logger.info("Proceeding with auth after failed wake check: %s", _backend_wake_error)

def _post_with_retry(url: str, payload: dict, status_placeholder, total_budget: int = WAKE_TOTAL_BUDGET_SECONDS):
    """
    POST with retries to survive a cold-starting backend.
    Retries on a TIME BUDGET (not a fixed attempt count) so a slow
    cold start doesn't get cut off early. Backs off gradually so we
    don't trip Render's rate limiting while it wakes up.
    Returns (response_or_None, error_message_or_None).
    """
    start = time.monotonic()
    attempt = 0
    wait = 5
    last_error = None

    while time.monotonic() - start < total_budget:
        attempt += 1
        elapsed = int(time.monotonic() - start)

        if attempt > 1:
            status_placeholder.info(
                f"⏳ Server is waking up, please wait... ({elapsed}s elapsed)"
            )

        try:
            request_started = time.monotonic()
            resp = requests.post(url, json=payload, timeout=(15, REQUEST_TIMEOUT_SECONDS))
            logger.info(
                "Auth request attempt %s completed in %.1fs with status %s",
                attempt,
                time.monotonic() - request_started,
                resp.status_code,
            )
        except requests.exceptions.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Auth request attempt %s failed: %s", attempt, last_error)
            time.sleep(wait)
            wait = min(wait + 2, 10)
            continue

        # 429 = rate limited, 502/503/504 = proxy up but app not ready - retry both
        if resp.status_code == 429 or resp.status_code in (502, 503, 504):
            time.sleep(wait)
            wait = min(wait + 2, 10)
            continue

        # Any other response (200, 401, 400, etc.) is a real answer - stop retrying
        return resp, None

    logger.error("Auth request exhausted its %ss wake budget; last error: %s", total_budget, last_error)
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
                    _wait_for_backend_wake(status_placeholder)
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
                    _wait_for_backend_wake(status_placeholder)
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
