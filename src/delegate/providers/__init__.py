from __future__ import annotations

from typing import Any

from .base import Provider, ProviderResult, Outcome
from .kimi import KimiProvider
from .gemini import GeminiProvider
from .opencode import OpencodeProvider
from .openrouter import OpenrouterProvider

_REGISTRY: dict[str, type[Provider]] = {
    "kimi-code": KimiProvider,
    "gemini-pro": GeminiProvider,
    "gemini-flash": GeminiProvider,
    "opencode-go": OpencodeProvider,
    "openrouter-free": OpenrouterProvider,
}


def build_provider(name: str, cfg: dict[str, Any]) -> Provider:
    if name not in _REGISTRY:
        raise ValueError(f"unknown provider '{name}'")
    return _REGISTRY[name](name, cfg)


__all__ = ["Provider", "ProviderResult", "Outcome", "build_provider"]
