"""pytest 共享夹具：所有图片用 Pillow 现场生成，不提交任何二进制图。"""

import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from PIL.TiffImagePlugin import IFDRational

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from petal import convert  # noqa: E402


def paint(img: Image.Image) -> None:
    """画一点结构，让编码与 LQIP 不至于太平凡。"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    draw.ellipse((w * 0.55, h * 0.2, w * 0.9, h * 0.55), fill=(240, 200, 140))
    draw.polygon([(0, h), (w * 0.4, h * 0.45), (w, h)], fill=(90, 70, 60))


def make_image(
    path: Path,
    size: tuple[int, int] = (1600, 1200),
    color=(170, 120, 90),
    exif: bool = False,
    mode: str = "RGB",
) -> Path:
    img = Image.new(mode, size, color)
    if mode == "RGB":
        paint(img)
    if exif:
        ex = Image.Exif()
        ex[271] = "TestCam"
        ex[272] = "TestModel X"
        sub = ex.get_ifd(0x8769)
        sub[0x829D] = IFDRational(28, 10)  # FNumber f/2.8
        sub[0x8827] = 400  # ISO
        sub[0x920A] = IFDRational(50, 1)  # 50mm
        sub[0x9003] = "2025:04:12 10:30:00"  # DateTimeOriginal
        img.save(path, exif=ex.tobytes())
    else:
        img.save(path)
    return path


@pytest.fixture
def photo_dir(tmp_path: Path) -> Path:
    """带子目录、多种格式、含/不含 EXIF 的小照片树。"""
    root = tmp_path / "photos"
    (root / "海边").mkdir(parents=True)
    make_image(root / "IMG_0001.jpg", (1600, 1200), exif=True)
    make_image(root / "IMG_0002.jpg", (900, 1400))
    make_image(root / "IMG_0003.jpg", (300, 200))  # 小图：不允许放大
    make_image(root / "海边" / "wave.png", (800, 1000))
    make_image(root / "海边" / "mist.png", (600, 600), mode="RGBA")  # 透明通道
    (root / "notes.txt").write_text("不是图片")
    (root / ".hidden.jpg").write_bytes(b"fake")
    return root


@pytest.fixture
def converted() -> dict:
    """对一张 2400x1800 EXIF JPEG 跑一次单张转换，返回结果字典。"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        src = make_image(Path(td) / "a.jpg", (2400, 1800), exif=True)
        out_dir = Path(td) / "p"
        out_dir.mkdir()
        task = {
            "src": str(src),
            "rel": "a.jpg",
            "out_dir": str(out_dir),
            "stem": convert.make_stem(Path("a.jpg")),
        }
        result = convert.convert_image(task)
        result["_out_dir"] = str(out_dir)
        yield result
