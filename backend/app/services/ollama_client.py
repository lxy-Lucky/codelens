"""Ollama 客户端 — 用 OpenAI 兼容 /api/chat 流式接口对接 Qwen3 14B。"""
import json
from typing import AsyncIterator

import httpx

from app.config import settings


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.llm_model
        self.num_ctx = settings.llm_num_ctx

    async def chat_stream(
        self, messages: list[dict], temperature: float = 0.2
    ) -> AsyncIterator[str]:
        """流式返回纯文本增量(token)。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_ctx": self.num_ctx},
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break

    async def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        parts = [c async for c in self.chat_stream(messages, temperature)]
        return "".join(parts)

    async def warmup(self) -> bool:
        try:
            await self.chat([{"role": "user", "content": "ping"}])
            return True
        except Exception:
            return False


ollama = OllamaClient()
