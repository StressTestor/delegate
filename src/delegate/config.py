from __future__ import annotations

import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    pass


def _load_default() -> dict[str, Any]:
    raw = files("delegate").joinpath("config.default.toml").read_bytes()
    return tomllib.loads(raw.decode())


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            # array-of-tables: replace entirely
            out[k] = list(v)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _validate(cfg: dict[str, Any]) -> None:
    providers = cfg.get("providers", {})
    for chain_name, entries in cfg.get("chains", {}).items():
        for i, entry in enumerate(entries):
            pname = entry.get("provider")
            if pname not in providers:
                raise ConfigError(
                    f"chain {chain_name}[{i}] references unknown provider '{pname}'"
                )
            pcfg = providers[pname]
            model = entry.get("model", "")
            if "allowlist" in pcfg:
                if model not in pcfg["allowlist"]:
                    raise ConfigError(
                        f"chain {chain_name}[{i}] model '{model}' not in "
                        f"provider '{pname}' allowlist {pcfg['allowlist']}"
                    )
            if "allowlist_suffix" in pcfg:
                if not model.endswith(pcfg["allowlist_suffix"]):
                    raise ConfigError(
                        f"chain {chain_name}[{i}] model '{model}' must end "
                        f"with allowlist_suffix '{pcfg['allowlist_suffix']}' "
                        f"for provider '{pname}'"
                    )


def load_config(user_config_path: Path | None = None) -> dict[str, Any]:
    cfg = _load_default()
    if user_config_path and user_config_path.exists():
        try:
            user = tomllib.loads(user_config_path.read_text())
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"invalid TOML in {user_config_path}: {e}") from e
        cfg = _deep_merge(cfg, user)
    _validate(cfg)
    return cfg
