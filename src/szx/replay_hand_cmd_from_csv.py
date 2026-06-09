#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import sys
import time

import rospy
from sensor_msgs.msg import JointState


DEFAULT_TOPIC = "/cb_right_hand_control_cmd"


def is_float(value):
    try:
        float(value)
        return True
    except Exception:
        return False


def load_csv(csv_path):
    """
    支持两种 CSV 格式：

    1. 带时间戳格式：
       bag_time,header_time,time_from_start,seq,joint1,joint2,...,joint20

    2. 纯 position 格式：
       joint1,joint2,...,joint20

    返回：
       rows = [
           {
               "time_from_start": float or None,
               "positions": [float, ...]
           },
           ...
       ]
    """
    rows = []

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise RuntimeError("CSV 文件为空或没有 header")

        fieldnames = reader.fieldnames

        # 找 position 列
        ignore_columns = {
            "bag_time",
            "header_time",
            "time_from_start",
            "seq",
        }

        position_columns = [
            col for col in fieldnames
            if col not in ignore_columns
        ]

        if len(position_columns) == 0:
            raise RuntimeError("CSV 中没有找到 position 列，例如 joint1, joint2, ...")

        for line_idx, row in enumerate(reader, start=2):
            positions = []

            for col in position_columns:
                value = row[col]

                if value is None or value == "":
                    raise RuntimeError(f"第 {line_idx} 行 {col} 为空")

                if not is_float(value):
                    raise RuntimeError(f"第 {line_idx} 行 {col} 不是数字: {value}")

                positions.append(float(value))

            time_from_start = None
            if "time_from_start" in row:
                value = row["time_from_start"]
                if value not in (None, ""):
                    time_from_start = float(value)

            rows.append({
                "time_from_start": time_from_start,
                "positions": positions,
            })

    if len(rows) == 0:
        raise RuntimeError("CSV 没有有效数据行")

    return rows, position_columns


def make_joint_state_msg(joint_names, positions, velocity_value):
    msg = JointState()

    msg.header.stamp = rospy.Time.now()
    msg.header.frame_id = ""

    msg.name = list(joint_names)
    msg.position = list(positions)
    msg.velocity = [float(velocity_value)] * len(positions)
    msg.effort = []

    return msg


def replay_csv(
    csv_path,
    topic,
    rate_hz,
    use_csv_timing,
    loop,
    velocity_value,
    publish_countdown,
):
    rows, joint_names = load_csv(csv_path)

    rospy.loginfo("CSV loaded: %s", csv_path)
    rospy.loginfo("Rows: %d", len(rows))
    rospy.loginfo("Joints: %d", len(joint_names))
    rospy.loginfo("Topic: %s", topic)

    pub = rospy.Publisher(topic, JointState, queue_size=10)

    # 等待 publisher 注册，避免刚启动时第一帧丢失
    rospy.sleep(1.0)

    if publish_countdown:
        for i in range(3, 0, -1):
            rospy.loginfo("Start replay in %d...", i)
            rospy.sleep(1.0)

    rate = rospy.Rate(rate_hz)

    while not rospy.is_shutdown():
        start_wall_time = time.time()

        previous_t = None

        for idx, item in enumerate(rows):
            if rospy.is_shutdown():
                break

            positions = item["positions"]

            msg = make_joint_state_msg(
                joint_names=joint_names,
                positions=positions,
                velocity_value=velocity_value,
            )

            pub.publish(msg)

            if idx == 0:
                rospy.loginfo("First command published")
                rospy.loginfo("Position: %s", positions)

            # 优先按照 CSV 的 time_from_start 回放
            if use_csv_timing and item["time_from_start"] is not None:
                current_t = item["time_from_start"]

                if previous_t is None:
                    previous_t = current_t
                    continue

                dt = current_t - previous_t
                previous_t = current_t

                if dt > 0:
                    rospy.sleep(dt)
            else:
                rate.sleep()

        rospy.loginfo("Replay finished once. Duration: %.3f s", time.time() - start_wall_time)

        if not loop:
            break

    rospy.loginfo("Replay node exit")


def main():
    parser = argparse.ArgumentParser(
        description="Replay LinkerHand JointState position commands from CSV."
    )

    parser.add_argument(
        "csv",
        help="输入 CSV 文件，例如 cb_right_hand_control_cmd_position.csv",
    )

    parser.add_argument(
        "-t",
        "--topic",
        default=DEFAULT_TOPIC,
        help=f"发布 topic，默认: {DEFAULT_TOPIC}",
    )

    parser.add_argument(
        "-r",
        "--rate",
        type=float,
        default=50.0,
        help="当 CSV 没有 time_from_start 或不使用 CSV 时间戳时的发布频率，默认 50 Hz",
    )

    parser.add_argument(
        "--no-csv-timing",
        action="store_true",
        help="不使用 CSV 中的 time_from_start，改用 --rate 固定频率发布",
    )

    parser.add_argument(
        "--loop",
        action="store_true",
        help="循环回放 CSV",
    )

    parser.add_argument(
        "--velocity",
        type=float,
        default=255.0,
        help="JointState.velocity 填充值，默认 255.0",
    )

    parser.add_argument(
        "--no-countdown",
        action="store_true",
        help="启动后不进行 3 秒倒计时",
    )

    args = parser.parse_args()

    rospy.init_node("replay_hand_cmd_from_csv", anonymous=True)

    try:
        replay_csv(
            csv_path=args.csv,
            topic=args.topic,
            rate_hz=args.rate,
            use_csv_timing=not args.no_csv_timing,
            loop=args.loop,
            velocity_value=args.velocity,
            publish_countdown=not args.no_countdown,
        )
    except Exception as e:
        rospy.logerr("Replay failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
