import anthropic
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str = ""
    class Config:
        env_file = ".env"

client = anthropic.AsyncAnthropic(api_key=Settings().anthropic_api_key)
MODEL = "claude-sonnet-4-6"
