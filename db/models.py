from sqlalchemy import Column, Integer, String
from db.database import Base

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)  
    patient_id = Column(Integer, unique=True, index=True) 
    fullname = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)