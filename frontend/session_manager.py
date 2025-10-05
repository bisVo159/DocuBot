import streamlit as st

def init_session_state():
    if "is_authenticated" not in st.session_state:
        st.session_state["is_authenticated"] = False
    if "access_token" not in st.session_state:
        st.session_state["access_token"] = None
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
        st.session_state.messages.append({"role": "assistant", "content": "I am a helpful assistant that helps patients to connect their doctors."})