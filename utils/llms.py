from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

class LLMModel:
    def __init__(self,model_name="gemini-2.5-flash",temperature=0.5):
        if not model_name:
            raise ValueError("Model is not defined.")
        self.model_name= model_name
        self.gemini_model= ChatGoogleGenerativeAI(model=model_name,temperature=temperature)
        self.groq_model=ChatGroq(model="llama-3.1-8b-instant")

    def get_gemini_model(self):
        return self.gemini_model
    
    def get_groq_model(self):
        return self.groq_model
