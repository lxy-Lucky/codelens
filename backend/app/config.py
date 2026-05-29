from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Ollama / LLM
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen3.5:9b"
    llm_num_ctx: int = 24576

    # Embedding / reranker
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    embedding_device: str = "cuda"
    # reranker 默认放 CPU:搜索时才用、批量小,放 CPU 省显存、避免与 LLM 抢 16GB
    reranker_device: str = "cpu"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "codelens123"

    # Local data
    data_dir: Path = Path("./data")

    # Retrieval
    retrieval_top_k: int = 50
    rerank_top_n: int = 8

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "codelens.db"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s


settings = get_settings()
