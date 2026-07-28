import json
import logging
import os
import threading
import requests
import streamlit as st
import streamlit.components.v1 as components

API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000/api")
TOKEN_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".ecosort_token")

REQUEST_TIMEOUT_SECONDS = 90
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

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
        requests.get(
            "https://ecosort-backend-yz6m.onrender.com/health",
            headers=BROWSER_HEADERS,
            timeout=3,
        )
    except Exception:
        pass


def _client_side_auth(endpoint_url: str, payload: dict, action_name: str, placeholder):
    """Executes authentication fetch() directly from the user's browser using JavaScript,
    bypassing Render server-side IP blocks (429 Too Many Requests) and utilizing the visitor's clean IP.
    """
    component_id = f"auth_fetch_{abs(hash(endpoint_url + action_name))}"
    
    # Clean JSON payload string for JS injection
    payload_json = json.dumps(payload)
    
    html_code = f"""
    <div id="{component_id}" style="font-family: sans-serif; color: #475569; padding: 10px 0;">
        <p id="status-{component_id}" style="font-weight: 500; font-size: 0.95rem; margin: 0;">⏳ Processing {action_name}...</p>
    </div>
    <script>
    async function performAuth() {{
        const statusEl = document.getElementById("status-{component_id}");
        try {{
            const response = await fetch("{endpoint_url}", {{
                method: "POST",
                headers: {{
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }},
                body: {payload_json}
            }});
            
            const data = await response.json();
            
            if (response.ok) {{
                statusEl.innerHTML = "✅ Success! Redirecting...";
                // Send token back to Streamlit via URL parameters and trigger top-level refresh
                const token = data.access_token || data.token;
                if (token) {{
                    const currentUrl = new URL(window.parent.location.href);
                    currentUrl.searchParams.set("client_token", token);
                    window.parent.location.href = currentUrl.toString();
                }} else {{
                    statusEl.innerHTML = "❌ Error: Token missing in response.";
                    statusEl.style.color = "#dc2626";
                }}
            }} else {{
                statusEl.innerHTML = "❌ " + (data.detail || data.message || "{action_name} failed.");
                statusEl.style.color = "#dc2626";
            }}
        }} catch (err) {{
            statusEl.innerHTML = "❌ Network error: Could not connect to server.";
            statusEl.style.color = "#dc2626";
        }}
    }}
    performAuth();
    </script>
    """
    components.html(html_code, height=60)


def check_auth():
    # Capture token if passed back from browser client-side fetch script via URL query param
    query_params = st.query_params
    if "client_token" in query_params:
        token_val = query_params["client_token"]
        if isinstance(token_val, list):
            token_val = token_val[0]
        st.session_state.token = token_val
        _save_token(token_val)
        # Clear query params from URL cleanly
        st.query_params.clear()
        st.rerun()

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
                    "Password", type="password", placeholder="••••••••", autocomplete="off"
                )
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button(
                    "Log In to Dashboard", use_container_width=True
                )

                if submit:
                    if not username or not password:
                        st.error("Please enter both username and password.")
                    else:
                        status_placeholder = st.empty()
                        status_placeholder.info("🚀 Initiating secure client-side login...")
                        _client_side_auth(
                            f"{API_BASE_URL}/auth/login",
                            {"username": username, "password": password},
                            "login",
                            status_placeholder,
                        )

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
                    if not new_username or not new_password:
                        st.error("Please choose a username and password.")
                    else:
                        status_placeholder = st.empty()
                        status_placeholder.info("🚀 Initiating secure client-side registration...")
                        _client_side_auth(
                            f"{API_BASE_URL}/auth/register",
                            {"username": new_username, "password": new_password},
                            "registration",
                            status_placeholder,
                        )

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
    st.query_params.clear()
    st.rerun()