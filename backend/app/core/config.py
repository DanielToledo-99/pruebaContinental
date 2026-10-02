from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/document_ai"
    )
    llm_provider: Literal["openai", "ollama"] = "openai"
    embedding_provider: Literal["openai", "ollama"] | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_embedding_model: str = "bge-m3"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, ge=1, le=3072)
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    max_upload_mb: int = Field(default=10, ge=1, le=25)
    max_text_chars: int = Field(default=200_000, ge=800, le=1_000_000)
    max_pdf_pages: int = Field(default=200, ge=1, le=500)
    chunk_size: int = Field(default=800, ge=200, le=1000)
    chunk_overlap: int = Field(default=100, ge=0, le=150)
    retrieval_top_k: int = Field(default=4, ge=1, le=10)
    retrieval_min_score: float = Field(default=0.25, ge=-1, le=1)
    ai_timeout_seconds: float = Field(default=45, ge=1, le=120)

    @model_validator(mode="after")
    def validate_overlap(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self

    @property
    def embedding_backend(self) -> Literal["openai", "ollama"]:
        return self.embedding_provider or self.llm_provider

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
