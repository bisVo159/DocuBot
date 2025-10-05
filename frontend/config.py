import os
from dotenv import load_dotenv

load_dotenv()

def load_frontend_config():

    return {
        "FASTAPI_BASE_URL": os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
    }

FRONTEND_CONFIG = load_frontend_config()