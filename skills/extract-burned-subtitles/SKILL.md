---
name: extract-burned-subtitles
description: 从 MP4、MOV 等视频画面中提取已经烧录、嵌入或压制的硬字幕，经过抽帧、底部区域裁剪、中文 OCR、连续帧去重、时间轴合并和人工复核，导出 SRT 与 TXT。用于用户要求提取画面字幕、识别无独立字幕轨的视频字幕、把硬字幕转成可编辑字幕、校订 OCR 字幕或检查字幕时间轴时。
---

# 提取视频硬字幕

将已经烧录进画面的字幕恢复为可编辑的 SRT 和 TXT。优先保留视频里真实出现的文字、换行与时间，不凭音频擅自改写。

## 强制规则

1. 在运行任何终端命令前，先向用户说明命令用途及会新增、修改、覆盖或删除的文件与配置。
2. 先用 `ffprobe` 判断是否存在独立字幕轨；有字幕轨时直接导出，不进入 OCR 流程。
3. 不修改、不重新封装源视频。所有帧、模型、日志和候选结果写到单独任务目录。
4. 不自动删除中间帧、虚拟环境、模型或结果。需要删除时先取得用户同意；涉及大量、重要或敏感路径时再次确认。
5. 不自动下载任何内容。安装 Python 包或下载 OCR 模型前，必须说明下载用途、保存路径、所用环境和工具、是否可复用，并取得用户同意。
6. 不把视频、帧或字幕上传到网络。默认全程本地处理。
7. OCR 结果必须人工复核；不得把高置信度等同于绝对正确。

## 工作流

### 1. 探测视频

```bash
python scripts/inspect_video.py "/path/to/video.mp4"
```

- `has_subtitle_stream=true`：用 `ffmpeg -map` 直接导出字幕轨。
- `has_subtitle_stream=false`：抽查画面，确认字幕位置、语言、单双行和转场方式，再进入 OCR。

### 2. 检查依赖与下载边界

需要 `ffmpeg`、`ffprobe`、Python 3.10+、RapidOCR、ONNX Runtime、OpenCV 和 NumPy。脚本不会安装依赖。依赖缺失时先按强制规则说明下载详情并取得同意，再在任务专用虚拟环境安装 `requirements.txt`。

RapidOCR 首次初始化可能下载 ONNX 模型；`extract_subtitles.py` 默认阻止隐式下载。只有在已经取得用户同意后，才可显式传入 `--allow-model-download`。

### 3. 运行 OCR

为每次运行创建新的空目录，不覆盖旧任务：

```bash
python scripts/extract_subtitles.py \
  "/path/to/video.mp4" \
  --run-dir "/path/to/work/run-001" \
  --sample-fps 4 \
  --crop-y 0.62 \
  --crop-height 0.36 \
  --scale 2
```

默认参数适合底部居中的简体中文字幕：

- 转场很快：提高 `--sample-fps`；4fps 的边界精度约为 ±0.125 秒。
- 字幕偏高或多行：调整 `--crop-y` 与 `--crop-height`，两者之和不得超过 1。
- 字体较小：提高 `--scale`，代价是速度和磁盘占用。
- 字幕不在底部中央：调整 `--min-center-y` 和 `--max-center-x-offset`。

任务目录输出：`frames/`、`video_info.json`、`raw_ocr.jsonl`、`segments.json`、`candidate.srt`、`candidate.txt`、`review.tsv`。

### 4. 生成总览并逐条复核

```bash
python scripts/make_review_sheets.py \
  --segments "/path/to/work/run-001/segments.json" \
  --frames "/path/to/work/run-001/frames" \
  --output-dir "/path/to/work/run-001/review-sheets"
```

必须检查全部唯一字幕段，而不只是 `review.tsv`。重点检查引号、书名号、标点、形近字、背景题字、角标、短暂连接词、开头标题、结尾字幕和双行顺序。

将确认后的修订写入 JSON：

```json
{
  "text_overrides": {},
  "time_overrides": {},
  "drop_indices": [],
  "extend_last_to_video_end": true,
  "normalize_chinese_punctuation": false
}
```

- `text_overrides`：以字幕编号字符串为键，以逐帧核对后的文字为值。
- `time_overrides`：以字幕编号字符串为键，以包含可选 `start`、`end` 秒数的对象为值。
- `drop_indices`：填写确认属于误识别、需要移除的字幕编号。
- `extend_last_to_video_end`：决定是否把最后一条延长至视频结尾。
- `normalize_chinese_punctuation`：决定是否把半角逗号、问号等转换为中文全角形式。

只改画面能够确认的内容，不根据语言习惯擅自润色。

### 5. 应用修订并导出

```bash
python scripts/apply_corrections.py \
  --segments "/path/to/work/run-001/segments.json" \
  --corrections "/path/to/work/run-001/corrections.json" \
  --srt "/path/to/outputs/video.srt" \
  --txt "/path/to/outputs/video.txt" \
  --json "/path/to/work/run-001/final_segments.json" \
  --video-duration "${VIDEO_DURATION_SECONDS}"
```

TXT 每条字幕一行；SRT 保留双行换行。默认拒绝覆盖已有输出，除非用户明确授权后传入 `--force`。

### 6. 验证

```bash
python scripts/validate_subtitles.py \
  --srt "/path/to/outputs/video.srt" \
  --txt "/path/to/outputs/video.txt" \
  --duration "${VIDEO_DURATION_SECONDS}"
```

确认 UTF-8、编号连续、时间单调无重叠、末条不超过视频时长、SRT/TXT 数量一致，并用 `ffprobe` 确认 SRT 可识别为 `subrip`。

## 失败处理

- OCR 依赖不存在：停止并征求下载同意，不自动 `pip install`。
- 模型缺失：报告即将写入的虚拟环境位置；获得同意后才传入 `--allow-model-download`。
- 背景文字误入：缩小裁剪区域或收紧位置过滤，不要只提高置信度。
- OCR 与音频不一致：以画面字幕为准，除非用户明确要求内容校正。
- 时间轴密集闪烁：提高采样率并复核转场帧，不猜测边界。

## 脚本

- `scripts/inspect_video.py`：只读探测视频流与字幕轨。
- `scripts/extract_subtitles.py`：抽帧、OCR、去重并生成候选时间轴。
- `scripts/make_review_sheets.py`：生成分段中间帧总览。
- `scripts/apply_corrections.py`：应用人工修订并导出最终文件。
- `scripts/validate_subtitles.py`：独立验证 SRT/TXT。
