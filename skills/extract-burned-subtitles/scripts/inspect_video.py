#!/usr/bin/env python3
"""只读探测视频流，判断是否存在可直接导出的字幕轨。"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="探测视频格式、时长和音视频/字幕流")
    parser.add_argument("video", type=Path, help="输入视频路径")
    args = parser.parse_args()

    if not args.video.is_file():
        raise SystemExit(f"视频不存在：{args.video}")
    if shutil.which("ffprobe") is None:
        raise SystemExit("找不到 ffprobe；请先安装 FFmpeg。")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=format_name,duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate:stream_tags=language,title",
        "-of",
        "json",
        str(args.video),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffprobe 失败：{result.stderr.strip()}")

    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    subtitle_streams = [stream for stream in streams if stream.get("codec_type") == "subtitle"]
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    output = {
        "path": str(args.video.resolve()),
        "has_subtitle_stream": bool(subtitle_streams),
        "subtitle_streams": subtitle_streams,
        "video_streams": video_streams,
        "audio_streams": audio_streams,
        "format": payload.get("format", {}),
        "recommended_route": "direct_export" if subtitle_streams else "visual_ocr",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
