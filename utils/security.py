import bcrypt,uuid
from db.models import Patient
from authlib.jose import jwt, JoseError
from sqlalchemy.orm import Session
from settings import settings
from fastapi import HTTPException, Request
from datetime import datetime, timedelta, timezone

def generate_patient_id(db: Session) -> int:
    """Generate unique 7–8 digit patient_id"""
    while True:
        pid = int(str(uuid.uuid4().int)[-8:])
        if not db.query(Patient).filter(Patient.patient_id == pid).first():
            return pid
        
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(data: dict) -> str:
    header= {'alg': settings.ALGORITHM}
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = data.copy()
    payload.update({"exp": expire})
    return jwt.encode(header,payload, settings.SECRET_KEY)

def decode_access_token(token: str):
    try:
        return jwt.decode(token,key=settings.SECRET_KEY)
    except JoseError:
        raise HTTPException(status_code=401,detail="Could not validate credentials")


def get_current_patient_id(request: Request) -> int:
    token = request.cookies.get(settings.COOKIE_NAME) or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(token)
    patient_id = payload.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return patient_id