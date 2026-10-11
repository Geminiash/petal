"""Static gallery page renderer.

单个 index.html 内联全部 CSS/JS：零 CDN、零框架、零外部请求。
JS 分两段——防闪主题脚本（head，先行执行）+ 灯箱/主题切换脚本（body 末尾），
合计约 1.2KB，上限 2KB（tests 守住）。画廊数据放在
<script type="application/json"> 里，属数据不属代码。
"""

from __future__ import annotations

import html
import json
from urllib.parse import quote

SIZES = "(max-width:559px) 94vw,(max-width:819px) 46vw,(max-width:1139px) 30vw,23vw"

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Cpath d='M16 3c5.5 6.3 8.5 10.6 8.5 15a8.5 8.5 0 1 1-17 0C7.5 13.6 10.5 9.3 16 3z' "
    "fill='%23b0563f'/%3E%3C/svg%3E"
)

# 落英 · 双主题：暖纸（#faf7f2 系）/ 深林（#0f1512 系）
CSS = """
:root{--bg:#faf7f2;--panel:#fffdf8;--text:#2b251d;--muted:#8d8071;--accent:#b0563f;
--line:#eadfcd;--chip:#f3ece0;
--shadow-sm:0 1px 2px rgba(74,52,28,.06);
--shadow-lg:0 2px 4px rgba(74,52,28,.08),0 18px 40px -18px rgba(74,52,28,.28);
--radius:16px;--serif:Georgia,"Times New Roman","Songti SC","STSong","Noto Serif SC",serif;
--sans:system-ui,-apple-system,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
:root[data-theme="d"]{--bg:#0f1512;--panel:#161d18;--text:#e8e4d8;--muted:#7d8a7f;--accent:#8bb598;
--line:#20291f;--chip:#18211b;
--shadow-sm:0 1px 2px rgba(0,0,0,.35);
--shadow-lg:0 2px 6px rgba(0,0,0,.45),0 22px 48px -20px rgba(0,0,0,.7)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
html.locked{overflow:hidden}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 var(--sans);
-webkit-font-smoothing:antialiased;transition:background-color .35s ease,color .35s ease}
::selection{background:var(--accent);color:#fff}
.wrap{max-width:1180px;margin:0 auto;padding:0 clamp(16px,4vw,40px)}
header .wrap{padding-top:clamp(40px,8vh,84px);padding-bottom:6px}
.head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px}
h1{margin:0;font-family:var(--serif);font-weight:600;font-size:clamp(38px,6vw,58px);letter-spacing:.06em;line-height:1.1}
h1 .latin{display:block;margin-top:10px;font-family:var(--sans);font-weight:400;font-size:11px;letter-spacing:.55em;color:var(--muted);text-transform:uppercase}
.tagline{margin:16px 0 0;font-family:var(--serif);font-size:17px}
.tagline .en{display:block;margin-top:5px;font-family:var(--sans);font-size:12.5px;color:var(--muted);font-style:italic;letter-spacing:.02em}
.toggle{flex:none;width:42px;height:42px;margin-bottom:4px;border-radius:50%;border:1px solid var(--line);
background:var(--panel);color:var(--text);font-size:16px;line-height:1;cursor:pointer;
transition:transform .25s ease,box-shadow .25s ease,border-color .25s ease}
.toggle:hover{transform:translateY(-2px);box-shadow:var(--shadow-sm);border-color:var(--accent)}
.toggle:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.toggle .sun{display:none}
:root[data-theme="d"] .toggle .sun{display:inline}
:root[data-theme="d"] .toggle .moon{display:none}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:28px}
.chips a{font-size:13px;color:var(--muted);text-decoration:none;border:1px solid var(--line);
background:var(--panel);border-radius:999px;padding:5px 13px;
transition:color .2s,border-color .2s,transform .2s}
.chips a:hover{color:var(--accent);border-color:var(--accent);transform:translateY(-1px)}
.chips i{font-style:normal;opacity:.6;margin-left:3px}
.group{margin-top:clamp(30px,5vh,52px)}
.group h2{margin:0 0 18px;font-family:var(--serif);font-weight:600;font-size:22px;letter-spacing:.03em}
.group h2 small{margin-left:10px;font-family:var(--sans);font-weight:400;font-size:13px;color:var(--muted);letter-spacing:0}
.masonry{columns:1;column-gap:20px}
@media(min-width:560px){.masonry{columns:2}}
@media(min-width:820px){.masonry{columns:3}}
@media(min-width:1140px){.masonry{columns:4}}
.card{display:block;break-inside:avoid;margin:0 0 20px;border-radius:var(--radius);overflow:hidden;
background:var(--panel);box-shadow:var(--shadow-sm);
transition:transform .35s cubic-bezier(.2,.7,.3,1),box-shadow .35s ease}
.card:hover,.card:focus-visible{transform:translateY(-5px);box-shadow:var(--shadow-lg)}
.card:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.card img{display:block;width:100%;height:auto;background-repeat:no-repeat;background-size:cover;
background-position:center;transition:transform .6s cubic-bezier(.2,.7,.3,1)}
.card:hover img{transform:scale(1.025)}
.empty{padding:90px 0 60px;text-align:center}
.empty h2{margin:0;font-family:var(--serif);font-weight:600;font-size:24px}
.empty p{color:var(--muted);margin:12px 0 0}
.empty code{background:var(--chip);border:1px solid var(--line);border-radius:6px;padding:2px 8px;font-size:14px}
footer .wrap{border-top:1px solid var(--line);margin-top:44px;padding-top:22px;padding-bottom:46px;
font-size:13px;color:var(--muted)}
footer p{margin:4px 0}
footer .note{font-family:var(--serif);color:var(--text);font-size:14px}
.lightbox{position:fixed;inset:0;z-index:60;display:flex;flex-direction:column;align-items:center;
justify-content:center;gap:16px;padding:28px;margin:0;background:rgba(12,15,13,.8);
backdrop-filter:blur(20px) saturate(.85);-webkit-backdrop-filter:blur(20px) saturate(.85);
opacity:0;visibility:hidden;cursor:zoom-out;
transition:opacity .3s ease,visibility 0s linear .3s}
.lightbox.open{opacity:1;visibility:visible;transition:opacity .3s ease}
.lightbox figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:14px;max-width:100%}
.lightbox img{max-width:min(1200px,92vw);max-height:84vh;width:auto;height:auto;border-radius:12px;
box-shadow:0 24px 80px -20px rgba(0,0,0,.7);cursor:default;opacity:0;transform:scale(.965);
transition:opacity .35s ease,transform .35s cubic-bezier(.2,.7,.3,1)}
.lightbox img.ld{opacity:1;transform:none}
.lightbox figcaption{color:#d6ddd6;font-size:13.5px;letter-spacing:.02em;text-align:center;
max-width:88vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(prefers-reduced-motion:reduce){*{transition-duration:.01ms!important}
html{scroll-behavior:auto}.lightbox img{opacity:1;transform:none}}
"""

