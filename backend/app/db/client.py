from supabase import create_client, Client
from app.config import settings

# TODO: Initialize once Supabase project is created and env vars are set
# supabase: Client = create_client(settings.supabase_url, settings.supabase_key)


def get_supabase() -> Client:
    """
    TODO: Uncomment and use once Supabase is configured.
    For now, the app runs with in-memory job storage (see routers/generate.py).
    """
    # return supabase
    raise NotImplementedError("Supabase not configured yet — using in-memory storage")
