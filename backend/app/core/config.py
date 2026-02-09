from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "进销存管理系统"
    database_url: str = "postgresql+asyncpg://znas:znas_pass@postgres:5432/znas"
    jwt_secret_key: str = "change_me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    admin_username: str = "admin"
    admin_password: str = "change_me_strong_password"
    images_dir: str = "/data/images"
    enable_web_ops: bool = True
    project_root: str = "/data/ops/repo"
    ops_dir: str = "/data/ops"
    repo_url: str = ""
    update_branch: str = "main"


settings = Settings()
