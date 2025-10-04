from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config=SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    GOOGLE_API_KEY : str
    GROQ_API_KEY : str
    SQLALCHEMY_DATABASE_URL:str = "sqlite:///./patients.db"

    SECRET_KEY : str
    ALGORITHM : str
    ACCESS_TOKEN_EXPIRE_MINUTES : int = 60*24
    COOKIE_NAME : str

settings = Settings()