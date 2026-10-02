from src.source_intelligence import load_source_registry
from src.source_registry_db import enabled, sync_registry

if __name__ == "__main__":
    if not enabled():
        raise SystemExit("Set SOURCE_INTELLIGENCE_DATABASE_URL or DATABASE_URL first.")
    sources = load_source_registry(from_database=False)
    print(f"Synced {sync_registry(sources)} configured sources into PostgreSQL.")
