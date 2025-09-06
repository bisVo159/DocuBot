from pydantic import BaseModel, Field

class UserQuery(BaseModel):
    patient_id: int = Field(..., description="Patient's unique ID (must be 7 or 8 digits)")
    message: str = Field(..., description="The raw query or message provided by the user")