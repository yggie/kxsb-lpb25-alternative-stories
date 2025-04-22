import random
from app.config import Config
from langchain_ollama.llms import OllamaLLM
from langchain_mistralai import ChatMistralAI

# llm = OllamaLLM(model="mistral-small", seed=random.seed())
# llm = OllamaLLM(model="gemma3:12b", seed=random.seed())
llm = ChatMistralAI(
    model_name="mistral-small-latest",
    temperature=0.3,
    random_seed=random.seed(),
    api_key=Config.mistral_api_key,
)

GAMEMASTER_BASE_CHARACTER = """
You are a passionate story writer, with a knack for writing stories based around
real world history and culture.
"""
