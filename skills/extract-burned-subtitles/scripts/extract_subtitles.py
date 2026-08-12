#!/usr/bin/env python3
"""抽帧、中文 OCR、连续帧去重并生成候选硬字幕。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


cv2: Any = None
np: Any = None
RapidOCR: Any = None


def load_dependencies(allow_model_download: bool) -> Path:
    global cv2, np, RapidOCR

    missing = [
        name
        for name in ("cv2", "numpy", "rapidocr", "onnxruntime")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise SystemExit(
            "缺少 Python 依赖："
            + ", ".join(missing)
            + "。脚本不会自动安装；请先说明下载详情并取得用户同意。"
        )

    rapidocr_spec = importlib.util.find_spec("rapidocr")
    if rapidocr_spec is None or rapidocr_spec.origin is None:
        raise SystemExit("无法定位 RapidOCR 安装目录。")
    model_dir = Path(rapidocr_spec.origin).resolve().parent / "models"
    model_files = list(model_dir.glob("*.onnx")) if model_dir.is_dir() else []
    roles = {
        "det": any("det" in path.stem.lower() for path in model_files),
        "rec": any("rec" in path.stem.lower() for path in model_files),
        "cls": any("cls" in path.stem.lower() for path in model_files),
    }
    if not all(roles.values()) and not allow_model_download:
        absent = [name for name, present in roles.items() if not present]
        raise SystemExit(
            "RapidOCR 模型不完整（缺少："
            + ", ".join(absent)
            + f"）。模型预计写入：{model_dir}。"
            + "脚本默认阻止隐式下载；说明用途、路径、环境、工具和复用范围并取得同意后，"
            + "再使用 --allow-model-download。"
        )

    import cv2 as cv2_module
    import numpy as numpy_module
    from rapidocr import RapidOCR as RapidOCRClass

    cv2 = cv2_module
    np = numpy_module
    RapidOCR = RapidOCRClass
    return model_dir


def probe_video(video: Path) -> dict:
    if shutil.which("ffprobe") is None:
        raise SystemExit("找不到 ffprobe；请先安装 FFmpeg。")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name,duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate:stream_tags=language,title",
            "-of",
            "json",
            str(video),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"ffprobe 失败：{result.stderr.strip()}")
    return json.loads(result.stdout)


def video_duration(info: dict) -> float:
    try:
        value = float(info["format"]["duration"])
    except (KeyError, TypeError, ValueError) as error:
        raise SystemExit("无法从 ffprobe 结果获取视频时长。") from error
    if value <= 0:
        raise SystemExit("视频时长无效。")
    return value


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", "", text)
    return text.strip("|丨I·•._")


def comparison_key(text: str) -> str:
    return "".join(
        char
        for char in normalize_text(text)
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def similarity(left: str, right: str) -> float:
    a = comparison_key(left)
    b = comparison_key(right)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        shorter = min(len(a), len(b))
        longer = max(len(a), len(b))
        if shorter >= 4:
            return max(0.78, shorter / longer)
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def contains_language_text(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fffA-Za-z0-9]", text))


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def line_text(parts: list[tuple[float, str]]) -> str:
    parts.sort(key=lambda item: item[0])
    result = ""
    for _, part in parts:
        if result and result[-1:].isascii() and part[:1].isascii():
            result += " "
        result += part
    return normalize_text(result)


def extract_positioned_text(
    result: Any,
    image_shape: tuple[int, ...],
    min_score: float,
    min_center_y: float,
    max_center_x_offset: float,
) -> tuple[str, float, list[dict]]:
    height, width = image_shape[:2]
    boxes = getattr(result, "boxes", None)
    texts = getattr(result, "txts", None)
    scores = getattr(result, "scores", None)
    if boxes is None or texts is None or scores is None:
        return "", 0.0, []

    accepted: list[dict] = []
    for box, raw_text, raw_score in zip(boxes, texts, scores):
        text = normalize_text(str(raw_text))
        score = float(raw_score)
        points = np.asarray(box, dtype=float)
        min_x, max_x = float(points[:, 0].min()), float(points[:, 0].max())
        min_y, max_y = float(points[:, 1].min()), float(points[:, 1].max())
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        box_width = max_x - min_x
        box_height = max_y - min_y
        if score < min_score or not contains_language_text(text):
            continue
        if center_y < height * min_center_y:
            continue
        if abs(center_x - width / 2) > width * max_center_x_offset:
            continue
        if box_width < 24 or box_height < 12:
            continue
        accepted.append(
            {
                "text": text,
                "score": score,
                "min_x": min_x,
                "max_x": max_x,
                "min_y": min_y,
                "max_y": max_y,
                "center_x": center_x,
                "center_y": center_y,
            }
        )

    if not accepted:
        return "", 0.0, []
    accepted.sort(key=lambda item: (item["center_y"], item["min_x"]))
    rows: list[list[dict]] = []
    for item in accepted:
        if not rows:
            rows.append([item])
            continue
        row_center = sum(value["center_y"] for value in rows[-1]) / len(rows[-1])
        row_height = sum(value["max_y"] - value["min_y"] for value in rows[-1]) / len(rows[-1])
        if abs(item["center_y"] - row_center) <= max(24.0, row_height * 0.65):
            rows[-1].append(item)
        else:
            rows.append([item])

    rendered_rows: list[str] = []
    weighted_score = 0.0
    weight_total = 0
    for row in rows:
        rendered = line_text([(item["min_x"], item["text"]) for item in row])
        if rendered:
            rendered_rows.append(rendered)
        for item in row:
            weight = max(1, len(comparison_key(item["text"])))
            weighted_score += item["score"] * weight
            weight_total += weight
    return "\n".join(rendered_rows), weighted_score / max(1, weight_total), accepted


def enhanced_image(image: Any) -> Any:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def choose_result(
    original: tuple[str, float, list[dict]],
    enhanced: tuple[str, float, list[dict]],
) -> tuple[tuple[str, float, list[dict]], str]:
    original_text, original_score, _ = original
    enhanced_text, enhanced_score, _ = enhanced
    if not enhanced_text:
        return original, "original"
    if not original_text:
        return enhanced, "enhanced"
    if similarity(original_text, enhanced_text) >= 0.78:
        if (
            len(comparison_key(enhanced_text)) > len(comparison_key(original_text))
            and enhanced_score >= original_score - 0.05
        ):
            return enhanced, "enhanced"
        if enhanced_score > original_score + 0.03:
            return enhanced, "enhanced"
        return original, "original"
    if enhanced_score > original_score + 0.12:
        return enhanced, "enhanced"
    return original, "original"


def canonical_text(items: list[dict]) -> str:
    choices = [item["text"] for item in items if item["text"]]
    if not choices:
        return ""
    counts = Counter(choices)
    scored: list[tuple[float, int, int, str]] = []
    for candidate in counts:
        support = sum(
            similarity(candidate, item["text"]) * max(0.5, float(item["score"]))
            for item in items
        )
        scored.append((support, counts[candidate], len(comparison_key(candidate)), candidate))
    return max(scored)[-1]


@dataclass
class Segment:
    items: list[dict] = field(default_factory=list)

    @property
    def first_frame(self) -> int:
        return int(self.items[0]["frame"])

    @property
    def last_frame(self) -> int:
        return int(self.items[-1]["frame"])

    @property
    def text(self) -> str:
        return canonical_text(self.items)


def fill_short_blank_gaps(entries: list[dict], max_gap: int = 2) -> None:
    index = 0
    while index < len(entries):
        if entries[index]["text"]:
            index += 1
            continue
        start = index
        while index < len(entries) and not entries[index]["text"]:
            index += 1
        end = index
        if start == 0 or end == len(entries) or end - start > max_gap:
            continue
        left = entries[start - 1]
        right = entries[end]
        if similarity(left["text"], right["text"]) >= 0.82:
            replacement = left if left["score"] >= right["score"] else right
            for gap_index in range(start, end):
                entries[gap_index]["text"] = replacement["text"]
                entries[gap_index]["score"] = min(left["score"], right["score"])
                entries[gap_index]["source"] = "interpolated"


def build_segments(entries: list[dict]) -> list[Segment]:
    fill_short_blank_gaps(entries)
    segments: list[Segment] = []
    current: Segment | None = None
    for entry in entries:
        if not entry["text"]:
            if current is not None:
                segments.append(current)
                current = None
            continue
        if current is None:
            current = Segment([entry])
        elif entry["frame"] == current.last_frame + 1 and similarity(current.text, entry["text"]) >= 0.72:
            current.items.append(entry)
        else:
            segments.append(current)
            current = Segment([entry])
    if current is not None:
        segments.append(current)

    merged: list[Segment] = []
    for segment in segments:
        if merged:
            previous = merged[-1]
            gap = segment.first_frame - previous.last_frame - 1
            if gap <= 2 and similarity(previous.text, segment.text) >= 0.80:
                previous.items.extend(segment.items)
                continue
        merged.append(segment)
    return merged


def segment_records(
    segments: list[Segment], sample_fps: float, duration: float
) -> list[dict]:
    interval = 1.0 / sample_fps
    records: list[dict] = []
    for index, segment in enumerate(segments):
        first_time = (segment.first_frame - 1) / sample_fps
        last_time = (segment.last_frame - 1) / sample_fps
        start = max(0.0, first_time - interval / 2)
        end = min(duration, last_time + interval / 2)
        if index and segment.first_frame == segments[index - 1].last_frame + 1:
            previous_last = (segments[index - 1].last_frame - 1) / sample_fps
            boundary = (previous_last + first_time) / 2
            records[-1]["end"] = boundary
            start = boundary

        text = segment.text
        scores = [float(item["score"]) for item in segment.items]
        variants = sorted({item["text"] for item in segment.items})
        reasons: list[str] = []
        if end - start < 0.50:
            reasons.append("short")
        if sum(scores) / len(scores) < 0.85:
            reasons.append("low_confidence")
        if len(variants) > 1 and min(similarity(text, variant) for variant in variants) < 0.78:
            reasons.append("variant_disagreement")
        if len(segment.items) == 1:
            reasons.append("single_sample")
        records.append(
            {
                "index": index + 1,
                "text": text,
                "start": start,
                "end": end,
                "first_frame": segment.first_frame,
                "last_frame": segment.last_frame,
                "sample_count": len(segment.items),
                "mean_confidence": sum(scores) / len(scores),
                "variants": variants,
                "review_reasons": reasons,
            }
        )
    return records


def write_candidates(records: list[dict], run_dir: Path) -> None:
    (run_dir / "segments.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    srt_blocks = [
        f"{item['index']}\n{srt_time(item['start'])} --> {srt_time(item['end'])}\n{item['text']}"
        for item in records
    ]
    (run_dir / "candidate.srt").write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")
    (run_dir / "candidate.txt").write_text(
        "\n".join(item["text"].replace("\n", " ") for item in records) + "\n",
        encoding="utf-8",
    )
    review_lines = [
        "index\tstart\tend\tconfidence\treasons\tfirst_frame\tlast_frame\ttext\tvariants"
    ]
    for item in records:
        if item["review_reasons"]:
            review_lines.append(
                "\t".join(
                    [
                        str(item["index"]),
                        srt_time(item["start"]),
                        srt_time(item["end"]),
                        f"{item['mean_confidence']:.4f}",
                        ",".join(item["review_reasons"]),
                        str(item["first_frame"]),
                        str(item["last_frame"]),
                        item["text"].replace("\n", " / "),
                        " || ".join(value.replace("\n", " / ") for value in item["variants"]),
                    ]
                )
            )
    (run_dir / "review.tsv").write_text("\n".join(review_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="从视频画面提取硬字幕")
    parser.add_argument("video", type=Path)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--sample-fps", type=float, default=4.0)
    parser.add_argument("--crop-y", type=float, default=0.62)
    parser.add_argument("--crop-height", type=float, default=0.36)
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument("--min-score", type=float, default=0.45)
    parser.add_argument("--enhance-below", type=float, default=0.88)
    parser.add_argument("--min-center-y", type=float, default=0.42)
    parser.add_argument("--max-center-x-offset", type=float, default=0.36)
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument(
        "--ocr-even-with-subtitle-stream",
        action="store_true",
        help="存在字幕轨时仍继续 OCR；默认停止并建议直接导出",
    )
    args = parser.parse_args()

    if not args.video.is_file():
        raise SystemExit(f"视频不存在：{args.video}")
    if args.sample_fps <= 0 or args.scale <= 0:
        raise SystemExit("sample-fps 和 scale 必须大于 0。")
    if not 0 <= args.crop_y < 1 or not 0 < args.crop_height <= 1:
        raise SystemExit("crop-y 或 crop-height 超出 0–1。")
    if args.crop_y + args.crop_height > 1.000001:
        raise SystemExit("crop-y 与 crop-height 之和不能超过 1。")
    if not 0 <= args.min_center_y <= 1 or not 0 <= args.max_center_x_offset <= 0.5:
        raise SystemExit("位置过滤参数无效。")
    if args.run_dir.exists() and any(args.run_dir.iterdir()):
        raise SystemExit(f"任务目录不是空目录，拒绝覆盖：{args.run_dir}")
    if shutil.which("ffmpeg") is None:
        raise SystemExit("找不到 ffmpeg；请先安装 FFmpeg。")

    info = probe_video(args.video)
    subtitle_streams = [
        stream for stream in info.get("streams", []) if stream.get("codec_type") == "subtitle"
    ]
    if subtitle_streams and not args.ocr_even_with_subtitle_stream:
        raise SystemExit("视频存在独立字幕轨；请优先直接导出。确需 OCR 时传入 --ocr-even-with-subtitle-stream。")
    duration = video_duration(info)
    model_dir = load_dependencies(args.allow_model_download)

    args.run_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = args.run_dir / "frames"
    frames_dir.mkdir()
    metadata = {
        "video": str(args.video.resolve()),
        "duration": duration,
        "model_dir": str(model_dir),
        "parameters": {
            "sample_fps": args.sample_fps,
            "crop_y": args.crop_y,
            "crop_height": args.crop_height,
            "scale": args.scale,
            "min_score": args.min_score,
            "enhance_below": args.enhance_below,
            "min_center_y": args.min_center_y,
            "max_center_x_offset": args.max_center_x_offset,
        },
        "ffprobe": info,
    }
    (args.run_dir / "video_info.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    video_filter = (
        f"fps={args.sample_fps},"
        f"crop=iw:ih*{args.crop_height}:0:ih*{args.crop_y},"
        f"scale=iw*{args.scale}:ih*{args.scale}:flags=lanczos"
    )
    extraction = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(args.video),
            "-vf",
            video_filter,
            "-q:v",
            "2",
            str(frames_dir / "frame_%06d.jpg"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if extraction.returncode != 0:
        raise SystemExit(f"ffmpeg 抽帧失败：{extraction.stderr.strip()}")
    frame_paths = sorted(frames_dir.glob("frame_*.jpg"))
    if not frame_paths:
        raise SystemExit("ffmpeg 未生成任何帧。")

    engine = RapidOCR()
    entries: list[dict] = []
    raw_path = args.run_dir / "raw_ocr.jsonl"
    with raw_path.open("w", encoding="utf-8") as raw_file:
        for position, frame_path in enumerate(frame_paths, start=1):
            image = cv2.imread(str(frame_path))
            if image is None:
                raise SystemExit(f"无法读取帧：{frame_path}")
            original = extract_positioned_text(
                engine(image),
                image.shape,
                args.min_score,
                args.min_center_y,
                args.max_center_x_offset,
            )
            chosen = original
            source = "original"
            if not original[0] or original[1] < args.enhance_below:
                enhanced_data = enhanced_image(image)
                enhanced = extract_positioned_text(
                    engine(enhanced_data),
                    enhanced_data.shape,
                    args.min_score,
                    args.min_center_y,
                    args.max_center_x_offset,
                )
                chosen, source = choose_result(original, enhanced)
            text, score, detections = chosen
            entry = {
                "frame": position,
                "time": (position - 1) / args.sample_fps,
                "path": str(frame_path),
                "text": text,
                "score": score,
                "source": source,
                "detections": detections,
            }
            entries.append(entry)
            raw_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            raw_file.flush()
            if position % 25 == 0 or position == len(frame_paths):
                print(f"已处理 {position}/{len(frame_paths)} 帧", flush=True)

    records = segment_records(build_segments(entries), args.sample_fps, duration)
    write_candidates(records, args.run_dir)
    print(
        json.dumps(
            {
                "frames": len(frame_paths),
                "segments": len(records),
                "run_dir": str(args.run_dir),
                "candidate_srt": str(args.run_dir / "candidate.srt"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
