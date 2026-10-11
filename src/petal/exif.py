"""Read-only EXIF extraction for photo captions.

petal 只读取用于展示的拍摄参数（机型/光圈/焦距/ISO/曝光/拍摄时间），
GPS 标签一律不读；写出的 WebP 不携带任何 EXIF（见 convert.py）。
"""

from __future__ import annotations

import re

# TIFF/EXIF 标签号（Exif 2.x 标准字段）
TAG_MAKE = 271
TAG_MODEL = 272
TAG_DATETIME = 306
EXIF_IFD_POINTER = 0x8769
TAG_EXPOSURE = 0x829A
TAG_FNUMBER = 0x829D
TAG_ISO = 0x8827
TAG_DATETIME_ORIGINAL = 0x9003
TAG_FOCAL = 0x920A

# 允许出现在 meta 里的键，测试用它守住“不泄露其他信息”的边界
ALLOWED_KEYS = frozenset({"camera", "taken_at", "aperture", "focal", "exposure", "iso"})

_DT = re.compile(r"(\d{4})[:-](\d{2})[:-](\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?")


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _fmt_exposure(seconds) -> str | None:
    v = _as_float(seconds)
    if v is None or v <= 0:
        return None
    if v >= 1:
        return f"{v:g} s"
    return f"1/{round(1 / v)} s"


def _fmt_aperture(fnumber) -> str | None:
    v = _as_float(fnumber)
    if v is None or v <= 0:
        return None
    return "f/" + f"{v:.1f}".rstrip("0").rstrip(".")


def _fmt_focal(mm) -> str | None:
    v = _as_float(mm)
    if v is None or v <= 0:
        return None
    return f"{round(v)}mm"


def _parse_datetime(text) -> str | None:
    """'2025:04:12 10:30:00' / '2025-04-12T10:30' -> '2025-04-12T10:30'。"""
    if not isinstance(text, str):
        return None
    m = _DT.search(text)
    if not m:
        return None
    y, mo, d, h, mi = m.groups()[:5]
    return f"{y}-{mo}-{d}T{h}:{mi}"


def read_camera_meta(im) -> dict:
    """从 PIL Image 读取展示用拍摄参数，缺什么省什么，读不到返回 {}。"""
    try:
        exif = im.getexif()
    except Exception:
        return {}
    if not exif:
        return {}
    try:
        sub = exif.get_ifd(EXIF_IFD_POINTER)
    except Exception:
        sub = {}

    make = str(exif.get(TAG_MAKE) or "").strip()
    model = str(exif.get(TAG_MODEL) or "").strip()
    if model.startswith(make):
        make = ""
    camera = " ".join(p for p in (make, model) if p) or None
    taken = _parse_datetime(sub.get(TAG_DATETIME_ORIGINAL)) or _parse_datetime(exif.get(TAG_DATETIME))

    meta: dict = {}
    if camera:
        meta["camera"] = camera
    if taken:
        meta["taken_at"] = taken
    for key, raw, fmt in (
        ("aperture", sub.get(TAG_FNUMBER), _fmt_aperture),
        ("focal", sub.get(TAG_FOCAL), _fmt_focal),
        ("exposure", sub.get(TAG_EXPOSURE), _fmt_exposure),
    ):
        v = fmt(raw)
        if v:
            meta[key] = v
    iso = sub.get(TAG_ISO)
    try:
        iso = int(str(iso).split(",")[0])
    except (TypeError, ValueError):
        iso = 0
    if iso > 0:
        meta["iso"] = iso
    return meta
