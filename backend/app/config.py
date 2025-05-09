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

    db_username = os.environ["DB_USERNAME"]
    db_password = os.environ["DB_PASSWORD"]
    db_port = int(os.environ["DB_PORT"])
    db_host = os.environ["DB_HOST"]
    db_database = os.environ["DB_DATABASE"]
