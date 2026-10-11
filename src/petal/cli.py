"""Command line interface: `python -m petal build / serve`。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from . import __version__, convert, template
from .config import build_config


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} GB"


def _url(path: str) -> str:
    return quote(path)


def _meta_line(meta: dict, day: str) -> str:
    parts = [day, meta.get("aperture"), meta.get("focal")]
    if meta.get("iso"):
        parts.append(f"ISO {meta['iso']}")
    parts.append(meta.get("camera"))
    return " · ".join(p for p in parts if p)


def _collect_records(src: Path, tasks: list[dict], results: list[dict]) -> tuple[list[dict], dict]:
    records, failures = [], []
    in_bytes = 0
    for task, res in zip(tasks, results):
        in_bytes += task["src_bytes"]
        if not res["ok"]:
            failures.append(res)
            continue
        rel = Path(task["rel"])
        mtime = datetime.fromtimestamp(task["mtime"])
        meta = res["meta"]
        taken = meta.get("taken_at")
        month = taken[:7] if taken else mtime.strftime("%Y-%m")
        day = taken[:10] if taken else mtime.strftime("%Y-%m-%d")
        records.append(
            {
                "rel": task["rel"],
                "rel_dir": rel.parent.as_posix() if rel.parent != Path(".") else "",
                "alt": rel.stem,
                "month": month,
                "day": day,
                "sort_key": (day, task["rel"]),
                "width": res["width"],
                "height": res["height"],
                "variants": res["variants"],
                "lqip": res["lqip"],
                "lqip_bytes": res["lqip_bytes"],
                "meta": meta,
            }
        )
    return records, {"failures": failures, "in_bytes": in_bytes}


def _group(records: list[dict], group_by: str) -> list[dict]:
    if group_by == "folder":
        buckets: dict[str, list[dict]] = {}
        for r in records:
            buckets.setdefault(r["rel_dir"], []).append(r)
        keys = sorted(buckets, key=lambda k: (k != "", k))
        return [
            {"key": k, "label": k if k else "未分类", "photos": buckets[k]}
            for k in keys
        ]
    buckets = {}
    for r in records:
        buckets.setdefault(r["month"], []).append(r)
    return [
        {
            "key": m,
            "label": f"{m[:4]} 年 {int(m[5:7])} 月",
            "photos": buckets[m],
        }
        for m in sorted(buckets, reverse=True)
    ]


def build_command(args) -> int:
    t0 = time.time()
    src = Path(args.source).expanduser().resolve()
    if not src.is_dir():
        print(f"petal: 照片目录不存在：{src}", file=sys.stderr)
        return 2
    out = Path(args.output).expanduser().resolve()
    if out == src or src in out.parents:
        print("petal: 输出目录不能在照片目录里，会自己吃掉自己。", file=sys.stderr)
        return 2

    cfg = build_config(
        toml_path=args.config,
        overrides={
            "title": args.title,
            "group_by": args.group_by,
            "workers": args.workers,
            "recursive": False if args.no_recursive else None,
        },
    )

    files = [f for f in convert.source_files(src, cfg.recursive) if out not in f.parents]
    img_dir = out / "p"
    img_dir.mkdir(parents=True, exist_ok=True)

    tasks = [
        {
            "src": str(f),
            "rel": f.relative_to(src).as_posix(),
            "out_dir": str(img_dir),
            "stem": convert.make_stem(f.relative_to(src)),
            "mtime": f.stat().st_mtime,
            "src_bytes": f.stat().st_size,
        }
        for f in files
    ]
    results = convert.run_tasks(tasks, cfg.workers)
    records, extra = _collect_records(src, tasks, results)
    for res in extra["failures"]:
        print(f"petal: 跳过 {res['src']}（{res.get('error', '未知错误')}）", file=sys.stderr)

    groups = _group(records, cfg.group_by)
    for group in groups:
        group["photos"].sort(key=lambda r: r["sort_key"])
        group["count"] = len(group["photos"])

    flat = [r for group in groups for r in group["photos"]]

    # 前 3 张不懒加载，保首屏 LCP
    for index, r in enumerate(flat):
        full = max(r["variants"], key=lambda v: v["width"])
        std = template.standard_variant(r["variants"])
        r["index"] = index
        r["eager"] = index < 3
        r["loading"] = "eager" if index < 3 else "lazy"
        r["full_url"] = _url("p/" + full["file"])
        r["std_url"] = _url("p/" + std["file"])
        r["srcset"] = template.srcset_for(r["variants"])

    items = [
        {
            "f": r["full_url"],
            "w": r["width"],
            "h": r["height"],
            "a": r["alt"],
            "m": _meta_line(r["meta"], r["day"].replace("-", ".")),
        }
        for r in flat
    ]

    out_bytes = sum(v["bytes"] for r in flat for v in r["variants"]) + sum(r["lqip_bytes"] for r in flat)
    stats = {
        "count": len(flat),
        "in_bytes": extra["in_bytes"],
        "out_bytes": out_bytes,
        "human_in": human_size(extra["in_bytes"]),
        "human_out": human_size(out_bytes),
    }
    site = {
        "title": cfg.title,
        "tagline": cfg.tagline,
        "tagline_en": cfg.tagline_en,
        "footer_note": cfg.footer_note,
        "groups": groups,
        "items": items,
        "theme": "auto",
        "year": datetime.now().year,
        "stats": stats,
    }

    (out / "index.html").write_text(template.render_page(site), encoding="utf-8")

    manifest = {
        "petal": __version__,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "source": src.name,
        "config": {
            "title": cfg.title,
            "group_by": cfg.group_by,
            "workers": cfg.workers,
        },
        "stats": {**stats, "human_total_seconds": round(time.time() - t0, 1)},
        "photos": [
            {
                "src": r["rel"],
                "stem": convert.make_stem(Path(r["rel"])),
                "width": r["width"],
                "height": r["height"],
                "variants": r["variants"],
                "lqip_bytes": r["lqip_bytes"],
                "month": r["month"],
                "day": r["day"],
                "meta": r["meta"],
            }
            for r in flat
        ],
    }
    (out / "petal.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    saved = (1 - out_bytes / extra["in_bytes"]) * 100 if extra["in_bytes"] else 0.0
    elapsed = time.time() - t0
    workers_note = f"{cfg.workers} 进程" if cfg.workers > 1 else "单进程"
    print("落英 · Petal — 构建完成")
    print(
        f"  照片 {stats['count']} 张 · 源 {stats['human_in']} → WebP {stats['human_out']}"
        f"（体积降到 {100 - saved:.1f}%）"
    )
    if extra["failures"]:
        print(f"  跳过 {len(extra['failures'])} 张（见上方 stderr）")
    print(f"  输出 {out}（index.html + p/ + petal.json）")
    print(f"  用时 {elapsed:.1f}s（{workers_note}）")
    print(f"预览：python -m petal serve \"{out}\"")
    return 0


def make_server(directory: str, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    return ThreadingHTTPServer((host, port), handler)


def serve_command(args) -> int:
    out = Path(args.directory).expanduser().resolve()
    if not (out / "index.html").is_file():
        print(f"petal: {out} 里没有 index.html，先跑一次 build。", file=sys.stderr)
        return 2
    httpd = make_server(str(out), args.host, args.port)
    host, port = httpd.server_address[:2]
    print(f"落英 · Petal 预览 → http://{host}:{port}/（Ctrl+C 停止）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="petal", description="落英 · Petal — 把照片文件夹一键变成静态画廊（全 WebP）"
    )
    parser.add_argument("--version", action="version", version=f"落英 · Petal {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="扫描照片目录，生成静态画廊")
    b.add_argument("source", help="照片目录")
    b.add_argument("-o", "--output", required=True, help="输出目录")
    b.add_argument("--config", help="pyproject 式 TOML 配置（读 [tool.petal] 小节）")
    b.add_argument("--title", help="覆盖画廊标题")
    b.add_argument("--group-by", choices=("date", "folder"), help="分组方式：拍摄日期 / 文件夹")
    b.add_argument("--workers", type=int, help="并行进程数（默认 4，1 为串行）")
    b.add_argument("--no-recursive", action="store_true", help="只扫描第一层，不递归子目录")
    b.set_defaults(func=build_command)

    s = sub.add_parser("serve", help="本地预览生成的画廊")
    s.add_argument("directory", help="build 的输出目录")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=serve_command)

    args = parser.parse_args(argv)
    return args.func(args)
