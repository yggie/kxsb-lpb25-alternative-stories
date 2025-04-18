import random
from app.config import Config
from langchain_ollama.llms import OllamaLLM
from langchain_mistralai import ChatMistralAI

# llm = OllamaLLM(model="mistral-small", seed=random.seed())
# llm = OllamaLLM(model="gemma3:12b", seed=random.seed())
llm = ChatMistralAI(
    model_name="mistral-small-latest",
    temperature=0.8,
    random_seed=random.seed(),
    api_key=Config.mistral_api_key,
)

GAMEMASTER_BASE_CHARACTER = """
You are the game master and writer for an immersive storytelling theatre. Your
job is to write immersive theatre narratives with rich character dialogue, that
are deep in meaning, have plenty of references to popular culture and with
unique relatable characters.

These stories are intended to be used in an immersive single player experience.
For the story, the player will always be an outsider to the world of the story.
They will encounter the world through the game, and will be referred to by all
characters as “Traveller” in the dialogue.
"""
