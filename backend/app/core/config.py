import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    llm_provider: str = Field(default="ollama", validation_alias="LLM_PROVIDER")
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", validation_alias="OPENAI_MODEL")
    
    anthropic_api_key: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-3-5-sonnet-20241022", validation_alias="CLAUDE_MODEL")
    
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5:7b", validation_alias="OLLAMA_MODEL")
    
    service_api_key: Optional[str] = Field(default=None, validation_alias="SERVICE_API_KEY")
    sqlite_db_path: str = Field(default="./data/processed/xcel_rag.db", validation_alias="SQLITE_DB_PATH")
    service_version: str = "2.0.0"
    
    embedding_model: str = Field(default="all-MiniLM-L6-v2", validation_alias="EMBEDDING_MODEL")
    
    chunk_size: int = Field(default=800, validation_alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, validation_alias="CHUNK_OVERLAP")
    top_k: int = Field(default=8, validation_alias="TOP_K")
    
    upload_dir: str = Field(default="./data/uploads", validation_alias="UPLOAD_DIR")
    chroma_dir: str = Field(default="./data/chroma", validation_alias="CHROMA_DIR")
    processed_dir: str = Field(default="./data/processed", validation_alias="PROCESSED_DIR")
    
    max_file_size_mb: int = Field(default=50, validation_alias="MAX_FILE_SIZE_MB")
    cors_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "*"]

    model_config = {
        "env_file": [".env", "backend/.env"],
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()

# Ensure directories exist
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
Path(settings.processed_dir).mkdir(parents=True, exist_ok=True)
