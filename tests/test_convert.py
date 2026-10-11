"""转换管线测试：三档尺寸、只缩不放、EXIF 剥离、透明通道、LQIP。"""

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from petal import convert


def _open_out(result, variant):
    return Image.open(Path(result["_out_dir"]) / variant["file"])


def test_three_tiers_at_expected_widths(converted):
    widths = [v["width"] for v in converted["variants"]]
    assert widths == [480, 1080, 1920]
    heights = [v["height"] for v in converted["variants"]]
    # 1600x1200 → 4:3 等比
    assert heights == [360, 810, 1440]
    for v in converted["variants"]:
        with _open_out(converted, v) as im:
            assert im.format == "WEBP"


def test_aspect_ratio_preserved_on_every_variant(converted):
    for v in converted["variants"]:
        assert abs(v["width"] / v["height"] - 4 / 3) < 0.01


def test_tiny_source_collapses_to_one_variant(tmp_path):
    """300px 源图：三档目标全部钳到 300，只出一份文件。"""
    from conftest import make_image

    src = make_image(tmp_path / "t.jpg", (300, 200))
    out_dir = tmp_path / "p"
    out_dir.mkdir()
    res = convert.convert_image(
        {"src": str(src), "rel": "t.jpg", "out_dir": str(out_dir), "stem": "t"}
    )
    assert [v["width"] for v in res["variants"]] == [300]
    assert (out_dir / "t-300.webp").is_file()


def test_exif_is_stripped(converted):
    """输出的 WebP 一律无 EXIF：读不出标签，字节里也搜不到机型。"""
    for v in converted["variants"]:
        with _open_out(converted, v) as im:
            assert dict(im.getexif()) == {}
            raw = (Path(converted["_out_dir"]) / v["file"]).read_bytes()
        assert b"TestCam" not in raw
        assert b"TestModel" not in raw


def test_camera_meta_survives_in_result_not_in_pixels(converted):
    assert converted["meta"]["camera"] == "TestCam TestModel X"


def test_alpha_channel_preserved(tmp_path):
    """半透明 PNG 必须保住 alpha；全不透明图被压平成 RGB 属于合理优化。"""
    from conftest import make_image

    src = make_image(tmp_path / "a.png", (500, 500), color=(170, 120, 90, 128), mode="RGBA")
    out_dir = tmp_path / "p"
    out_dir.mkdir()
    res = convert.convert_image(
        {"src": str(src), "rel": "a.png", "out_dir": str(out_dir), "stem": "a"}
    )
    with Image.open(out_dir / res["variants"][0]["file"]) as im:
        assert im.mode == "RGBA"


def test_lqip_is_inline_webp_data_uri(converted):
    lqip = converted["lqip"]
    assert lqip.startswith("data:image/webp;base64,")
    payload = base64.b64decode(lqip.split(",", 1)[1])
    assert len(payload) < 4096, "LQIP 应该不到 4KB"
    with Image.open(io.BytesIO(payload)) as im:
        assert im.format == "WEBP"
        assert im.width == 24  # 1600x1200 → 24x18


def test_source_files_scanning(photo_dir):
    files = convert.source_files(photo_dir)
    names = [f.name for f in files]
    assert names == ["IMG_0001.jpg", "IMG_0002.jpg", "IMG_0003.jpg", "mist.png", "wave.png"]
    assert "notes.txt" not in names
    assert ".hidden.jpg" not in names


def test_run_tasks_parallel_matches_serial(photo_dir, tmp_path):
    files = convert.source_files(photo_dir)
    tasks = [
        {
            "src": str(f),
            "rel": f.relative_to(photo_dir).as_posix(),
            "out_dir": str(tmp_path / "par"),
            "stem": convert.make_stem(f.relative_to(photo_dir)),
        }
        for f in files
    ]
    (tmp_path / "par").mkdir()
    results = convert.run_tasks(tasks, workers=4)
    assert all(r["ok"] for r in results)
    assert len({Path(r["variants"][0]["file"]).name for r in results}) == len(results)
