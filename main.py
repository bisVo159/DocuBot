from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from agent import DoctorAppointmentAgent
from langchain_core.messages import ToolMessage, AIMessage, AIMessageChunk
from data_models.userQuery import UserQuery
from data_models.models import SignupRequest, SignupResponse, TokenResponse
from db.database import get_db, Base, engine
from db.models import Patient
from settings import settings
from utils.security import (
    generate_patient_id, create_access_token, hash_password, 
    verify_password, get_current_patient_id
)
from sqlalchemy.orm import Session
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

Base.metadata.create_all(bind=engine)

agent=DoctorAppointmentAgent()
app_graph=agent.workflow()

@app.post("/signup", response_model=SignupResponse)
def signup(user: SignupRequest, db: Session = Depends(get_db)):
    try:
        if db.query(Patient).filter(Patient.email == user.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        patient_id = generate_patient_id(db)
        password_hash = hash_password(user.password)
        new_user = Patient(
            patient_id=patient_id,
            fullname=user.fullname,
            email=user.email,
            password_hash=password_hash
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return SignupResponse(patient_id=new_user.patient_id, fullname=new_user.fullname, email=new_user.email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login", response_model=TokenResponse)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.email == form_data.username).first()
    if not patient or not verify_password(form_data.password, patient.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({
        "patient_id": patient.patient_id
    })

    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        # max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=True,
        samesite="Lax"
    )

    return TokenResponse(access_token=token)

@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.COOKIE_NAME)
    return {"message": "Logged out successfully"}

@app.post("/execute")
def execute_agent(user_input: UserQuery, patient_id: int = Depends(get_current_patient_id)):
    query_data = {
        'query': user_input.message
    }
    def event_generator() -> Generator[str, None, None]:
        try:
            seen_tool_ids = set()
            events = app_graph.stream(
                query_data, 
                stream_mode="messages",
                config={
                    "configurable": {
                    "thread_id": patient_id
                }
                })
            for msg_chunk, _ in events:
                try:
                    if isinstance(msg_chunk, AIMessage):
                        if hasattr(msg_chunk, 'tool_call_chunks') and msg_chunk.tool_call_chunks:
                            for chunk in msg_chunk.tool_call_chunks:
                                if chunk.get("name") and chunk.get("id") and chunk["id"] not in seen_tool_ids:
                                    seen_tool_ids.add(chunk["id"])
                                    yield json.dumps({
                                        "type": "tool", 
                                        "tool_name": f'{chunk["name"]} node'
                                    }) + "\n"
                        if msg_chunk.content:
                            yield json.dumps({
                                "type": "text", 
                                "content": str(msg_chunk.content)
                            }) + "\n"
                    elif isinstance(msg_chunk, ToolMessage): 
                        yield json.dumps({"type": "tool", "tool_name": f'{msg_chunk.name} tool'}) + "\n"
                except Exception as inner_err:
                    yield json.dumps({"type": "error", "message": str(inner_err)}) + "\n"

        except Exception as outer_err:
            yield json.dumps({"type": "fatal_error", "message": str(outer_err)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/json")