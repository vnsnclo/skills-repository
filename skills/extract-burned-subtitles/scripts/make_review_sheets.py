#!/usr/bin/env python3
"""为每个候选字幕段生成带编号的中间帧总览图。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="生成字幕逐条复核总览图")
    parser.add_argument("--segments", type=Path, required=True, help="segments.json")
    parser.add_argument("--frames", type=Path, required=True, help="抽帧目录")
    parser.add_argument("--output-dir", type=Path, required=True, help="总览图输出目录")
    parser.add_argument("--columns", type=int, default=2)
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--tile-width", type=int, default=960)
    parser.add_argument("--tile-height", type=int, default=258)
    args = parser.parse_args()

    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise SystemExit(f"缺少 OpenCV 或 NumPy：{error}") from error

    if not args.segments.is_file():
        raise SystemExit(f"分段文件不存在：{args.segments}")
    if not args.frames.is_dir():
        raise SystemExit(f"帧目录不存在：{args.frames}")
    if args.columns < 1 or args.rows < 1 or args.tile_width < 100 or args.tile_height < 100:
        raise SystemExit("总览图布局参数无效。")

    records = json.loads(args.segments.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    existing = list(args.output_dir.glob("review_sheet_*.jpg"))
    if existing:
        raise SystemExit(f"输出目录已有 review_sheet_*.jpg，拒绝覆盖：{args.output_dir}")

    per_sheet = args.columns * args.rows
    written: list[str] = []
    for sheet_index in range(math.ceil(len(records) / per_sheet)):
        sheet = np.zeros(
            (args.rows * args.tile_height, args.columns * args.tile_width, 3),
            dtype=np.uint8,
        )
        subset = records[sheet_index * per_sheet : (sheet_index + 1) * per_sheet]
        for position, record in enumerate(subset):
            frame_number = (int(record["first_frame"]) + int(record["last_frame"])) // 2
            frame_path = args.frames / f"frame_{frame_number:06d}.jpg"
            image = cv2.imread(str(frame_path))
            if image is None:
                raise SystemExit(f"无法读取帧：{frame_path}")
            image = cv2.resize(
                image,
                (args.tile_width, args.tile_height),
                interpolation=cv2.INTER_AREA,
            )
            cv2.rectangle(image, (0, 0), (115, 44), (0, 0, 0), -1)
            cv2.putText(
                image,
                f"#{record['index']}",
                (10, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            row, column = divmod(position, args.columns)
            y0 = row * args.tile_height
            x0 = column * args.tile_width
            sheet[y0 : y0 + args.tile_height, x0 : x0 + args.tile_width] = image

        output_path = args.output_dir / f"review_sheet_{sheet_index + 1:02d}.jpg"
        if not cv2.imwrite(str(output_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 94]):
            raise SystemExit(f"无法写出总览图：{output_path}")
        written.append(str(output_path))

    print(json.dumps({"segments": len(records), "sheets": written}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
