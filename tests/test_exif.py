"""EXIF 读取测试：参数提取正确、读不到不炸、绝不碰 GPS。"""

from PIL import Image

from conftest import make_image
from petal.exif import ALLOWED_KEYS, read_camera_meta


def test_reads_camera_params(photo_dir):
    with Image.open(photo_dir / "IMG_0001.jpg") as im:
        meta = read_camera_meta(im)
    assert meta["camera"] == "TestCam TestModel X"
    assert meta["aperture"] == "f/2.8"
    assert meta["focal"] == "50mm"
    assert meta["iso"] == 400
    assert meta["taken_at"].startswith("2025-04-12T10:30")


def test_image_without_exif_returns_empty(photo_dir):
    with Image.open(photo_dir / "海边" / "wave.png") as im:
        assert read_camera_meta(im) == {}


def test_meta_never_carries_gps(photo_dir):
    """无论原图带什么标签，meta 的键集合必须落在白名单里——GPS 永远不出现。"""
    with Image.open(photo_dir / "IMG_0001.jpg") as im:
        meta = read_camera_meta(im)
    assert set(meta) <= ALLOWED_KEYS
    assert not any(k.lower().startswith(("gps", "lat", "lon")) for k in meta)


def test_non_image_object_is_safe():
    """防御分支：随便一个对象进来也不该抛异常。"""
    assert read_camera_meta(object()) == {}
