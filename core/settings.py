from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str | None = os.getenv("DATABASE_URL")
    llama_server_url: str = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:9931")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "180"))


settings = Settings()
