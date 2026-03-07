from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    llm_provider: str = "anthropic"            # "anthropic" | "openai"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"  # or "gpt-4o-mini"

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Crawl
    max_pages: int = 50
    crawl_timeout: int = 30                    # seconds per page

    # App
    frontend_url: str = "http://localhost:5173"
    mock_llm: bool = True                     # Skip real LLM calls, return fixture data

    profound_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
