from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 在这里定义所有的配置项
    # 需要覆盖database.py、storage.py、dependencies.py 中的散落配置

    model_config = SettingsConfigDict(
        env_file=".env",  # 支持 env 文件
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量大小写不敏感
    )

    database_url: str = "sqlite:///./data/registry.db"
    model_store_path: str = "./model_store"
    api_key: str = "dev-api-key"
    allow_dev_api_key: bool = True
    storage_backend: str = "local"  # local 或 s3

    app_env: str = "development"  # development, staging, production
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # s3 config
    s3_bucket_name: str = ""
    s3_prefix: str = "models/"


settings = Settings()
