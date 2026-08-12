#!/usr/bin/env python3
"""应用人工修订并导出最终 SRT、TXT 和结构化分段。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PUNCTUATION_TRANSLATION = str.maketrans(
    {",": "，", "?": "？", ":": "：", ";": "；", "!": "！"}
)


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def refuse_existing(paths: list[Path], force: bool) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing and not force:
        raise SystemExit("以下输出已存在，拒绝覆盖：\n" + "\n".join(existing))


def main() -> None:
    parser = argparse.ArgumentParser(description="应用 corrections.json 并导出最终字幕")
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--corrections", type=Path, required=True)
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--txt", type=Path, required=True)
    parser.add_argument("--json", type=Path, help="可选的最终结构化记录")
    parser.add_argument("--video-duration", type=float, help="视频总时长（秒）")
    parser.add_argument("--force", action="store_true", help="允许覆盖已有输出；使用前应取得授权")
    args = parser.parse_args()

    if not args.segments.is_file():
        raise SystemExit(f"分段文件不存在：{args.segments}")
    if not args.corrections.is_file():
        raise SystemExit(f"修订文件不存在：{args.corrections}")

    output_paths = [args.srt, args.txt] + ([args.json] if args.json else [])
    refuse_existing(output_paths, args.force)

    records = json.loads(args.segments.read_text(encoding="utf-8"))
    corrections = json.loads(args.corrections.read_text(encoding="utf-8"))
    text_overrides = {int(key): value for key, value in corrections.get("text_overrides", {}).items()}
    time_overrides = {int(key): value for key, value in corrections.get("time_overrides", {}).items()}
    drop_indices = {int(value) for value in corrections.get("drop_indices", [])}
    normalize_punctuation = bool(corrections.get("normalize_chinese_punctuation", False))

    final_records: list[dict] = []
    for source in records:
        source_index = int(source["index"])
        if source_index in drop_indices:
            continue
        record = dict(source)
        record["source_index"] = source_index
        record["text"] = str(text_overrides.get(source_index, record["text"]))
        if normalize_punctuation:
            record["text"] = record["text"].translate(PUNCTUATION_TRANSLATION)
        if source_index in time_overrides:
            override = time_overrides[source_index]
            if "start" in override:
                record["start"] = float(override["start"])
            if "end" in override:
                record["end"] = float(override["end"])
        final_records.append(record)

    if not final_records:
        raise SystemExit("修订后没有任何字幕段。")
    if corrections.get("extend_last_to_video_end", False):
        if args.video_duration is None:
            raise SystemExit("extend_last_to_video_end=true 时必须提供 --video-duration。")
        final_records[-1]["end"] = args.video_duration

    for position, record in enumerate(final_records):
        record["index"] = position + 1
        text = str(record["text"]).strip()
        if not text:
            raise SystemExit(f"第 {position + 1} 条字幕为空。")
        record["text"] = text
        start = float(record["start"])
        end = float(record["end"])
        if not 0 <= start < end:
            raise SystemExit(f"第 {position + 1} 条时间范围无效：{start} - {end}")
        if args.video_duration is not None and end > args.video_duration + 0.0005:
            raise SystemExit(f"第 {position + 1} 条超过视频时长。")
        if position and start < float(final_records[position - 1]["end"]):
            raise SystemExit(f"第 {position} 与第 {position + 1} 条时间重叠。")

    srt_blocks = [
        f"{record['index']}\n{srt_time(float(record['start']))} --> {srt_time(float(record['end']))}\n{record['text']}"
        for record in final_records
    ]
    txt_lines = [str(record["text"]).replace("\n", " ") for record in final_records]

    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    args.srt.write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")
    args.txt.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(final_records, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "cues": len(final_records),
                "srt": str(args.srt),
                "txt": str(args.txt),
                "json": str(args.json) if args.json else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
