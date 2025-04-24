import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    debug = False
    stub_text_generation = False  # os.environ.get("STUB_TEXT_LLM", None) is not None
    stub_video_generation = False
    stub_image_generation = False
    luma_api_key = os.environ["LUMAAI_API_KEY"]
    mistral_api_key = os.environ["MISTRAL_API_KEY"]
