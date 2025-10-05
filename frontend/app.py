import streamlit as st
import requests
from ui_components import auth_sidebar, display_chat_history
from session_manager import init_session_state
from chat_api import chat_with_backend_agent
from config import FRONTEND_CONFIG

st.title("🤖 DocuBot – Doctor Appointment Assistant")

st.markdown(
    "Welcome! I can help you **check doctor availability, book, cancel, or reschedule appointments**. "
    "Please login to continue."
)

fastapi_base_url=FRONTEND_CONFIG['FASTAPI_BASE_URL']

st.set_page_config(page_title="DocuBot", page_icon="🤖")

init_session_state()
auth_sidebar(fastapi_base_url)

def main():
    display_chat_history()

    if prompt := st.chat_input("💬 Enter your query"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        status_holder = {"box": None}
        status_placeholder = st.empty()
        chat_area = st.chat_message("assistant").empty()
        try:
            chat_with_backend_agent(fastapi_base_url, prompt,chat_area,status_holder,status_placeholder)
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Connection error: {e}")
        except Exception as e:
            st.error(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    main()