import cv2
import numpy as np
import math
from ultralytics import YOLO

# ---------- Config ----------
model = YOLO("../models/best_yolo26n.pt")
CLASSES = {0: 'bowling-ball', 1: 'bowling-pins', 2: 'sweep board', 3: 'car'}
PIN_CLASS = 1
CAR_CLASS = 3
ASPECT_UPRIGHT_MIN = 2.2  # h/w for standing pin
ASPECT_FALLEN_MAX = 0.6  # width must be > height
CONF_THRESH = 0.4
SHOW_VIDEO = False

# Fall Detection Tuning
FALL_CONFIRM_FRAMES = 5
# How far (in pixels) a fallen pin can roll/slide between frames and still keep its label
MATCH_RADIUS = 30
# -----------------------------

# Video I/O
cap = cv2.VideoCapture("../input_dataset/IMG_3794.mov")
fps = cap.get(cv2.CAP_PROP_FPS) or 30
frame_width = int(cap.get(3))
frame_height = int(cap.get(4))

# Output video writer (MP4)
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('../outputs/youssef_yolo_output.mp4', fourcc, fps, (frame_width, frame_height))

# --- New State Management ---
pin_states = {}  # Only used for debouncing standing pins now: {track_id: {'fall_frames': int}}
fallen_registry = []  # SPATIAL ANCHORS: [{'order': int, 'cx': float, 'cy': float}]
pin_fall_order = 0
car_path = []
start_time_sec = None

while True:
    ret, frame = cap.read()
    if not ret:
        break
    if start_time_sec is None:
        start_time_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

    # 1. Run YOLO with built-in Tracker
    results = model.track(frame, tracker="botsort.yaml", persist=True, conf=CONF_THRESH, verbose=False)
    current_frame_fallen = 0  # High Water Mark counter for this frame

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

                # --- 1. CHECK THE SPATIAL ANCHOR REGISTRY FIRST ---
                # Is this box sitting on top of a pin we ALREADY know fell down?
                matched_registry_pin = None
                min_dist = MATCH_RADIUS

                for f_pin in fallen_registry:
                    dist = math.hypot(cx - f_pin['cx'], cy - f_pin['cy'])
                    if dist < min_dist:
                        min_dist = dist
                        matched_registry_pin = f_pin

                if matched_registry_pin is not None:
                    # Success! This is an already-fallen pin.
                    # Update its center slightly in case it rolled
                    matched_registry_pin['cx'] = cx
                    matched_registry_pin['cy'] = cy

                    # Draw it Green and lock its label (ignoring the track_id completely)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"#{matched_registry_pin['order']}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

                    if aspect <= ASPECT_FALLEN_MAX:
                        current_frame_fallen += 1

                    continue  # Skip the rest of the logic for this specific pin!

                # --- 2. IF NOT IN REGISTRY, CHECK IF IT IS CURRENTLY FALLING ---
                if track_id not in pin_states:
                    pin_states[track_id] = {'fall_frames': 0}

                state = pin_states[track_id]

                if aspect <= ASPECT_FALLEN_MAX:
                    current_frame_fallen += 1
                    state['fall_frames'] += 1
                else:
                    state['fall_frames'] = max(0, state['fall_frames'] - 2)

                # Has it been horizontal long enough to make it official?
                if state['fall_frames'] >= FALL_CONFIRM_FRAMES:
                    pin_fall_order += 1

                    # Create a permanent spatial anchor for this pin!
                    fallen_registry.append({
                        'order': pin_fall_order,
                        'cx': cx,
                        'cy': cy
                    })

                    # Reset the debounce in case the ID is recycled
                    state['fall_frames'] = 0

                    # Draw immediately
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"#{pin_fall_order}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                else:
                    # Pin is still standing (Draw Red)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

            elif cls == CAR_CLASS:
                # --- Car path drawing ---
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                car_path.append((cx, cy))

    # Draw the accumulated car path
    for i in range(1, len(car_path)):
        cv2.line(frame, car_path[i - 1], car_path[i], (0, 255, 255), 2)

    # --- Live overlay (time & pins) ---
    # Safe fallback: The score is either the number of permanent anchors,
    # or the sheer number of horizontal pins YOLO sees right now.
    display_pins_down = max(len(fallen_registry), current_frame_fallen)

    elapsed = (cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 - start_time_sec) if start_time_sec else 0
    info_text = f"Time: {elapsed:.1f}s   Pins down: {display_pins_down}"
    cv2.rectangle(frame, (5, 5), (400, 40), (0, 0, 0), -1)
    cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (255, 255, 255), 2)

    # Write annotated frame to output video
    out.write(frame)
    if SHOW_VIDEO:
        cv2.imshow("Bowling RC App (Python)", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

# --- After recording: final summary screen (3 seconds) ---
if 'elapsed' not in locals():
    elapsed = (cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 - start_time_sec) if start_time_sec else 0

final_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
final_text_lines = [
    "Run Complete!",
    f"Total Time: {elapsed:.1f}s",
    f"Pins Knocked Down: {max(len(fallen_registry), current_frame_fallen)}",
    f"Car Path Length: {len(car_path)} points"
]
y0 = frame_height // 3
for i, line in enumerate(final_text_lines):
    cv2.putText(final_frame, line, (50, y0 + i * 50),
                cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)

for _ in range(int(fps * 3)):
    out.write(final_frame)

# Clean up
cap.release()
out.release()
cv2.destroyAllWindows()

print(f"Final: {max(len(fallen_registry), current_frame_fallen)} pins in {elapsed:.1f}s")
print("Annotated video saved as 'annotated_output.mp4'")