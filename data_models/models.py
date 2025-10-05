import re
from pydantic import BaseModel, Field, field_validator, EmailStr

class DateTimeModel(BaseModel):
    datetime: str = Field(..., description="A date-time string in the format DD-MM-YYYY HH:MM",pattern=r'^\d{2}-\d{2}-\d{4} \d{2}:\d{2}$')

    @field_validator('datetime')
    def validate_datetime_format(cls, v):
        pattern = r'^\d{2}-\d{2}-\d{4} \d{2}:\d{2}$'
        if not re.match(pattern, v):
            raise ValueError('datetime must be in the format DD-MM-YYYY HH:MM')
        return v
    
class DateModel(BaseModel):
    date: str = Field(..., description="A date string in the format DD-MM-YYYY", pattern=r'^\d{2}-\d{2}-\d{4}$')

    @field_validator('date')
    def validate_date_format(cls, v):
        pattern = r'^\d{2}-\d{2}-\d{4}$'
        if not re.match(pattern, v):
            raise ValueError('date must be in the format DD-MM-YYYY')
        return v
    
class IdentificationNumberModel(BaseModel):
    id: int = Field(..., description="An identification number(7 or 8 digit long)")
    @field_validator('id')
    def validate_id_length(cls, v):
        if not re.match(r'^\d{7,8}$', str(v)): 
            raise ValueError("The ID number should be a 7 or 8-digit number")
        return v
    
class SignupRequest(BaseModel):
    fullname: str
    email: EmailStr
    password: str

class SignupResponse(BaseModel):
    patient_id: int
    fullname: str
    email: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"