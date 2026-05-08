"""
Wrapper module for youssef_yolo pipeline that exposes a clean run_pipeline interface.
This allows the Flask server to call the pipeline without directly importing the main script.
"""

import cv2
import numpy as np
import math
import os
from pathlib import Path
from ultralytics import YOLO

# Pipeline configuration constants
CLASSES = {0: 'bowling-ball', 1: 'bowling-pins', 2: 'sweep board', 3: 'car'}
PIN_CLASS = 1
CAR_CLASS = 3
ASPECT_UPRIGHT_MIN = 2.2
ASPECT_FALLEN_MAX = 0.6
CONF_THRESH = 0.4
SHOW_VIDEO = False

FALL_CONFIRM_FRAMES = 5
MATCH_RADIUS = 30


def run_pipeline(input_path: str) -> dict:
    return os.execv("/usr/bin/python3", ["python3", "youssef_yolo.py", "--input_video", input_path])

    return result

