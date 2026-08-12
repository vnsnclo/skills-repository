# 视频硬字幕提取 Skill

这个 Skill 用于把已经烧录进 MP4、MOV 等视频画面的字幕，通过本地 OCR 恢复为可编辑的 SRT 和 TXT。流程包括视频流探测、字幕区域抽帧、中文 OCR、连续帧去重、时间轴合并、逐条人工复核和格式验证。

## 特点

- 先检查独立字幕轨，避免对软字幕做不必要的 OCR。
- 默认以 4fps 扫描底部字幕区域，时间边界精度约为 ±0.125 秒。
- 对低置信度画面追加增强识别，并按相似度合并连续帧。
- 保留中间帧、原始 OCR 和人工修订记录，方便追溯。
- 默认不上传视频、不修改源文件、不自动删除中间产物。
- 默认阻止隐式模型下载，避免未获同意时联网写入环境。

## 文件结构

```text
extract-burned-subtitles/
├── SKILL.md
├── README.md
├── requirements.txt
├── agents/
│   └── openai.yaml
└── scripts/
    ├── inspect_video.py
    ├── extract_subtitles.py
    ├── make_review_sheets.py
    ├── apply_corrections.py
    └── validate_subtitles.py
```

## 环境要求

- Python 3.10 或更高版本
- FFmpeg（包括 `ffmpeg` 与 `ffprobe`）
- Python 包：RapidOCR、ONNX Runtime、OpenCV、NumPy

建议在每个任务自己的虚拟环境里安装：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

安装 Python 包和 RapidOCR 首次下载模型都会产生网络下载。执行前必须先说明下载用途、保存路径、所用环境和工具、是否可复用，并取得用户同意。

## 快速使用

### 1. 检查视频是否已有字幕轨

```bash
python scripts/inspect_video.py "/path/to/video.mp4"
```

如果 `has_subtitle_stream` 为 `true`，应直接用 FFmpeg 导出字幕轨，不需要 OCR。

### 2. 提取硬字幕

```bash
python scripts/extract_subtitles.py \
  "/path/to/video.mp4" \
  --run-dir "/path/to/work/run-001"
```

模型尚不存在时，脚本会停止并提示。只有在已经取得下载同意后，才使用 `--allow-model-download`。

主要参数：

- `--sample-fps 4`：每秒采样帧数。
- `--crop-y 0.62`：裁剪区域顶部占画面高度的比例。
- `--crop-height 0.36`：裁剪区域高度比例。
- `--scale 2`：字幕区域放大倍数。
- `--min-center-y 0.42`：字幕在裁剪图内的最低纵向位置。
- `--max-center-x-offset 0.36`：字幕中心偏离画面中心的最大比例。

### 3. 生成复核总览

```bash
python scripts/make_review_sheets.py \
  --segments "/path/to/work/run-001/segments.json" \
  --frames "/path/to/work/run-001/frames" \
  --output-dir "/path/to/work/run-001/review-sheets"
```

即使 `review.tsv` 没有报错，也应查看全部总览图。高置信度不代表引号、标点和形近字一定正确。

### 4. 应用人工修订

创建 `corrections.json`：

```json
{
  "text_overrides": {},
  "time_overrides": {},
  "drop_indices": [],
  "extend_last_to_video_end": true,
  "normalize_chinese_punctuation": false
}
```

字段含义：

- `text_overrides`：按字幕编号覆盖文字。
- `time_overrides`：按字幕编号调整起止秒数。
- `drop_indices`：移除确认属于误识别的字幕编号。
- `extend_last_to_video_end`：把最后一条字幕延长到视频结尾。
- `normalize_chinese_punctuation`：把常见半角标点转为中文全角标点。

然后导出：

```bash
python scripts/apply_corrections.py \
  --segments "/path/to/work/run-001/segments.json" \
  --corrections "/path/to/work/run-001/corrections.json" \
  --srt "/path/to/outputs/video.srt" \
  --txt "/path/to/outputs/video.txt" \
  --video-duration "${VIDEO_DURATION_SECONDS}"
```

### 5. 验证结果

```bash
python scripts/validate_subtitles.py \
  --srt "/path/to/outputs/video.srt" \
  --txt "/path/to/outputs/video.txt" \
  --duration "${VIDEO_DURATION_SECONDS}"
```

## 注意事项

- 当前算法针对底部居中、白字黑边的中文硬字幕效果最佳。
- 字幕位于顶部、两侧或动态移动时，需要调整裁剪和位置参数。
- 不要直接相信自动标点，应以视频画面为准。
- 不要为了清理空间自动删除中间帧或模型，删除前必须征得用户同意。