# 防闪主题：body 渲染前根据 localStorage / 系统偏好定好 data-theme
THEME_JS = (
    'var e=document.documentElement,t;try{t=localStorage.getItem("petal:theme")}'
    'catch(n){}"l"!=t&&"d"!=t&&(t=matchMedia("(prefers-color-scheme:dark)").matches?"d":"l"),'
    "e.dataset.theme=t;"
)

# 灯箱 + 主题切换：原生 JS，无依赖
APP_JS = (
    "!function(){"
    'var r=document.documentElement,b=document.getElementById("theme-toggle"),'
    'x=document.getElementById("lightbox"),v=x.querySelector("img"),c=x.querySelector("figcaption"),'
    'd=JSON.parse(document.getElementById("gallery-data").textContent),i=0;'
    'b.addEventListener("click",function(){var t="d"==r.dataset.theme?"l":"d";r.dataset.theme=t;'
    'try{localStorage.setItem("petal:theme",t)}catch(e){}});'
    "function s(n){i=(n+d.length)%d.length;var p=d[i];v.classList.remove(\"ld\");"
    'v.onload=function(){v.classList.add("ld")};v.src=p.f;v.width=p.w;v.height=p.h;v.alt=p.a;'
    'c.textContent=p.a+(p.m?" — "+p.m:"")}'
    'function h(){x.classList.remove("open");r.classList.remove("locked");v.removeAttribute("src")}'
    'document.addEventListener("click",function(e){var a=e.target.closest("a.card");'
    "a&&(e.preventDefault(),s(+a.dataset.i),x.classList.add(\"open\"),r.classList.add(\"locked\"))});"
    'x.addEventListener("click",function(e){e.target!==v&&h()});'
    'document.addEventListener("keydown",function(e){if(!x.classList.contains("open"))return;'
    'e.key==="Escape"?h():e.key==="ArrowRight"?s(i+1):e.key==="ArrowLeft"&&s(i-1)});'
    "}();"
)


