import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from config import GROQ_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE

load_dotenv()

# Get GROQ_API_KEY from environment
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables or .env file.")

# Reusable ChatGroq LLM instance
llm = ChatGroq(
    model=GROQ_MODEL,
    groq_api_key=api_key,
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS,
    model_kwargs={"top_p": 1.0}
)
