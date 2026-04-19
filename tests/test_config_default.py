import tomllib
from importlib.resources import files

def _load():
    raw = files("delegate").joinpath("config.default.toml").read_bytes()
    return tomllib.loads(raw.decode())

def test_defaults_section_present():
    cfg = _load()
    assert cfg["defaults"]["task_type"] == "code-gen"
    assert cfg["defaults"]["concurrency"] == 1


def test_all_four_providers_defined():
    cfg = _load()
    for p in ["kimi-code", "opencode-go", "gemini-pro", "gemini-flash", "openrouter-free"]:
        assert p in cfg["providers"], f"missing provider {p}"

def test_opencode_allowlist_is_exact():
    cfg = _load()
    assert set(cfg["providers"]["opencode-go"]["allowlist"]) == {"opencode-go/glm-5", "opencode-go/kimi-k2.5", "opencode-go/minimax-m2.5"}

def test_openrouter_requires_free_suffix():
    cfg = _load()
    assert cfg["providers"]["openrouter-free"]["allowlist_suffix"] == ":free"

def test_chains_present_with_expected_heads():
    cfg = _load()
    assert cfg["chains"]["code-gen"][0]["provider"] == "kimi-code"
    assert cfg["chains"]["bulk"][0]["provider"] == "openrouter-free"
    assert cfg["chains"]["research"][0]["provider"] == "gemini-pro"
