from supabase import create_client, Client
from app.config import settings

_client: Client | None = None
_initialized = False


def get_supabase() -> Client | None:
    """Return a Supabase client if configured, otherwise None.

    Lazily initializes on first call. Returns None when SUPABASE_URL
    or SUPABASE_KEY are empty, allowing the app to fall back to
    in-memory storage.
    """
    global _client, _initialized
    if not _initialized:
        _initialized = True
        if settings.supabase_url and settings.supabase_key:
            _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client
