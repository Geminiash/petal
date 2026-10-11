# 落英 · Petal

![示例画廊](docs/screenshot.webp)

把一个本地照片文件夹，一键变成绝美的静态画廊。所有图片 WebP 化，三档尺寸 + LQIP 占位，
输出单个 `index.html`：零 CDN、零框架、零外部请求。

> 光落进镜头，就成了可以回看的日子。
> Light lands, and stays.

## 特性

- **全图 WebP 化**：jpg / jpeg / png / bmp / tiff / webp → 三档 WebP——缩略 480w（q78）、
  标准 1080w（q82）、全尺寸 1920w（q85），等比缩放、只缩不放，小图不放大。
- **隐私先行**：输出一律剥离 EXIF/GPS（保留 ICC 色彩配置）；剥离前提取拍摄参数
  （机型/光圈/焦距/ISO/曝光/拍摄时间）存入 `petal.json`，在灯箱字幕里展示。
- **LQIP 占位**：24px 宽高斯模糊小图 base64 内联，配合固有宽高，首屏无跳色、无布局跳动。
- **自适应加载**：`srcset` 三档 + `sizes`，`loading="lazy"` + `decoding="async"`；
  前 3 张 eager + `fetchpriority="high"` 保 LCP。
- **站点地图式目录**：按拍摄月份（EXIF `DateTimeOriginal`，缺省回退文件 mtime）或文件夹分组，
  页首锚点导航。
- **灯箱**：原生 JS 约 1.2KB 内联，`←`/`→` 切换、`Esc` 关闭、点击遮罩关闭、背景 blur、缩放过渡。
- **双主题**：暖纸浅色（`#faf7f2` 系）与深林暗色（`#0f1512` 系），右上角切换，localStorage 记忆，
  未选择时跟随系统。
- **可选并行**：multiprocessing 默认 4 workers，`--workers 1` 串行；单张失败不拖垮整个画廊。
- **本地预览**：`petal serve` 一条命令起本地服务器。

## Quick Start (English)

```bash
# 1. Install (Python 3.11+)
python -m pip install pillow

# 2. Build a gallery from a photo folder
python -m petal build ./photos -o ./site

# 3. Preview locally
python -m petal serve ./site            # → http://127.0.0.1:8000/

# Optional: install as a CLI
python -m pip install -e .
petal build ./photos -o ./site
```

The output is a fully static folder — `index.html`, `p/*.webp` and `petal.json`.
Upload it anywhere; no server-side code, no CDN, no external requests.

## 转换实测报告

20 张合成样例（4000×2667，带渐变/形体细节/颗粒，单张 3.66–4.00 MB，无真实人物与地点信息），
`--workers 4` 跑完整管线，复现命令：`python scripts/benchmark.py -n 20`。

