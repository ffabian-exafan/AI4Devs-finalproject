"""Variables de entorno y ajustes de la aplicación."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://usuario:password@localhost:5432/gestor_obra"

    # Opcionales: solo si Seguridad autoriza proveedores cloud [NO-ENTRENAR]
    llm_api_key: str | None = None
    llm_api_base: str | None = None
    # Modelo multimodal para OCR vía visión (sin Tesseract en el host)
    llm_vision_model: str = "gpt-4o-mini"
    ocr_api_key: str | None = None
    ocr_api_base: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
