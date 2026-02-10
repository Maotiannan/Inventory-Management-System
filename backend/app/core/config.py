import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "进销存管理系统"
    database_url: str = "postgresql+asyncpg://znas:znas_pass@postgres:5432/znas"
    jwt_secret_key: str = ""
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

    def model_post_init(self, __context) -> None:
        # BUG-13: 未配置 JWT 密钥时自动生成随机密钥并警告
        if not self.jwt_secret_key or self.jwt_secret_key == "change_me":
            self.jwt_secret_key = secrets.token_urlsafe(48)
            logger.warning(
                "JWT_SECRET_KEY 未配置或使用了默认弱密码，已自动生成随机密钥。"
                "重启后所有已签发的 Token 将失效。请在 .env 中设置 JWT_SECRET_KEY。"
            )


settings = Settings()
