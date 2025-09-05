from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

class LLMModel:
    def __init__(self,model_name="gemini-2.5-flash",temperature=0.5):
        if not model_name:
            raise ValueError("Model is not defined.")
        self.model_name= model_name
        self.gemini_model= ChatGoogleGenerativeAI(model=model_name,temperature=temperature)

    def get_model(self):
        return self.gemini_model
