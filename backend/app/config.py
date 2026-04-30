from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    ai_api_key: str = ""
    ai_base_url: str = "https://chat-api.tamu.ai/api"
    ai_model: str = "protected.gpt-4o"

    # Google OAuth app credentials (for Calendar/Gmail/Tasks OAuth)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8000/api/gcal/callback"

    # Spotify OAuth app credentials
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8000/api/spotify/callback"

    # Fallbacks for integrations now configured through the UI
    # (used only if not set in the integrations DB)
    google_calendar_ics_url: str = ""
    canvas_ics_url: str = ""
    weather_api_key: str = ""
    weather_city: str = "College Station"
    fatsecret_client_id: str = ""
    fatsecret_client_secret: str = ""
    ntfy_topic: str = ""

    daily_token_budget: int = 0

    database_url: str = "sqlite+aiosqlite:///./sonus.db"

    user_name: str = "User"

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
