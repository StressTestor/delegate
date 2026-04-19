import pytest
from delegate.providers import build_provider
from delegate.providers.kimi import KimiProvider
from delegate.providers.gemini import GeminiProvider
from delegate.providers.opencode import OpencodeProvider
from delegate.providers.openrouter import OpenrouterProvider


def test_registry_dispatches_by_name():
    assert isinstance(build_provider("kimi-code", {"cli": "kimi"}), KimiProvider)
    assert isinstance(build_provider("gemini-pro", {"cli": "gemini"}), GeminiProvider)
    assert isinstance(build_provider("gemini-flash", {"cli": "gemini"}), GeminiProvider)
    assert isinstance(build_provider("opencode-go", {"cli": "opencode", "allowlist": []}), OpencodeProvider)
    assert isinstance(build_provider("openrouter-free", {"api": "x", "api_key_env": "K", "allowlist_suffix": ":free"}), OpenrouterProvider)

def test_registry_unknown_name_raises():
    with pytest.raises(ValueError, match="unknown provider"):
        build_provider("ghost", {})
