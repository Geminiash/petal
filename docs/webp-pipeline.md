# 落英 · Petal — WebP 管线设计说明

> 本文拆解 petal 从"一个照片文件夹"到"一个静态画廊"的完整管线，以及每一步的取舍。

## 管线总览

```
扫描照片（7 种格式，跳过隐藏文件）
  ↓ 每张图（可选并行，默认 4 进程）
摆正方向（EXIF Orientation → 物理像素）
  ↓
归一色彩模式（RGB / 保留 alpha→RGBA）
  ↓（同时，在剥离前）
提取拍摄参数（机型/光圈/焦距/ISO/曝光/DateTimeOriginal）→ JSON
  ↓
三档 WebP：480w q78 / 1080w q82 / 1920w q85（只缩不放，宽度去重）
  ↓
LQIP：24w → 高斯模糊 → WebP q35 → base64 内联
  ↓
模板渲染：单个 index.html（CSS/JS 全内联）+ petal.json + p/*.webp
```

## 档位与质量

| 档位 | 目标宽 | 质量 | 用途 |
|---|---|---|---|
| thumb | 480w | 78 | `srcset` 小屏档，移动端主力 |
| standard | 1080w | 82 | `<img src>` 默认档，瀑布流格子 |
| full | 1920w | 85 | `srcset` 大屏档 + 灯箱 |

三条规则：

1. **只缩不放**。目标宽取 `min(目标, 原宽)`，小于 480px 的原图只出一档。
2. **宽度去重**。三档钳制后若宽度重合（如 800px 原图的 1080 与 1920 档都落在 800），
   只写一份文件，`srcset` 不重复；重合档位采用更大档的质量。
3. **质量梯度错位**（78/82/85）。缩略图放大后噪点最明显，质量偏低会糊；全尺寸在 q85 后
   体积陡增而观感提升有限。三档差距刻意收窄，让 `srcset` 切换时不跳质。

文件名用相对路径的 blake2b 前 12 位十六进制：规避中文/空格/同名目录的路径问题，
重建幂等（同一路径永远得到同一个名字），`petal.json` 保留源路径供追溯。

## 隐私：剥什么，留什么

- **剥掉**：EXIF 全部（含 GPS、拍摄时间、机型、序列号）、XMP、缩略图嵌入。
  机制上不需要"清洗"——Pillow 只有显式传 `exif=` 才会把元数据写进 WebP，petal 永远不传。
  测试用两层断言守住：`getexif()` 为空 + 文件字节里搜不到机型字符串。
- **留 ICC 色彩配置**：广色域屏上颜色不走样，且不含隐私。
- **物理摆正**：EXIF Orientation 在缩放前用 `ImageOps.exif_transpose` 烘焙进像素，
  之后方向信息随元数据一起消失，图不会横躺。
- **提取后进 JSON，不进图片**：机型/光圈/焦距/ISO/曝光/`DateTimeOriginal` 在转换前读出，
  写入 `petal.json` 与灯箱字幕。GPS 标签**从不读取**，`exif.ALLOWED_KEYS` 白名单有测试守门。

## LQIP：零 JS 的占位方案

常见做法是"小图 data URI 打底 + 大图淡入"，需要一小段 JS 监听 load。petal 用更省的方式：

```html
<img src="…-1080.webp" width="1600" height="1200"
     style="background:url(data:image/webp;base64,…) center/cover">
```

- 占位图作为**元素自身的背景**：加载期间背景先显示，解码完成像素覆盖背景，无需任何 JS。
- `width`/`height` 属性给出固有宽高比，图片未加载时布局已稳定（无 CLS）。
- LQIP 规格：24px 宽 → 高斯模糊 r1.4 → WebP q35 method6，单张约 100–200 字节（base64 后），
  100 张图约多付 15KB HTML。
- 首屏无跳色：占位是同图的模糊版，色块分布一致，从糊到清是"对焦"而不是"换图"。

## 页面骨架

- **单个 index.html**：CSS（约 5.3KB）与 JS（约 1.2KB，硬上限 2KB，有测试）全部内联。
  全站请求 = HTML 本身 + N 个 WebP，无字体、无图标库、无 CDN（favicon 是 data URI SVG）。
- **灯箱**：事件委托 + 单函数循环取模，键盘 `←`/`→`/`Esc`，点击遮罩关闭（点图不关），
  背景模糊 + 缩放过渡。画廊数据放在 `<script type="application/json">` 里——是数据不是代码，
  不占 JS 预算。
- **双主题**：`data-theme="l|d"` 驱动 CSS 变量；一段约 200 字节的脚本放在 `<head>`，
  在首帧绘制前读 localStorage（否则跟系统），从根上消灭暗色闪白。
- **加载优先级**：前 3 张 `loading="eager"` + `fetchpriority="high"`，其余全部懒加载 +
  `decoding="async"`；`sizes` 断言与 CSS columns 断点一一对应（1/2/3/4 列）。
- **分组**：默认按拍摄月份倒序（EXIF `DateTimeOriginal`，缺省回退文件 mtime），
  `--group-by folder` 按相对目录分组；≥2 组时页首出现锚点胶囊导航。
- **降级**：无 JS 时瀑布流完整可用（灯箱与主题切换不可用，卡片的 `<a href>` 仍可打开全尺寸图）。

## 并行模型

`ProcessPoolExecutor`（Windows spawn 安全：worker 是模块级函数，任务与结果都是可 pickle 的 dict，
worker 自行打开文件，不在进程间传 Image 对象）。默认 4 workers，`--workers 1` 退化为串行；
单张解码失败只记录并跳过，最后统一汇报，不影响其余照片。

## 已知取舍

- 不做增量构建：重建是全量覆盖（文件名幂等，重复转换成本 = 纯 CPU）。
- 不生成 AVIF：Pillow 无原生 AVIF 编码，依赖最小化优先。
- 灯箱不预加载相邻图：换的是"全尺寸 1920w 档"，网络快时感知不到；保持 JS 极简优先。
