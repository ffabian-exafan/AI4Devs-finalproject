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
    # Claude: basta LLM_API_KEY. LLM_API_BASE vacío usa https://api.anthropic.com
    llm_api_key: str | None = None
    llm_api_base: str | None = None
    # anthropic | openai. Vacío: Claude si la base está vacía o es api.anthropic.com
    llm_proveedor: str | None = None
    # Vacío: claude-sonnet-5 en Claude, gpt-4o-mini en un endpoint compatible
    llm_model: str | None = None
    # PDF → markdown. Vacío: claude-sonnet-5
    llm_modelo_transcripcion: str | None = None
    # Markdown → apartados. Vacío: claude-haiku-4-5
    llm_modelo_extraccion: str | None = None
    # Modelo multimodal para OCR vía visión (sin Tesseract en el host)
    llm_vision_model: str = "gpt-4o-mini"
    ocr_api_key: str | None = None
    ocr_api_base: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
