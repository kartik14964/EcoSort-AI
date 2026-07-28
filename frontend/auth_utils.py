import json
import os
import streamlit as st

TOKEN_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".ecosort_token")
REACT_LOGIN_URL = os.environ.get("REACT_LOGIN_URL", "http://localhost:5173/")


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


def check_auth():
    # Token handed off from the React login page via ?token=... redirect
    qp_token = st.query_params.get("token")
    if qp_token:
        st.session_state.token = qp_token
        _save_token(qp_token)
        st.query_params.clear()
        st.rerun()

    if "token" not in st.session_state or not st.session_state.token:
        st.session_state.token = _load_token()

    if st.session_state.token:
        return True

    # Not logged in — send them to the React login page
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown(
        "<h1 style='text-align: center; color: #0f172a; font-weight: 700;'>EcoSort Secure Gateway</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: #64748b; font-size: 1.1rem;'>Your private sustainability dashboard.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<br><br>", unsafe_allow_html=True)

    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        st.markdown(
            f"""
            <div style="text-align:center;">
                <a href="{REACT_LOGIN_URL}" target="_self" style="
                    display:inline-block; padding: 14px 32px;
                    background: linear-gradient(120deg, #178a55, #1f9b62);
                    color: white; border-radius: 10px; font-weight: 600;
                    text-decoration: none; font-size: 1.05rem;">
                    Go to Secure Login →
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.stop()


def get_auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def logout():
    st.session_state.token = None
    _clear_token()
    st.rerun()