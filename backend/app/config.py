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
    content_fetch_concurrency: int = 5
    homepage_content_threshold: int = 10000    # chars; above this, LLM uses tool to search

    # BFS crawl
    bfs_max_level1_urls: int = 20

    # App
    frontend_url: str = "http://localhost:5173"
    mock_llm: bool = True                     # Skip real LLM calls, return fixture data

    profound_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
