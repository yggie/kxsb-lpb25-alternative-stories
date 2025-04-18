from app.config import Config
from lumaai import AsyncLumaAI

luma_client = AsyncLumaAI(
    auth_token=Config.luma_api_key,
)
