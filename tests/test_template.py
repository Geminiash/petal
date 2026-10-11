"""模板测试：零外部请求、JS 预算、双主题、懒加载、转义与 URL 编码。"""

import re

from petal import template


def _photo(**over):
    base = {
        "index": 0,
        "eager": False,
        "loading": "lazy",
        "full_url": "p/ab12-1920.webp",
        "std_url": "p/ab12-1080.webp",
        "srcset": "p/ab12-480.webp 480w, p/ab12-1080.webp 1080w",
        "width": 1080,
        "height": 810,
        "alt": "示例照片",
        "lqip": "data:image/webp;base64,AAAA",
    }
    base.update(over)
    return base


def _site(**over):
    site = {
        "title": "落英",
        "tagline": "光落进镜头，就成了可以回看的日子。",
        "tagline_en": "Light lands, and stays.",
        "footer_note": "",
        "groups": [{"key": "2025-04", "label": "2025 年 4 月", "count": 1, "photos": [_photo()]}],
        "items": [{"f": "p/ab12-1920.webp", "w": 1920, "h": 1440, "a": "示例照片", "m": ""}],
        "theme": "auto",
        "year": 2026,
        "stats": {"count": 1, "human_in": "1.0 MB", "human_out": "0.1 MB"},
    }
    site.update(over)
    return site


def test_no_external_requests():
    """零 CDN：不允许任何 http(s) 资源引用、@import 或外链 url()。"""
    html = template.render_page(_site())
    for marker in ('src="http', 'href="http', "url(http", "@import", "//cdn"):
        assert marker not in html, f"发现外部引用：{marker}"


def test_js_budget_under_2kb():
    html = template.render_page(_site())
    scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
    assert len(scripts) == 2, "应恰好两段 JS：防闪主题 + 灯箱/切换"
    total = sum(len(s.encode("utf-8")) for s in scripts)
    assert total <= 2048, f"JS 超预算：{total} bytes"


def test_gallery_data_is_data_not_js():
    html = template.render_page(_site())
    assert '<script type="application/json" id="gallery-data">' in html


def test_dual_theme_palette_present():
    html = template.render_page(_site())
    assert "#faf7f2" in html  # 暖纸浅主题
    assert "#0f1512" in html  # 深林暗主题
    assert 'data-theme="d"' in html


def test_lazy_loading_and_decoding():
    html = template.render_page(_site())
    assert 'loading="lazy"' in html
    assert 'decoding="async"' in html


def test_eager_first_photo_gets_priority():
    p = _photo(eager=True, loading="eager")
    site = _site()
    site["groups"][0]["photos"] = [p]
    html = template.render_page(site)
    assert 'fetchpriority="high"' in html
    assert 'loading="eager"' in html


def test_lightbox_and_theme_toggle_markup():
    html = template.render_page(_site())
    assert 'id="lightbox"' in html
    assert 'role="dialog"' in html
    assert 'id="theme-toggle"' in html
    assert "backdrop-filter:blur" in html


def test_srcset_and_sizes_on_img():
    html = template.render_page(_site())
    assert 'srcset="p/ab12-480.webp 480w, p/ab12-1080.webp 1080w"' in html
    assert template.SIZES in html
    assert 'width="1080" height="810"' in html  # 固有宽高，防布局跳动


def test_lqip_inlined_as_background():
    html = template.render_page(_site())
    assert "background:url(data:image/webp;base64,AAAA) center/cover" in html


def test_html_escaping():
    site = _site(title='<b>标题&"引号</b>')
    html = template.render_page(site)
    assert "<b>标题" not in html
    assert "&lt;b&gt;标题&amp;" in html


def test_unicode_url_quoting():
    p = _photo(full_url="p/%E6%B5%B7-1920.webp", std_url="p/%E6%B5%B7-1080.webp")
    site = _site()
    site["groups"][0]["photos"] = [p]
    html = template.render_page(site)
    assert 'href="p/%E6%B5%B7-1920.webp"' in html


def test_group_chips_only_when_multiple():
    single = template.render_page(_site())
    assert 'class="chips"' not in single
    site = _site()
    site["groups"].append({"key": "g2", "label": "海边", "count": 0, "photos": []})
    multi = template.render_page(site)
    assert 'class="chips"' in multi
    assert "海边" in multi


def test_empty_state():
    html = template.render_page(_site(groups=[], items=[]))
    assert "这里还没有照片" in html
    assert "python -m petal build" in html


def test_standard_variant_prefers_1080():
    variants = [
        {"file": "a-480.webp", "width": 480},
        {"file": "a-1080.webp", "width": 1080},
        {"file": "a-1920.webp", "width": 1920},
    ]
    assert template.standard_variant(variants)["width"] == 1080
    small = [{"file": "a-600.webp", "width": 600}]
    assert template.standard_variant(small)["width"] == 600
