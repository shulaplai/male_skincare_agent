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

    # LLM: cloud is opt-in (keys read from env). DeepSeek is the default
    # provider: reachable directly from HK and vision-capable since 2026-08
    # (`deepseek-v4-flash-vision-exp`). Anthropic/OpenAI remain configurable
    # for non-HK deployments. Note: legacy model names like `deepseek-chat`
    # were discontinued 2026-07-24 — always use explicit V4 model ids.
    llm_provider: str = "deepseek"  # deepseek | anthropic | openai
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    openai_api_key: str = ""

    # DeepSeek V4 model tiering: photo analysis uses the vision model, other
    # tasks (advice, memory) use the plain text model.
    deepseek_text_model: str = "deepseek-v4-flash"
    deepseek_vision_model: str = "deepseek-v4-flash-vision-exp"

    # Model names for the other providers (only used when a key is set).
    anthropic_model: str = "claude-sonnet-5"
    openai_model: str = "gpt-5"

    # Privacy consent: per-conversation cloud-analysis default for NEW
    # conversations. Product default is off (photos never leave the machine
    # unless the user opts in); a self-hoster who has consented can set
    # SKINCOACH_CLOUD_ANALYSIS_DEFAULT=true so every new conversation starts
    # with cloud analysis enabled. The per-conversation toggle overrides this.
    cloud_analysis_default: bool = False


settings = Settings()
