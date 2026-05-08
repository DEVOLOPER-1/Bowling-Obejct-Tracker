from pathlib import Path
import ultralytics
from ultralytics import YOLO

ultralytics.checks()

# absolute path resolution
ROOT = Path("data/processed/data.yaml").resolve()

print("Using dataset:", ROOT)

model = YOLO("yolo26n.pt")

results = model.train(
    data=str(ROOT),
    epochs=100,
    imgsz=640,
    batch=16,
    freeze=10,
    dropout=0.2,
    project="bowling_tracker",
    name="v3_yolo26_dropout",
    device=0,
    optimizer="auto",
    lr0=0.01,
)

print(results)
