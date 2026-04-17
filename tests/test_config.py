import pytest
from pathlib import Path
from delegate.config import load_config, ConfigError

def _write(p: Path, content: str) -> Path:
    p.write_text(content)
    return p

def test_load_defaults_only(tmp_path):
    # No user config → returns defaults as-is.
    cfg = load_config(user_config_path=tmp_path / "missing.toml")
    assert cfg["defaults"]["task_type"] == "code-gen"
    assert cfg["providers"]["kimi-code"]["default_model"] == "k2p5"

def test_scalar_deep_merge(tmp_path):
    user = _write(tmp_path / "c.toml", """
[providers.kimi-code]
rpm_cap = 99
""")
    cfg = load_config(user_config_path=user)
    assert cfg["providers"]["kimi-code"]["rpm_cap"] == 99
    # other keys survive
    assert cfg["providers"]["kimi-code"]["default_model"] == "k2p5"

def test_array_of_tables_replaces_entirely(tmp_path):
    user = _write(tmp_path / "c.toml", """
[[chains.code-gen]]
provider = "gemini-pro"
model = "gemini-2.5-pro"
""")
    cfg = load_config(user_config_path=user)
    assert len(cfg["chains"]["code-gen"]) == 1
    assert cfg["chains"]["code-gen"][0]["provider"] == "gemini-pro"
    # other chains unaffected
    assert cfg["chains"]["bulk"][0]["provider"] == "openrouter-free"

def test_invalid_toml_raises(tmp_path):
    user = _write(tmp_path / "c.toml", "this is [not valid toml")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(user_config_path=user)

def test_chain_references_unknown_provider_raises(tmp_path):
    user = _write(tmp_path / "c.toml", """
[[chains.code-gen]]
provider = "ghost-provider"
model = "x"
""")
    with pytest.raises(ConfigError, match="unknown provider"):
        load_config(user_config_path=user)

def test_chain_entry_model_violates_allowlist_raises(tmp_path):
    user = _write(tmp_path / "c.toml", """
[[chains.code-gen]]
provider = "opencode-go"
model = "not-on-allowlist"
""")
    with pytest.raises(ConfigError, match="allowlist"):
        load_config(user_config_path=user)

def test_openrouter_model_without_free_suffix_raises(tmp_path):
    user = _write(tmp_path / "c.toml", """
[[chains.code-gen]]
provider = "openrouter-free"
model = "openai/gpt-4"
""")
    with pytest.raises(ConfigError, match="allowlist_suffix"):
        load_config(user_config_path=user)