| # | 样例 | 源 JPEG | WebP 480w | WebP 1080w | WebP 全尺寸 | LQIP | WebP 合计 | 压缩到 |
|---|---|---|---|---|---|---|---|---|
| 1 | sample_00.jpg | 3.67 MB | 6 KB | 40 KB | 392 KB (1920w) | 0.1 KB | 0.43 MB | 11.7% |
| 2 | sample_01.jpg | 4.00 MB | 5 KB | 38 KB | 388 KB (1920w) | 0.1 KB | 0.42 MB | 10.5% |
| 3 | sample_02.jpg | 4.00 MB | 5 KB | 37 KB | 389 KB (1920w) | 0.1 KB | 0.42 MB | 10.5% |
| 4 | sample_03.jpg | 4.00 MB | 5 KB | 37 KB | 387 KB (1920w) | 0.1 KB | 0.42 MB | 10.5% |
| 5 | sample_04.jpg | 3.66 MB | 5 KB | 39 KB | 390 KB (1920w) | 0.1 KB | 0.42 MB | 11.6% |
| 6 | sample_05.jpg | 4.00 MB | 5 KB | 39 KB | 389 KB (1920w) | 0.1 KB | 0.42 MB | 10.6% |
| 7 | sample_06.jpg | 3.66 MB | 5 KB | 38 KB | 389 KB (1920w) | 0.1 KB | 0.42 MB | 11.5% |
| 8 | sample_07.jpg | 3.66 MB | 5 KB | 39 KB | 390 KB (1920w) | 0.1 KB | 0.42 MB | 11.6% |
| 9 | sample_08.jpg | 4.00 MB | 5 KB | 38 KB | 389 KB (1920w) | 0.1 KB | 0.42 MB | 10.5% |
| 10 | sample_09.jpg | 3.66 MB | 6 KB | 40 KB | 397 KB (1920w) | 0.1 KB | 0.43 MB | 11.8% |
| 11 | sample_10.jpg | 4.00 MB | 5 KB | 38 KB | 388 KB (1920w) | 0.1 KB | 0.42 MB | 10.5% |
| 12 | sample_11.jpg | 4.00 MB | 5 KB | 38 KB | 385 KB (1920w) | 0.1 KB | 0.42 MB | 10.4% |
| 13 | sample_12.jpg | 3.66 MB | 6 KB | 39 KB | 391 KB (1920w) | 0.1 KB | 0.43 MB | 11.6% |
| 14 | sample_13.jpg | 4.00 MB | 5 KB | 38 KB | 386 KB (1920w) | 0.1 KB | 0.42 MB | 10.4% |
| 15 | sample_14.jpg | 3.66 MB | 6 KB | 38 KB | 394 KB (1920w) | 0.1 KB | 0.43 MB | 11.7% |
| 16 | sample_15.jpg | 4.00 MB | 5 KB | 38 KB | 390 KB (1920w) | 0.1 KB | 0.42 MB | 10.6% |
| 17 | sample_16.jpg | 3.67 MB | 6 KB | 40 KB | 394 KB (1920w) | 0.1 KB | 0.43 MB | 11.7% |
| 18 | sample_17.jpg | 3.66 MB | 5 KB | 39 KB | 391 KB (1920w) | 0.1 KB | 0.43 MB | 11.6% |
| 19 | sample_18.jpg | 4.00 MB | 5 KB | 37 KB | 388 KB (1920w) | 0.1 KB | 0.42 MB | 10.5% |
| 20 | sample_19.jpg | 3.66 MB | 6 KB | 39 KB | 389 KB (1920w) | 0.1 KB | 0.42 MB | 11.6% |
| — | **总计（20 张）** | **76.6 MB** | | | | | **8.5 MB** | **11.1%** |

- 转换用时 **5.3 s**（4 进程，Windows 11，Python 3.11 + Pillow 12）。
- 样例为脚本合成的"类照片"图，不含真实人物/地点；真实照片的压缩率随内容波动，
  细节丰富的图通常落在源体积的 5%–15% 区间。
- 页面骨架体积：CSS 约 5.3 KB + JS 约 1.2 KB（全部内联进 `index.html`，JS 上限 2KB 有测试守护）。

## 使用

```bash
python -m petal build <照片目录> -o <输出目录> [选项]

# 常用选项
--config petal.toml        # pyproject 式 TOML 配置（读 [tool.petal] 小节）
--title "京都行"            # 覆盖画廊标题
--group-by folder          # 按文件夹分组（默认 date：按拍摄月份）
--workers 4                # 并行进程数（默认 4；1 为串行）
--no-recursive             # 只扫描第一层

python -m petal serve <输出目录> [--host 127.0.0.1] [--port 8000]
```

### 配置文件（pyproject 式 TOML）

```toml
[tool.petal]
title = "落英"
tagline = "光落进镜头，就成了可以回看的日子。"
tagline_en = "Light lands, and stays."
footer_note = ""            # 页脚寄语，可留空
group_by = "date"           # date | folder
theme = "auto"              # light | dark | auto（页面初始主题）
workers = 4
recursive = true
```

命令行选项优先于配置文件。输出目录不要放在照片目录里。

### 输出结构

```
site/
├── index.html      # 画廊本体：CSS/JS 全内联，双主题 + 灯箱
├── petal.json      # 构建清单：每张图的档位、体积、拍摄参数（机型/光圈/焦距/ISO/日期）
└── p/              # WebP 变体：<哈希>-480.webp / -1080 / -1920 …
```

## 设计说明

WebP 管线的取舍细节（档位与质量、EXIF 剥离策略、LQIP 的零 JS 方案、分组规则）见
[docs/webp-pipeline.md](docs/webp-pipeline.md)。

## 开发

```bash
python -m pip install pillow pytest
python -m pytest tests -q
```

测试夹具用 Pillow 现场生成图片，仓库不提交任何二进制图。基准脚本：`python scripts/benchmark.py -n 20`。

## License

[MIT](LICENSE)
