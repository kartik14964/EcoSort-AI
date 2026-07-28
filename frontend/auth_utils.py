import json
import logging
import os
import threading
import requests
import streamlit as st
import streamlit.components.v1 as components

API_BASE_URL = os.environ.get("API_URL", "https://ecosort-backend-yz6m.onrender.com/api")
TOKEN_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".ecosort_token")

BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

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
    """Fires a background request to wake up Render."""
    try:
        requests.get(
            "https://ecosort-backend-yz6m.onrender.com/health",
            headers=BROWSER_HEADERS,
            timeout=3,
        )
    except Exception:
        pass

def _client_side_auth(endpoint_url: str, payload: dict, action_name: str):
    """Executes authentication from the user's browser to bypass Render 429 errors."""
    component_id = f"auth_fetch_{abs(hash(endpoint_url + action_name))}"
    payload_json_str = json.dumps(payload)

    html_code = f"""
        <div id="status-{component_id}" style="font-family: sans-serif; font-size: 0.9rem; color: #334155; padding: 4px 0;">
            ⏳ Connecting to server (this may take up to a minute if waking up)...
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
                    body: JSON.stringify({payload_json_str})
                }});

                let data = {{}};
                try {{
                    data = await response.json();
                }} catch (e) {{
                    console.log("Response was not JSON");
                }}

                if (response.ok) {{
                    const token = data.access_token || data.token;
                    if (token) {{
                        statusEl.innerHTML = "✅ Success! Redirecting...";
                        const currentUrl = new URL(window.parent.location.href);
                        currentUrl.searchParams.set("client_token", token);
                        window.parent.location.href = currentUrl.toString();
                    }} else {{
                        statusEl.innerHTML = "❌ Error: Token missing.";
                        statusEl.style.color = "#dc2626";
                    }}
                }} else {{
                    let errorMsg = data.detail || data.message || "Authentication failed.";
                    if (typeof errorMsg === 'object') errorMsg = JSON.stringify(errorMsg);
                    statusEl.innerHTML = "❌ " + errorMsg;
                    statusEl.style.color = "#dc2626";
                }}
            }} catch (err) {{
                console.error(err);
                statusEl.innerHTML = "❌ Network error: Could not reach server.";
                statusEl.style.color = "#dc2626";
            }}
        }}
        performAuth();
        </script>
        """
    components.html(html_code, height=50)

def check_auth():
    query_params = st.query_params
    if "client_token" in query_params:
        token_val = query_params["client_token"]
        if isinstance(token_val, list):
            token_val = token_val[0]
        st.session_state.token = token_val
        _save_token(token_val)
        st.query_params.clear()
        st.rerun()

    if "token" not in st.session_state or not st.session_state.token:
        st.session_state.token = _load_token()

    if st.session_state.token:
        return True

    if "woke_up" not in st.session_state:
        st.session_state.woke_up = True
        threading.Thread(target=_ping_backend_background, daemon=True).start()

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
                        st.info("🚀 Authenticating...")
                        _client_side_auth(f"{API_BASE_URL}/auth/login", {"username": username, "password": password}, "login")

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
                        st.info("🚀 Registering...")
                        _client_side_auth(f"{API_BASE_URL}/auth/register", {"username": new_username, "password": new_password}, "registration")

    st.stop()

def get_auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

def logout():
    st.session_state.token = None
    _clear_token()
    st.query_params.clear()
    st.rerun()