"""Application settings loaded from environment / .env file.

Every secret and environment-specific value lives here so the rest of the
codebase never reads os.environ directly. This is part of the "production
skeleton" story: config is typed and validated at startup.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SKINCOACH_",
        extra="ignore",
    )

    app_name: str = "SkinCoach"
    # Local-first: everything lives under a single data dir by default.
    data_dir: str = "./data"
    database_url: str = "sqlite:///./data/skincoach.db"

    # LLM: cloud is opt-in; local mode uses Ollama.
    llm_provider: str = "anthropic"  # anthropic | deepseek | openai | ollama
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Strong model for deep one-off tasks (analysis, advice), fast for high-frequency.
    strong_model: str = "claude-3-5-sonnet-latest"
    fast_model: str = "claude-3-5-haiku-latest"

    # Embeddings (local by default; bilingual corpus).
    embedding_model: str = "BAAI/bge-m3"


settings = Settings()
