# Changelog

所有显著变更记录在本文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-10-11

### 新增

- `python -m petal build`：扫描照片目录（jpg/jpeg/png/bmp/tiff/webp），一键生成静态画廊。
- WebP 三档管线：缩略 480w（q78）/ 标准 1080w（q82）/ 全尺寸 1920w（q85），等比缩放、只缩不放，
  一律剥离 EXIF/GPS（保留 ICC 色彩配置）。
- 隐私先行：转换前提取拍摄参数（机型/光圈/焦距/ISO/曝光/拍摄时间）写入 `petal.json` 供展示，
  输出图片不携带任何元数据。
- LQIP 占位：24w 高斯模糊小图 base64 内联，首屏无跳色、无布局跳动。
- `srcset` 多档自适应 + `loading="lazy"` + `decoding="async"`，首 3 张 eager + `fetchpriority="high"`。
- 站点地图式目录：按拍摄月份（EXIF DateTimeOriginal，缺省回退文件 mtime）或文件夹分组，锚点导航。
- 灯箱：原生 JS 单文件内联（约 1.2KB），键盘 ←/→/Esc、点击遮罩关闭、背景 blur、缩放过渡。
- 双主题：暖纸浅色（#faf7f2 系）/ 深林暗色（#0f1512 系），右上角切换，localStorage 记忆，
  未选择时跟随系统偏好。
- `python -m petal serve`：本地预览（http.server 封装）。
- 可选并行：multiprocessing 默认 4 workers，`--workers 1` 串行。
- `--config`：pyproject 式 TOML 配置（`[tool.petal]` 小节）。
- pytest 测试 38 项（夹具用 Pillow 现场生成，仓库不携带二进制图）。
