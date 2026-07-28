import os
import streamlit as st
import requests

REACT_LOGIN_URL = os.environ.get("REACT_LOGIN_URL", "http://localhost:5173/")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api")


def _redirect_to_login():
    st.markdown(
        f'<meta http-equiv="refresh" content="0; url={REACT_LOGIN_URL}">',
        unsafe_allow_html=True
    )
    st.stop()


def check_auth():
    # Step 1: grab token from React redirect query param
    qp_token = st.query_params.get("token")
    if qp_token:
        st.session_state.token = qp_token
        st.query_params.clear()
        st.rerun()

    # Step 2: check session state only — no file cache
    token = st.session_state.get("token")
    if not token:
        _redirect_to_login()

    # Step 3: verify token against API
    try:
        resp = requests.get(
            f"{API_BASE_URL}/settings",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if resp.status_code == 401:
            st.session_state.clear()
            _redirect_to_login()
    except Exception:
        pass  # API down — allow session token

    return True


def get_auth_headers():
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def logout():
    st.session_state.clear()
    _redirect_to_login()