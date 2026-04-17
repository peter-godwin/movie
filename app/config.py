from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Moviz"
    env: str = "development"
    debug: bool = False

    database_url: str

    def get_allowed_origins(self):
        if self.env == "production":
            return ["https://moviz.app"]
        return [
            "http://localhost:3000",
            "http://localhost:5173",
        ]

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    jwt_issuer: str = "moviz-api"
    jwt_audience: str = "moviz-users"

    mail_username: str
    mail_password: str
    mail_from: str
    mail_from_name: str = "Moviz"
    mail_port: int = 587
    mail_server: str = "smtp.gmail.com"
    mail_starttls: bool = True
    mail_ssl_tls: bool = False

    tmdb_api_key: str = ""
    gemini_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()