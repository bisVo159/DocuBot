import streamlit as st
import json
import requests

def chat_with_backend_agent(fastapi_base_url: str, query: str,chat_area,status_holder,status_placeholder):
    headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}
    docubot_reply = ""
    
    with requests.post(
        f"{fastapi_base_url}/execute",
        json={"message": query},
        headers=headers,
        stream=True,
    ) as r:
        if r.status_code != 200:
                    st.error(f"❌ Server returned {r.status_code}: {r.json().get('detail', 'Authentication failed')}")
        else:
            for chunk in r.iter_lines():
                if not chunk:
                    continue
                try:
                    data = json.loads(chunk.decode("utf-8"))
                except Exception as e:
                    st.error(f"Failed to parse chunk: {chunk}")
                    continue

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
                elif data.get("type") == "text":
                    content = str(data.get("content", ""))
                    docubot_reply += content
                    chat_area.markdown(docubot_reply)

            if status_holder["box"] is not None:
                status_holder["box"].update(
                    label=f"✅ Tool finished", state="complete", expanded=False
                )
            st.session_state.messages.append({"role": "assistant", "content": docubot_reply})