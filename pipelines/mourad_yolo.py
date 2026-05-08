import cv2
import numpy as np
from ultralytics import YOLO
import argparse
import json

# 1. Factory-Standard Arguments (Maintains Wrapper Compatibility)
parser = argparse.ArgumentParser()
parser.add_argument("--input_video", type=str, required=True)
parser.add_argument("--output_video", type=str, required=True)
args = parser.parse_args()

# 2. Model Configuration
# Classes: 0: fallen_pin, 1: rc_car, 2: standing_pin
model = YOLO("./models/mourad_best_yolo26n.pt")
FALLEN_CLASS = 0
CAR_CLASS = 1
STANDING_CLASS = 2
CONF_THRESH = 0.6
SHOW_VIDEO = False

cap = cv2.VideoCapture(args.input_video)
fps = cap.get(cv2.CAP_PROP_FPS) or 30
frame_width = int(cap.get(3))
frame_height = int(cap.get(4))

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(args.output_video, fourcc, fps, (frame_width, frame_height))

# Tracking state
car_path = []
start_time_sec = None
total_fallen_detected = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    if start_time_sec is None:
        start_time_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

    # Using persist=True to keep track of objects across frames
    results = model.track(
        frame, tracker="botsort.yaml", persist=True, conf=CONF_THRESH, verbose=False
    )
    
    current_frame_fallen = 0

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        clss = results[0].boxes.cls.cpu().numpy().astype(int)

        for box, cls in zip(boxes, clss):
            x1, y1, x2, y2 = map(int, box)

            if cls == FALLEN_CLASS:
                current_frame_fallen += 1
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, "FALLEN", (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            elif cls == STANDING_CLASS:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, "STANDING", (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            elif cls == CAR_CLASS:
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                car_path.append((cx, cy))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

    # Visualization: Draw car path
    for i in range(1, len(car_path)):
        cv2.line(frame, car_path[i - 1], car_path[i], (0, 255, 255), 2)

    # We track the maximum number of fallen pins seen at once to represent the score
    total_fallen_detected = max(total_fallen_detected, current_frame_fallen)

    # HUD
    elapsed = (cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 - start_time_sec) if start_time_sec else 0
    info_text = f"Time: {elapsed:.1f}s | Pins Down: {total_fallen_detected}"
    cv2.rectangle(frame, (5, 5), (420, 40), (0, 0, 0), -1)
    cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    out.write(frame)

# Final Summary Card (3 seconds)
final_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
summary_lines = [
    "Run Complete (Classified)",
    f"Total Time: {elapsed:.1f}s",
    f"Fallen Pins (Max Count): {total_fallen_detected}",
    f"Car Trajectory: {len(car_path)} pts"
]

for i, line in enumerate(summary_lines):
    cv2.putText(final_frame, line, (50, (frame_height//3) + i*60), 
                cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)

for _ in range(int(fps * 3)):
    out.write(final_frame)

cap.release()
out.release()

# 3. Data Output (Strictly matches the Wrapper's expected format)
output_dict = {
    "pins": int(total_fallen_detected),
    "elapsed_s": round(float(elapsed), 2),
    "car_path_len": len(car_path),
}

print(f"\nRESULT_JSON: {json.dumps(output_dict)}")
