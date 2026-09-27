from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _list(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(v.strip() for v in os.getenv(name, default).split(",") if v.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str = ""
    redis_url: str = ""
    cors_origins: tuple[str, ...] = ()
    write_token: str = ""
    default_page_size: int = 20
    max_page_size: int = 100
    cache_ttl_seconds: int = 300
    rate_limit_default: str = "600 per minute"
    rate_limit_write: str = "30 per minute"
    rate_limit_enabled: bool = True
    ratelimit_storage_uri: str = "memory://"
    trusted_proxies: int = 1
    db_pool_min: int = 1
    db_pool_max: int = 10
    db_statement_timeout_ms: int = 5000
    log_level: str = "INFO"
    environment: str = "development"
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Settings:
        redis_url = os.getenv("REDIS_URL", "")
        return cls(
            database_url=os.getenv("DATABASE_URL", ""),
            redis_url=redis_url,
            cors_origins=_list("CORS_ORIGINS"),
            write_token=os.getenv("API_WRITE_TOKEN", ""),
            default_page_size=_int("DEFAULT_PAGE_SIZE", 20),
            max_page_size=_int("MAX_PAGE_SIZE", 100),
            cache_ttl_seconds=_int("CACHE_TTL_SECONDS", 300),
            rate_limit_default=os.getenv("RATE_LIMIT_DEFAULT", "600 per minute"),
            rate_limit_write=os.getenv("RATE_LIMIT_WRITE", "30 per minute"),
            rate_limit_enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            ratelimit_storage_uri=os.getenv("RATELIMIT_STORAGE_URI", redis_url or "memory://"),
            trusted_proxies=_int("TRUSTED_PROXIES", 1),
            db_pool_min=_int("DB_POOL_MIN", 1),
            db_pool_max=_int("DB_POOL_MAX", 10),
            db_statement_timeout_ms=_int("DB_STATEMENT_TIMEOUT_MS", 5000),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            environment=os.getenv("ENVIRONMENT", "development"),
        )
