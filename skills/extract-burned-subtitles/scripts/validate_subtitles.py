#!/usr/bin/env python3
"""独立验证 SRT 编号、时间轴、UTF-8 和对应 TXT。"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


TIME_PATTERN = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$")


def parse_time(value: str) -> int:
    match = TIME_PATTERN.match(value)
    if not match:
        raise ValueError(f"时间格式无效：{value}")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"时间值无效：{value}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def main() -> None:
    parser = argparse.ArgumentParser(description="验证 SRT/TXT 字幕")
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--txt", type=Path)
    parser.add_argument("--duration", type=float, help="视频时长（秒）")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    if not args.srt.is_file():
        raise SystemExit(f"SRT 不存在：{args.srt}")
    try:
        srt_text = args.srt.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise SystemExit(f"SRT 不是有效 UTF-8：{error}") from error

    blocks = re.split(r"\n\s*\n", srt_text.strip()) if srt_text.strip() else []
    ranges: list[tuple[int, int]] = []
    for expected, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        if len(lines) < 3:
            errors.append(f"第 {expected} 个区块不足三行。")
            continue
        if lines[0].strip() != str(expected):
            errors.append(f"第 {expected} 个区块编号为 {lines[0]!r}。")
        if " --> " not in lines[1]:
            errors.append(f"第 {expected} 个区块缺少标准时间箭头。")
            continue
        start_text, end_text = lines[1].split(" --> ", 1)
        try:
            start = parse_time(start_text)
            end = parse_time(end_text)
        except ValueError as error:
            errors.append(f"第 {expected} 个区块：{error}")
            continue
        if start >= end:
            errors.append(f"第 {expected} 条起点不早于终点。")
        if ranges and start < ranges[-1][1]:
            errors.append(f"第 {expected - 1} 与第 {expected} 条重叠。")
        if args.duration is not None and end > round(args.duration * 1000) + 1:
            errors.append(f"第 {expected} 条超过视频时长。")
        if not "\n".join(lines[2:]).strip():
            errors.append(f"第 {expected} 条文本为空。")
        ranges.append((start, end))

    txt_lines = None
    if args.txt:
        if not args.txt.is_file():
            errors.append(f"TXT 不存在：{args.txt}")
        else:
            try:
                txt_lines = args.txt.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError as error:
                errors.append(f"TXT 不是有效 UTF-8：{error}")
            if txt_lines is not None and len(txt_lines) != len(blocks):
                errors.append(f"TXT 行数 {len(txt_lines)} 与 SRT 条目数 {len(blocks)} 不一致。")

    ffprobe_codec = None
    if shutil.which("ffprobe"):
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,codec_type",
                "-of",
                "json",
                str(args.srt),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            streams = json.loads(result.stdout).get("streams", [])
            if streams:
                ffprobe_codec = streams[0].get("codec_name")
            if ffprobe_codec != "subrip":
                errors.append(f"ffprobe 未识别为 subrip：{ffprobe_codec}")
        else:
            errors.append(f"ffprobe 无法解析 SRT：{result.stderr.strip()}")
    else:
        warnings.append("未安装 ffprobe，跳过 SubRip 解析验证。")

    report = {
        "valid": not errors,
        "cues": len(blocks),
        "txt_lines": len(txt_lines) if txt_lines is not None else None,
        "first_ms": ranges[0][0] if ranges else None,
        "last_ms": ranges[-1][1] if ranges else None,
        "ffprobe_codec": ffprobe_codec,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
