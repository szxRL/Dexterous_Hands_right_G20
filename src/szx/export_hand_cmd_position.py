#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import os
import re
import sys

import rosbag


DEFAULT_TOPIC = "/cb_right_hand_control_cmd"


def sanitize_column_name(name: str, fallback: str) -> str:
    """
    把 joint 名称转换成适合 CSV header 的列名。
    """
    if not name:
        return fallback

    name = str(name).strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^0-9a-zA-Z_]", "_", name)

    return name if name else fallback


def make_unique(names):
    """
    避免 CSV header 里出现重复列名。
    """
    used = {}
    result = []

    for name in names:
        if name not in used:
            used[name] = 0
            result.append(name)
        else:
            used[name] += 1
            result.append(f"{name}_{used[name]}")

    return result


def ros_time_to_sec(stamp):
    """
    兼容 genpy.Time / rospy.Time。
    """
    if stamp is None:
        return None

    if hasattr(stamp, "to_sec"):
        return float(stamp.to_sec())

    secs = getattr(stamp, "secs", 0)
    nsecs = getattr(stamp, "nsecs", 0)
    return float(secs) + float(nsecs) * 1e-9


def get_msg_header_time(msg, bag_time):
    """
    优先使用 msg.header.stamp；如果没有 header，则使用 rosbag 记录时间。
    """
    if hasattr(msg, "header") and hasattr(msg.header, "stamp"):
        stamp_sec = ros_time_to_sec(msg.header.stamp)
        if stamp_sec is not None and stamp_sec > 0:
            return stamp_sec

    return ros_time_to_sec(bag_time)


def export_position_to_csv(
    bag_path: str,
    csv_path: str,
    topic: str,
    positions_only: bool = False,
):
    if not os.path.exists(bag_path):
        raise FileNotFoundError(f"rosbag 文件不存在: {bag_path}")

    msg_count = 0
    first_time = None
    writer = None
    csv_file = None

    try:
        with rosbag.Bag(bag_path, "r") as bag:
            topic_info = bag.get_type_and_topic_info().topics

            if topic not in topic_info:
                available_topics = "\n".join(sorted(topic_info.keys()))
                raise RuntimeError(
                    f"rosbag 中找不到话题: {topic}\n\n"
                    f"可用 topics:\n{available_topics}"
                )

            for _, msg, bag_time in bag.read_messages(topics=[topic]):
                if not hasattr(msg, "position"):
                    raise RuntimeError(
                        f"话题 {topic} 的消息没有 position 字段，"
                        f"实际消息类型可能不是 sensor_msgs/JointState。"
                    )

                positions = list(msg.position)
                msg_time = get_msg_header_time(msg, bag_time)

                if first_time is None:
                    first_time = msg_time

                    # 优先用 msg.name 作为列名；如果 name 为空或长度不匹配，则用 joint1..jointN。
                    msg_names = list(getattr(msg, "name", []))
                    if len(msg_names) == len(positions) and len(msg_names) > 0:
                        position_columns = [
                            sanitize_column_name(n, f"joint{i + 1}")
                            for i, n in enumerate(msg_names)
                        ]
                    else:
                        position_columns = [
                            f"joint{i + 1}" for i in range(len(positions))
                        ]

                    position_columns = make_unique(position_columns)

                    csv_file = open(csv_path, "w", newline="", encoding="utf-8")
                    writer = csv.writer(csv_file)

                    if positions_only:
                        header = position_columns
                    else:
                        header = [
                            "bag_time",
                            "header_time",
                            "time_from_start",
                            "seq",
                        ] + position_columns

                    writer.writerow(header)

                if len(positions) != len(position_columns):
                    raise RuntimeError(
                        f"第 {msg_count + 1} 条消息的 position 长度变化："
                        f"当前 {len(positions)}，首条消息 {len(position_columns)}。"
                        f"建议检查 rosbag 是否混入了不同型号/不同维度的数据。"
                    )

                seq = ""
                if hasattr(msg, "header") and hasattr(msg.header, "seq"):
                    seq = msg.header.seq

                if positions_only:
                    row = positions
                else:
                    row = [
                        ros_time_to_sec(bag_time),
                        msg_time,
                        msg_time - first_time,
                        seq,
                    ] + positions

                writer.writerow(row)
                msg_count += 1

    finally:
        if csv_file is not None:
            csv_file.close()

    print(f"导出完成: {csv_path}")
    print(f"topic: {topic}")
    print(f"messages: {msg_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Export LinkerHand JointState.position from ROS1 rosbag to CSV."
    )
    parser.add_argument(
        "bag",
        help="输入 rosbag 文件路径，例如 data.bag",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="cb_right_hand_control_cmd_position.csv",
        help="输出 CSV 文件路径",
    )
    parser.add_argument(
        "-t",
        "--topic",
        default=DEFAULT_TOPIC,
        help=f"要导出的 topic，默认: {DEFAULT_TOPIC}",
    )
    parser.add_argument(
        "--positions-only",
        action="store_true",
        help="只保存 position 列，不保存时间戳/seq。若后续要按原节奏回放，不建议开启。",
    )

    args = parser.parse_args()

    try:
        export_position_to_csv(
            bag_path=args.bag,
            csv_path=args.output,
            topic=args.topic,
            positions_only=args.positions_only,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
