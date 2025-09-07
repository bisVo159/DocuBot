import streamlit as st
import json
import requests

st.set_page_config(page_title="DocuBot", page_icon="🤖")

# Title
st.title("🤖 DocuBot – Doctor Appointment Assistant")

st.markdown(
    "Welcome! I can help you **check doctor availability, book, cancel, or reschedule appointments**. "
    "Just type your request below 👇"
)

# ---- Form Section ----
with st.form("agent_form"):
    user_input = st.text_input("💬 Enter your query:")
    submitted = st.form_submit_button("Run Agent")

# ---- Placeholders for streaming ----
status_placeholder = st.empty()  # Tool status will appear here
chat_area = st.empty()           # Agent messages will appear here
status_holder = {"box": None}
docubot_reply = ""  # running string buffer

# ---- Handle form submission ----
if submitted and user_input:
    with requests.post(
        "http://localhost:8000/execute",
        json={"patient_id": 1234567, "message": user_input},
        stream=True,
    ) as r:
        for chunk in r.iter_lines():
            if not chunk:
                continue

            try:
                data = json.loads(chunk.decode("utf-8"))
            except Exception as e:
                st.error(f"Failed to parse chunk: {chunk}")
                continue

            # ---- Tool message ----
            if data.get("type") == "tool":
                tool_name = data.get("tool_name", "tool")
                if status_holder["box"] is None:
                    status_holder["box"] = status_placeholder.status(
                        f"🔧 Using `{tool_name}` …", expanded=True
                    )
                else:
                    status_holder["box"].update(
                        label=f"🔧 Using `{tool_name}` …",
                        state="running",
                        expanded=True,
                    )

            # ---- AI text message ----
            elif data.get("type") == "text":
                content = str(data.get("content", ""))
                docubot_reply += content  # ✅ keep appending to one string
                chat_area.markdown("**DocuBot:** " + docubot_reply)

        # ---- Mark tool as complete ----
        if status_holder["box"] is not None:
            status_holder["box"].update(
                label=f"✅ Tool finished", state="complete", expanded=False
            )
