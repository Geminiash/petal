"""Configuration: pyproject 式 TOML（[tool.petal]）+ 命令行覆盖。"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields


@dataclass
class Config:
    title: str = "落英"
    tagline: str = "光落进镜头，就成了可以回看的日子。"
    tagline_en: str = "Light lands, and stays."
    footer_note: str = ""
    group_by: str = "date"  # date | folder
    theme: str = "auto"  # light | dark | auto
    workers: int = 4
    recursive: bool = True


def _coerce(cfg: Config, key: str, value) -> None:
    field = {f.name: f for f in fields(Config)}.get(key)
    if field is None:
        raise ValueError(f"未知配置项：{key}（允许：{', '.join(f.name for f in fields(Config))}）")
    current = getattr(cfg, key)
    try:
        if isinstance(current, bool):
            value = bool(value) if not isinstance(value, str) else value.lower() not in ("false", "0", "no")
        elif isinstance(current, int):
            value = int(value)
        else:
            value = str(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"配置项 {key} 的值 {value!r} 类型不对：{exc}") from exc
    setattr(cfg, key, value)


def _validate(cfg: Config) -> None:
    if cfg.group_by not in ("date", "folder"):
        raise ValueError(f"group_by 只能是 date 或 folder，现在是 {cfg.group_by!r}")
    if cfg.theme not in ("light", "dark", "auto"):
        raise ValueError(f"theme 只能是 light / dark / auto，现在是 {cfg.theme!r}")
    if not 0 <= cfg.workers <= 32:
        raise ValueError(f"workers 取值 0-32，现在是 {cfg.workers}")


def load_toml(path) -> dict:
    """读取 TOML，返回 [tool.petal] 小节；文件不存在或没有该小节都视为空。"""
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    section = data.get("tool", {}).get("petal", {})
    if not isinstance(section, dict):
        raise ValueError("[tool.petal] 必须是表（table）")
    return section


def build_config(toml_path=None, overrides: dict | None = None) -> Config:
    cfg = Config()
    if toml_path is not None:
        for key, value in load_toml(toml_path).items():
            _coerce(cfg, key, value)
    for key, value in (overrides or {}).items():
        if value is not None:
            _coerce(cfg, key, value)
    _validate(cfg)
    return cfg
