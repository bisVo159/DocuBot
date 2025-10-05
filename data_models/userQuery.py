from pydantic import BaseModel, Field

class UserQuery(BaseModel):
    message: str = Field(..., description="The raw query or message provided by the user")