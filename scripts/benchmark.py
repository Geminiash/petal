"""基准测试：生成 20 张 ~4MB 的合成 JPEG 样例，跑完整 WebP 管线，输出体积对比表。

用法（在仓库根目录）：
    PYTHONPATH=src python scripts/benchmark.py [-n 20] [--keep]

默认在 tests/tmp 下生成样例并清理构建产物（--keep 保留）。
"""

from __future__ import annotations

import argparse
import io
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from petal import convert, template  # noqa: E402

TARGET_BYTES = 4_000_000
SAMPLE_SIZE = (4000, 2667)


def synth_photo(path: Path, seed: int, size=SAMPLE_SIZE) -> int:
    """生成一张类照片合成图（渐变天空 + 山脊 + 随机形体 + 颗粒），JPEG 落到 ~4MB。"""
    import random

    rnd = random.Random(seed)
    random.seed(seed)  # effect_noise 用全局 random，保证可复现

    palette = [(rnd.randint(40, 220), rnd.randint(60, 220), rnd.randint(80, 240)) for _ in range(4)]
    grad = Image.new("RGB", (4, 4))
    grad.putdata(palette * 4)
    img = grad.resize(size, Image.Resampling.BICUBIC)

    draw = ImageDraw.Draw(img)
    w, h = size
    horizon = int(h * 0.62)
    draw.rectangle((0, horizon, w, h), fill=(rnd.randint(40, 80), rnd.randint(50, 90), rnd.randint(30, 60)))
    ridge = [(x, horizon - int(abs((x * 7919 + seed * 131) % 900) * (0.35 + rnd.random() * 0.3)))
             for x in range(0, w + 400, 300)]
    draw.polygon(ridge + [(w, h), (0, h)], fill=(25 + rnd.randint(0, 30), 35 + rnd.randint(0, 30), 25 + rnd.randint(0, 20)))
    for _ in range(60):  # 随机形体补充细节量，让样例接近真实照片的压缩特征
        x, y = rnd.randint(0, w), rnd.randint(0, horizon)
        r = rnd.randint(30, 260)
        draw.ellipse((x - r, y - r, x + r, y + r),
                     fill=(rnd.randint(120, 240), rnd.randint(120, 240), rnd.randint(100, 220)))
    img = img.filter(ImageFilter.GaussianBlur(0.5))

    noise = Image.effect_noise(size, 34).convert("L")
    img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.34)

    q = 96
    buf = io.BytesIO()
    while q >= 45:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=q)
        if buf.tell() <= 4_200_000:
            break
        q -= 2
    path.write_bytes(buf.getvalue())
    return buf.tell()


def main() -> int:
    parser = argparse.ArgumentParser(description="petal WebP 转换基准")
    parser.add_argument("-n", type=int, default=20, help="样例张数（默认 20）")
    parser.add_argument("--keep", action="store_true", help="保留生成的样例与构建产物")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    src_dir = root / "tests" / "tmp" / "bench-src"
    out_dir = root / "tests" / "tmp" / "bench-site"
    src_dir.mkdir(parents=True, exist_ok=True)

    print(f"生成 {args.n} 张 {SAMPLE_SIZE[0]}x{SAMPLE_SIZE[1]} 合成样例（目标 ~4MB/张）…", flush=True)
    for i in range(args.n):
        synth_photo(src_dir / f"sample_{i:02d}.jpg", seed=1000 + i)
        print(f"  [{i + 1}/{args.n}] sample_{i:02d}.jpg", flush=True)

    files = convert.source_files(src_dir)
    tasks = [
        {
            "src": str(f),
            "rel": f.name,
            "out_dir": str(out_dir / "p"),
            "stem": convert.make_stem(Path(f.name)),
            "mtime": f.stat().st_mtime,
            "src_bytes": f.stat().st_size,
        }
        for f in files
    ]
    (out_dir / "p").mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    results = convert.run_tasks(tasks, workers=4)
    elapsed = time.time() - t0

    rows, src_total, out_total = [], 0, 0
    for task, res in zip(tasks, results):
        if not res["ok"]:
            print(f"跳过 {task['rel']}: {res.get('error')}", file=sys.stderr)
            continue
        by_w = {v["width"]: v["bytes"] for v in res["variants"]}
        total = sum(by_w.values()) + res["lqip_bytes"]
        src_total += task["src_bytes"]
        out_total += total
        rows.append((task["rel"], task["src_bytes"], by_w, res["lqip_bytes"], total))

    lines = [
        "| # | 样例 | 源 JPEG | WebP 480w | WebP 1080w | WebP 全尺寸 | LQIP | WebP 合计 | 压缩到 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, (name, src_b, by_w, lqip_b, total) in enumerate(rows, 1):
        full_w = max(by_w)
        lines.append(
            f"| {i} | {name} | {src_b / 1048576:.2f} MB | {by_w.get(480, 0) / 1024:.0f} KB | "
            f"{by_w.get(1080, 0) / 1024:.0f} KB | {by_w[full_w] / 1024:.0f} KB ({full_w}w) | "
            f"{lqip_b / 1024:.1f} KB | {total / 1048576:.2f} MB | {total / src_b * 100:.1f}% |"
        )
    lines.append(
        f"| — | **总计（{len(rows)} 张）** | **{src_total / 1048576:.1f} MB** |  |  |  |  | "
        f"**{out_total / 1048576:.1f} MB** | **{out_total / src_total * 100:.1f}%** |"
    )
    report = "\n".join(lines)
    print("\n" + report)
    print(f"\n转换用时 {elapsed:.1f}s（4 进程，{len(rows)} 张）")
    print(f"页面骨架：CSS {len(template.CSS.encode()) / 1024:.2f} KB + "
          f"JS {(len(template.THEME_JS) + len(template.APP_JS)) / 1024:.2f} KB（内联，无外链）")

    (root / "tests" / "tmp" / "bench-report.md").write_text(report + "\n", encoding="utf-8")
    if not args.keep:
        shutil.rmtree(src_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