def standard_variant(variants: list[dict]) -> dict:
    """最接近 1080w 的那档作为 <img src>；不足 1080 时取最大档。"""
    return min(variants, key=lambda v: (abs(v["width"] - 1080), -v["width"]))


def srcset_for(variants: list[dict]) -> str:
    return ", ".join(f"{quote('p/' + v['file'])} {v['width']}w" for v in sorted(variants, key=lambda v: v["width"]))


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def render_page(site: dict) -> str:
    """site: title/tagline/tagline_en/footer_note/theme/groups/items/stats…"""
    items_json = json.dumps(site["items"], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")

    chips = ""
    if len(site["groups"]) >= 2:
        links = "".join(
            f'<a href="#g{k}">{esc(g["label"])}<i>{g["count"]}</i></a>'
            for k, g in enumerate(site["groups"])
        )
        chips = f'<nav class="chips" aria-label="分组导航">{links}</nav>'

    sections = []
    for k, g in enumerate(site["groups"]):
        cards = []
        for p in g["photos"]:
            eager = ' fetchpriority="high"' if p["eager"] else ""
            cards.append(
                f'<a class="card" href="{p["full_url"]}" data-i="{p["index"]}">'
                f'<img src="{p["std_url"]}" srcset="{esc(p["srcset"])}" sizes="{SIZES}"'
                f' width="{p["width"]}" height="{p["height"]}" alt="{esc(p["alt"])}"'
                f' loading="{p["loading"]}" decoding="async"{eager}'
                f' style="background:url({p["lqip"]}) center/cover"></a>'
            )
        sections.append(
            f'<section class="group" id="g{k}">'
            f'<h2>{esc(g["label"])}<small>{g["count"]} 张</small></h2>'
            f'<div class="masonry">{"".join(cards)}</div></section>'
        )
    body_main = "".join(sections) or (
        '<section class="empty"><h2>这里还没有照片</h2>'
        "<p>把 jpg、png 或 webp 放进文件夹，再跑一次 <code>python -m petal build</code>。</p></section>"
    )

    note = f'<p class="note">{esc(site["footer_note"])}</p>' if site.get("footer_note") else ""
    stats = site["stats"]
    footer = (
        f'{note}<p>© {site["year"]} {esc(site["title"])} · {stats["count"]} 张照片 · '
        f'{stats["human_in"]} → {stats["human_out"]} · 由 落英 · Petal 生成</p>'
    )

    theme = site.get("theme", "auto")
    data_theme = {"light": "l", "dark": "d", "auto": "l"}[theme]

    return (
        "<!doctype html>\n"
        '<html lang="zh-CN" data-theme="' + data_theme + '">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f'<meta name="description" content="{esc(site["tagline"])}">\n'
        f"<title>{esc(site['title'])}</title>\n"
        f'<link rel="icon" href="{FAVICON}">\n'
        f"<script>{THEME_JS}</script>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n<body>\n"
        '<header><div class="wrap"><div class="head"><div>'
        f"<h1>{esc(site['title'])}<span class=\"latin\">Petal</span></h1>"
        f'<p class="tagline">{esc(site["tagline"])}'
        f'<span class="en">{esc(site["tagline_en"])}</span></p>'
        "</div>"
        '<button id="theme-toggle" class="toggle" type="button" aria-label="切换明暗主题">'
        '<span class="moon">&#9790;</span><span class="sun">&#9788;</span></button>'
        f"</div>{chips}</div></header>\n"
        f"<main><div class=\"wrap\">{body_main}</div></main>\n"
        f'<footer><div class="wrap">{footer}</div></footer>\n'
        '<div id="lightbox" class="lightbox" role="dialog" aria-modal="true" aria-label="查看大图">'
        "<figure><img alt=\"\"><figcaption></figcaption></figure></div>\n"
        f'<script type="application/json" id="gallery-data">{items_json}</script>\n'
        f"<script>{APP_JS}</script>\n"
        "</body>\n</html>\n"
    )
