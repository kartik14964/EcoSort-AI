import streamlit as st
from streamlit_cookies_controller import CookieController
controller = CookieController()
st.write(controller.get("test"))
