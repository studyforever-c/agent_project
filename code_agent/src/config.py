import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass


@dataclass
class Config:
    model: str = 'qwen-max'
    api_key: str = ''
    base_url: str|None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    max_context_tokens: int = 128_000
    provider: str = 'openai'

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()

        return cls(
            model = os.getenv('MODEL', 'qwen-max'),
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv('DEEPSEEK_API_KEY') or '',
            base_url = os.getenv('OPENAI_BASE_URL', None),
            max_tokens = int(os.getenv("MAX_TOKENS", '4096')),
            temperature = float(os.getenv('TEMPERATURE', '0.0')),
            max_context_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", '128_000')),
            provider = os.getenv('PROVIDER', 'openai')
        )