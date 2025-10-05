import streamlit as st
from auth import signup, login, logout


def auth_sidebar(fastapi_base_url: str):
    with st.sidebar.expander("🔐 Authentication", expanded=True):
        st.title("🔐 Authentication")

        if not st.session_state["is_authenticated"]:
            choice = st.radio("Choose action:", ["Login", "Signup"],horizontal=True)
            if choice == "Login":
                login(fastapi_base_url)
            else:
                signup(fastapi_base_url)
        else:
            st.sidebar.success("✅ Logged in")
            if st.sidebar.button("Logout"):
                logout(fastapi_base_url)

def display_chat_history():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])