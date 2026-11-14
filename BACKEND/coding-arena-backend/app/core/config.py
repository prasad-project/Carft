from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./arena.db"  # prod: postgresql+asyncpg://user:pw@host/db
    redis_url: str = "fakeredis://"  # prod: redis://host:6379/0
    jwt_secret: str = "change-me"
    jwt_ttl_minutes: int = 720
    enable_dev_login: bool = True  # prod: false, plug a real IdP into core/security.py
    admin_usernames: str = "admin"
    room_ttl_minutes: int = 30
    start_countdown_seconds: float = 3.0
    reconnect_window_seconds: int = 20
    min_pool_size: int = 30
    ws_rate_limit_per_sec: int = 20


settings = Settings()

# Admin-overridable via PUT /api/v1/admin/rules (stored in Redis hash arena:rules)
DEFAULT_RULES = {
    "base_points": 10,
    "max_speed_bonus": 5,
    "reward_win": 50,
    "reward_loss": 10,
    "reward_draw": 25,
    "reveal_pause_ms": 300,
    "allowed_durations": [60, 120, 180, 300],
    "min_questions": 5,
    "max_questions": 50,
}
