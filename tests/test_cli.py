"""端到端测试：build / serve / 配置覆盖 / 并行。"""

import json
import threading
import urllib.request
from pathlib import Path

import pytest

from petal import cli


def _build(photo_dir: Path, out: Path, *extra) -> int:
    return cli.main(["build", str(photo_dir), "-o", str(out), *extra])


def test_build_end_to_end(photo_dir: Path, tmp_path: Path):
    out = tmp_path / "site"
    assert _build(photo_dir, out, "--workers", "2") == 0

    html = (out / "index.html").read_text(encoding="utf-8")
    assert "落英" in html

    # 输出目录只允许 webp / html / json —— 任何 jpg/png 都算泄漏
    produced = [p for p in out.rglob("*") if p.is_file()]
    assert produced, "输出目录不应为空"
    for p in produced:
        assert p.suffix in {".webp", ".html", ".json"}, f"混入了 {p.name}"

    # webp 数量与源图对应：1600→3 档，900→2 档(480,900)，300→1 档，800→2 档(480,800)，600→2 档(480,600)
    webps = [p for p in produced if p.suffix == ".webp"]
    assert len(webps) == 10

    manifest = json.loads((out / "petal.json").read_text(encoding="utf-8"))
    assert manifest["stats"]["count"] == 5
    assert any(
        p["meta"].get("camera") == "TestCam TestModel X" for p in manifest["photos"]
    ), "EXIF 相机参数应进入 manifest"
    assert "src" in manifest["photos"][0]


def test_build_groups_by_date_with_exif_and_mtime(photo_dir: Path, tmp_path: Path):
    out = tmp_path / "site"
    _build(photo_dir, out, "--workers", "1")
    html = (out / "index.html").read_text(encoding="utf-8")
    # EXIF 拍摄日期与 mtime 兜底各自成组（按月，倒序）
    assert "2025 年 4 月" in html
    from datetime import datetime

    now = datetime.now()
    assert f"{now.year} 年 {now.month} 月" in html


def test_build_groups_by_folder(photo_dir: Path, tmp_path: Path):
    out = tmp_path / "site"
    _build(photo_dir, out, "--workers", "1", "--group-by", "folder")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "海边" in html  # 子目录名作为分组
    assert "未分类" in html  # 根目录文件


def test_build_respects_title_override(photo_dir: Path, tmp_path: Path):
    out = tmp_path / "site"
    _build(photo_dir, out, "--title", "山与海")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "<title>山与海</title>" in html


def test_build_reads_toml_config(photo_dir: Path, tmp_path: Path):
    cfg = tmp_path / "petal.toml"
    cfg.write_text(
        '[tool.petal]\ntitle = "toml标题"\ntagline = "配置来的标语。"\nworkers = 1\n',
        encoding="utf-8",
    )
    out = tmp_path / "site"
    _build(photo_dir, out, "--config", str(cfg))
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "toml标题" in html
    assert "配置来的标语。" in html


def test_config_cli_override_wins(photo_dir: Path, tmp_path: Path):
    cfg = tmp_path / "petal.toml"
    cfg.write_text('[tool.petal]\ntitle = "toml标题"\n', encoding="utf-8")
    out = tmp_path / "site"
    _build(photo_dir, out, "--config", str(cfg), "--title", "命令行赢")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "命令行赢" in html
    assert "toml标题" not in html


def test_bad_config_fails_loudly(photo_dir: Path, tmp_path: Path):
    cfg = tmp_path / "bad.toml"
    cfg.write_text("[tool.petal]\ngroup_by = \"nonsense\"\n", encoding="utf-8")
    with pytest.raises(ValueError):
        cli.build_config(toml_path=cfg)


def test_output_inside_source_is_rejected(photo_dir: Path, tmp_path: Path):
    assert cli.main(["build", str(photo_dir), "-o", str(photo_dir)]) == 2


def test_serve_serves_gallery(photo_dir: Path, tmp_path: Path):
    out = tmp_path / "site"
    _build(photo_dir, out, "--workers", "1")
    httpd = cli.make_server(str(out), "127.0.0.1", 0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
            body = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "落英" in body
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/petal.json", timeout=5) as resp:
            assert resp.status == 200
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_serve_requires_build(photo_dir: Path, tmp_path: Path, capsys):
    assert cli.main(["serve", str(tmp_path / "empty"), "--port", "0"]) == 2
    assert "index.html" in capsys.readouterr().err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "Petal" in capsys.readouterr().out
