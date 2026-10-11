"""Image conversion pipeline: source photos -> WebP tiers + LQIP.

三档输出（缩略 480w q78 / 标准 1080w q82 / 全尺寸 1920w q85），等比缩放、
只缩不放；小于目标宽度的原图保持原尺寸。所有输出一律不带 EXIF/GPS：
Pillow 只有显式传入 exif 才会写进 WebP，petal 永远不传——只有 ICC 色彩
配置被保留，颜色不失真，位置信息不出门。
"""

from __future__ import annotations

import base64
import hashlib
import io
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from .exif import read_camera_meta

# (档位名, 目标宽, WebP 质量)，从小到大排列
TIERS: tuple[tuple[str, int, int], ...] = (
    ("thumb", 480, 78),
    ("standard", 1080, 82),
    ("full", 1920, 85),
)

LQIP_WIDTH = 24
LQIP_QUALITY = 35
LQIP_BLUR = 1.4

SOURCE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"})


def source_files(root: Path, recursive: bool = True) -> list[Path]:
    """列出待转换的照片，跳过隐藏文件，路径排序保证输出稳定。"""
    it = root.rglob("*") if recursive else root.iterdir()
    return sorted(
        p
        for p in it
        if p.is_file()
        and not p.name.startswith(".")
        and p.suffix.lower() in SOURCE_EXTENSIONS
    )


def make_stem(rel: Path) -> str:
    """相对路径 -> 12 位十六进制名，规避中文/空格/同名冲突，重建幂等。"""
    return hashlib.blake2b(rel.as_posix().encode("utf-8"), digest_size=6).hexdigest()


def _flatten(im: Image.Image) -> Image.Image:
    """按 EXIF 方向摆正，并归一到 RGB / RGBA。"""
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        return im.convert("RGBA")
    return im.convert("RGB")


def make_lqip(im: Image.Image) -> str:
    """24w 高斯模糊小图 -> base64 data URI，内联进 HTML 当占位。"""
    w = min(LQIP_WIDTH, im.width)
    small = im.resize((w, max(1, round(im.height * w / im.width))), Image.Resampling.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(LQIP_BLUR))
    buf = io.BytesIO()
    small.save(buf, "WEBP", quality=LQIP_QUALITY, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def convert_image(task: dict) -> dict:
    """转换一张照片。模块级函数，ProcessPoolExecutor 需要它能被 pickle。"""
    src = Path(task["src"])
    out_dir = Path(task["out_dir"])
    stem = task["stem"]
    result = {"src": task["rel"], "ok": False}

    try:
        with Image.open(src) as im:
            icc = im.info.get("icc_profile")
            meta = read_camera_meta(im)
            im = _flatten(im)
            width, height = im.size

            # 同一宽度只出一份文件：高像素原图的高档位会覆盖低档位的质量
            plans: dict[int, int] = {}
            for _name, max_w, quality in TIERS:
                plans[min(max_w, width)] = quality

            variants = []
            for w in sorted(plans):
                out = out_dir / f"{stem}-{w}.webp"
                v = im if w == width else im.resize(
                    (w, max(1, round(height * w / width))), Image.Resampling.LANCZOS
                )
                kwargs = {"quality": plans[w], "method": 4}
                if icc:
                    kwargs["icc_profile"] = icc
                v.save(out, "WEBP", **kwargs)
                variants.append(
                    {"file": out.name, "width": w, "height": v.height, "bytes": out.stat().st_size}
                )

            lqip = make_lqip(im)
    except Exception as exc:  # 单张失败不拖垮整个画廊，交由上层汇报
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result.update(
        ok=True,
        width=width,
        height=height,
        variants=variants,
        lqip=lqip,
        lqip_bytes=len(lqip),
        meta=meta,
    )
    return result


def run_tasks(tasks: list[dict], workers: int = 4) -> list[dict]:
    """并行转换；workers <= 1 或任务很少时退化为串行。"""
    if workers <= 1 or len(tasks) <= 1:
        return [convert_image(t) for t in tasks]
    with ProcessPoolExecutor(max_workers=min(workers, len(tasks))) as pool:
        return list(pool.map(convert_image, tasks, chunksize=1))
