from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from agent import DoctorAppointmentAgent
from langgraph.types import Command
from langchain_core.messages import ToolMessage, AIMessage
from data_models.userQuery import UserQuery
from typing import Generator
import json

app=FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
    expose_headers=["Content-Type"], 
)

agent=DoctorAppointmentAgent()
app_graph=agent.workflow()

@app.post("/execute")
def execute_agent(user_input: UserQuery):
    query_data = {
        'query': user_input.message,
        'patient_id':user_input.patient_id
    }
    def event_generator() -> Generator[str, None, None]:
        events = app_graph.stream(
            query_data, 
            stream_mode="messages",
            config={
                "configurable": {
                "thread_id": user_input.patient_id
            }
            })
        for msg_chunk, _ in events:
            if isinstance(msg_chunk, ToolMessage): 
                yield json.dumps({"type": "tool", "tool_name": msg_chunk.name}) + "\n"
            elif isinstance(msg_chunk, AIMessage):  
                yield json.dumps({"type": "text", "content": msg_chunk.content}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/json")