from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str
    debug: bool = False

    postgres_db: str = "portal"
    postgres_user: str = "portal"
    postgres_password: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    media_root: str = "/app/media"

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "pi-lab-portal/1.0"

    admin_username: str = "admin"
    admin_password: str = "changeme"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
