import cv2
import numpy as np
import math
from ultralytics import YOLO
import argparse
import json

# 1. Factory-Standard Arguments
parser = argparse.ArgumentParser()
parser.add_argument("--input_video", type=str, required=True)
parser.add_argument("--output_video", type=str, required=True)
args = parser.parse_args()
#################################################

model = YOLO("./models/best_yolo26n.pt")
CLASSES = {0: "bowling-ball", 1: "bowling-pins", 2: "sweep board", 3: "car"}
PIN_CLASS = 1
CAR_CLASS = 3
ASPECT_UPRIGHT_MIN = 2.2
ASPECT_FALLEN_MAX = 0.6
CONF_THRESH = 0.4
SHOW_VIDEO = False

FALL_CONFIRM_FRAMES = 5
MATCH_RADIUS = 30

cap = cv2.VideoCapture(f"{args.input_video}")
fps = cap.get(cv2.CAP_PROP_FPS) or 30
frame_width = int(cap.get(3))
frame_height = int(cap.get(4))

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(args.output_video, fourcc, fps, (frame_width, frame_height))

pin_states = {}
fallen_registry = []
pin_fall_order = 0
car_path = []
start_time_sec = None

while True:
    ret, frame = cap.read()
    if not ret:
        break
    if start_time_sec is None:
        start_time_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

    results = model.track(
        frame, tracker="botsort.yaml", persist=True, conf=CONF_THRESH, verbose=False
    )
    current_frame_fallen = 0

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.cpu().numpy().astype(int)
        clss = results[0].boxes.cls.cpu().numpy().astype(int)

        for box, track_id, cls in zip(boxes, ids, clss):
            x1, y1, x2, y2 = map(int, box)

            if cls == PIN_CLASS:
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                w = x2 - x1
                h = y2 - y1
                aspect = h / w if w > 0 else 0

                matched_registry_pin = None
                min_dist = MATCH_RADIUS

                for f_pin in fallen_registry:
                    dist = math.hypot(cx - f_pin["cx"], cy - f_pin["cy"])
                    if dist < min_dist:
                        min_dist = dist
                        matched_registry_pin = f_pin

                if matched_registry_pin is not None:
                    matched_registry_pin["cx"] = cx
                    matched_registry_pin["cy"] = cy

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        frame,
                        f"#{matched_registry_pin['order']}",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.9,
                        (0, 255, 0),
                        2,
                    )

                    if aspect <= ASPECT_FALLEN_MAX:
                        current_frame_fallen += 1

                    continue

                if track_id not in pin_states:
                    pin_states[track_id] = {"fall_frames": 0}

                state = pin_states[track_id]

                if aspect <= ASPECT_FALLEN_MAX:
                    current_frame_fallen += 1
                    state["fall_frames"] += 1
                else:
                    state["fall_frames"] = max(0, state["fall_frames"] - 2)

                if state["fall_frames"] >= FALL_CONFIRM_FRAMES:
                    pin_fall_order += 1

                    fallen_registry.append(
                        {"order": pin_fall_order, "cx": cx, "cy": cy}
                    )

                    state["fall_frames"] = 0

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        frame,
                        f"#{pin_fall_order}",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.9,
                        (0, 255, 0),
                        2,
                    )
                else:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

            elif cls == CAR_CLASS:
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                car_path.append((cx, cy))

    for i in range(1, len(car_path)):
        cv2.line(frame, car_path[i - 1], car_path[i], (0, 255, 255), 2)

    display_pins_down = max(len(fallen_registry), current_frame_fallen)

    elapsed = (
        (cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 - start_time_sec)
        if start_time_sec
        else 0
    )
    info_text = f"Time: {elapsed:.1f}s   Pins down: {display_pins_down}"
    cv2.rectangle(frame, (5, 5), (400, 40), (0, 0, 0), -1)
    cv2.putText(
        frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2
    )

    out.write(frame)
    if SHOW_VIDEO:
        cv2.imshow("Bowling RC App (Python)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

if "elapsed" not in locals():
    elapsed = (
        (cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 - start_time_sec)
        if start_time_sec
        else 0
    )

final_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
final_text_lines = [
    "Run Complete!",
    f"Total Time: {elapsed:.1f}s",
    f"Pins Knocked Down: {max(len(fallen_registry), current_frame_fallen)}",
    f"Car Path Length: {len(car_path)} points",
]
y0 = frame_height // 3
for i, line in enumerate(final_text_lines):
    cv2.putText(
        final_frame,
        line,
        (50, y0 + i * 50),
        cv2.FONT_HERSHEY_DUPLEX,
        1.2,
        (255, 255, 255),
        2,
    )

for _ in range(int(fps * 3)):
    out.write(final_frame)

cap.release()
out.release()
cv2.destroyAllWindows()


final_pins = max(len(fallen_registry), current_frame_fallen)

output_dict = {
    "pins": final_pins,
    "elapsed_s": float(elapsed) if "elapsed" in locals() else 0.0,
    "car_path_len": len(car_path),
}
################################
# Print the JSON payload to stdout so the Wrapper can catch it
print(f"\nRESULT_JSON: {json.dumps(output_dict)}")
