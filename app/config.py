from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All .env values in one validated place.

    Fields without a default are required: if one is missing from .env the app
    fails loudly at startup instead of running with a silently wrong value.
    """

    db_host: str = "localhost"
    db_name: str = "booking"
    db_user: str = "postgres"
    db_password: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    institute_email_domain: str = "iitdh.ac.in"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()