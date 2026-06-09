#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import os


def read_csv(csv_path):
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise RuntimeError("CSV 文件为空，或者没有 header")

        rows = list(reader)
        fieldnames = reader.fieldnames

    if len(rows) == 0:
        raise RuntimeError("CSV 没有数据行")

    return fieldnames, rows


def reset_time_from_start(rows):
    """
    如果 CSV 中有 time_from_start，把每段动作的时间重新从 0 开始。
    """
    if not rows:
        return rows

    if "time_from_start" not in rows[0]:
        return rows

    first_t = float(rows[0]["time_from_start"])

    for row in rows:
        if row["time_from_start"] not in ("", None):
            row["time_from_start"] = str(float(row["time_from_start"]) - first_t)

    return rows


def write_csv(csv_path, fieldnames, rows):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def split_csv(input_csv, grasp_csv, release_csv, reset_time=True):
    fieldnames, rows = read_csv(input_csv)

    total = len(rows)
    mid = total // 2

    grasp_rows = rows[:mid]
    release_rows = rows[mid:]

    if reset_time:
        grasp_rows = reset_time_from_start(grasp_rows)
        release_rows = reset_time_from_start(release_rows)

    write_csv(grasp_csv, fieldnames, grasp_rows)
    write_csv(release_csv, fieldnames, release_rows)

    print("Split finished.")
    print(f"Input:   {input_csv}")
    print(f"Total:   {total} rows")
    print(f"Grasp:   {grasp_csv}, {len(grasp_rows)} rows")
    print(f"Release: {release_csv}, {len(release_rows)} rows")


def main():
    parser = argparse.ArgumentParser(
        description="Split hand command CSV into grasp and release halves."
    )

    parser.add_argument(
        "input_csv",
        help="输入 CSV，例如 cb_right_hand_control_cmd_position.csv",
    )

    parser.add_argument(
        "--grasp",
        default="grasp.csv",
        help="前半段输出文件，默认 grasp.csv",
    )

    parser.add_argument(
        "--release",
        default="release.csv",
        help="后半段输出文件，默认 release.csv",
    )

    parser.add_argument(
        "--keep-time",
        action="store_true",
        help="不重置 time_from_start，保留原始时间",
    )

    args = parser.parse_args()

    split_csv(
        input_csv=args.input_csv,
        grasp_csv=args.grasp,
        release_csv=args.release,
        reset_time=not args.keep_time,
    )


if __name__ == "__main__":
    main()
