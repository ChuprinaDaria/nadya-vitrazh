# Stained Glass Pavilion — Technical Overview

## Project Summary

An interactive art installation where stained glass fragments rotate on spindles (motors). When a visitor approaches, the pieces stop and assemble into a complete image. If the visitor takes a photo or looks at their phone, the glass resumes spinning — the artwork "refuses" to be captured.

---

## System Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐
│   Camera     │────▶│  Person Detector  │────▶│  Pose Classifier   │
│  (OpenCV)    │     │  (YOLOv8n)       │     │  (MediaPipe Pose)  │
└─────────────┘     └──────────────────┘     └───────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  State Machine   │
                                              │                  │
                                              │  ROTATING        │
                                              │  ASSEMBLING      │
                                              │  ASSEMBLED       │
                                              │  DISASSEMBLING   │
                                              └─────────────────┘
                                                       │
                                           ┌───────────┼───────────┐
                                           ▼                       ▼
                                  ┌─────────────────┐    ┌──────────────────┐
                                  │ Motor Controller │    │    Dashboard      │
                                  │ (GPIO / Serial)  │    │ (FastAPI + WS)   │
                                  └─────────────────┘    └──────────────────┘
```

---

## Detection Pipeline

### Step 1: Camera Input

**Library:** OpenCV (`cv2.VideoCapture`)
**File:** `vitrazh/camera/opencv_source.py`

Supports three source types:
- **USB webcam** — index `0`, `1`, etc.
- **Video file** — path to `.mp4`, `.avi`
- **RTSP stream** — `rtsp://ip:port/path` for IP cameras

Features:
- FPS limiting (default 15 fps — sufficient for detection, saves CPU)
- Automatic reconnection with exponential backoff for RTSP streams
- Protocol-based interface (`CameraSource`) — any camera backend can be swapped in

**Origin:** Ported from [korview-ai](https://github.com/ferusnet/korview-ai) (perimeter security project), simplified for single-camera use.

---

### Step 2: Person Detection

**Library:** Ultralytics YOLOv8 (`ultralytics` package)
**Model:** `yolov8n.pt` (YOLOv8 Nano — 6.3 MB, ~45 FPS on CPU, ~200 FPS on GPU)
**File:** `vitrazh/detection/person_detector.py`

How it works:
1. Each frame is passed to `YOLO.track()` with ByteTrack multi-object tracking
2. Only class 0 (person) is detected — all other COCO classes are filtered out
3. Bounding boxes are normalized to `[0, 1]` range
4. Each detected person gets a `tracking_id` for continuity across frames

Output: `list[Detection]` with `bbox`, `confidence`, `tracking_id`

Why YOLOv8n:
- Pre-trained on COCO (80 classes), person detection works out of the box
- Nano variant is fast enough for real-time on Raspberry Pi 4/5
- No custom training needed
- ByteTrack provides stable tracking IDs across frames

**Origin:** Ported from [korview-ai](https://github.com/ferusnet/korview-ai), restricted to person-only detection.

---

### Step 3: Pose Classification

**Library:** MediaPipe Pose Landmarker (`mediapipe` package)
**Model:** `pose_landmarker_lite.task` (~200 KB, auto-downloaded on first run)
**File:** `vitrazh/detection/pose_classifier.py`

How it works:
1. MediaPipe detects 33 body landmarks (shoulders, elbows, wrists, hips, knees, etc.)
2. Each landmark has `(x, y, z, visibility)` coordinates
3. A rule-based classifier analyzes landmark geometry to determine pose

**Pose categories:**

| Pose | Detection Logic | Meaning |
|------|----------------|---------|
| `IDLE` | Default — person standing normally | Glass stays assembled |
| `PHOTOGRAPHING` | Arms raised, elbows bent (30°–150°), wrists near face level | Person is taking a photo → glass resumes spinning |
| `PHONE_VIEWING` | Wrist very close to nose (< 0.15 normalized distance) | Person looking at phone screen → glass resumes spinning |

Key geometric checks:
- **Elbow angle:** `angle(shoulder, elbow, wrist)` — bent arm indicates holding a device
- **Wrist-to-nose distance:** close proximity suggests phone held to face
- **Wrist elevation:** wrists above elbows = raised arms (photo pose)
- **Wrist at face level:** `abs(wrist.y - nose.y) < 0.15` = camera/phone at eye height

All thresholds are configurable via `config.yaml` → `classifier` section.

**Origin:** Pose detection pattern from [exercises-counter](https://github.com/ChuprinaDaria/exercises-counter) (MediaPipe backend + Landmark dataclass). Classification logic is new — custom for this project.

---

### Step 4: State Machine

**File:** `vitrazh/state_machine.py`

```
                    person present
                    for N seconds
    ROTATING ─────────────────────▶ ASSEMBLING ──▶ ASSEMBLED
       ▲                                              │
       │                              person leaves   │
       │                              for N seconds   │
       │◀─── DISASSEMBLING ◀──────────────────────────┤
       │                              OR               │
       │                              photo/phone pose │
       │                              for N seconds    │
       └──────────────────────────────────────────────┘
```

Timing parameters (all configurable):
- `presence_delay: 2.0s` — person must stand for 2 seconds before glass assembles
- `absence_delay: 3.0s` — person must be gone for 3 seconds before glass starts rotating
- `photo_resume_delay: 1.5s` — photo pose must be held for 1.5 seconds to trigger rotation

The delays prevent jitter from momentary detection glitches.

---

### Step 5: Motor Control

**File:** `vitrazh/motor/base.py` (Protocol), `vitrazh/motor/mock.py` (Mock)

The motor controller receives state commands:
- `ROTATING` → all motors spin at their configured speeds
- `ASSEMBLING` → motors decelerate and align to home position
- `ASSEMBLED` → motors hold position
- `DISASSEMBLING` → motors accelerate back to spinning

Protocol-based interface — implementations:
- `MockMotorController` — logs state changes, no hardware (for development/demo)
- `GpioMotorController` — (to be implemented) controls stepper/servo motors via Raspberry Pi GPIO
- `SerialMotorController` — (to be implemented) sends commands to Arduino via serial port

---

### Step 6: Dashboard

**Files:** `vitrazh/dashboard/server.py`, `vitrazh/dashboard/static/index.html`
**Stack:** FastAPI + WebSocket + Tailwind CSS

Features:
- **Real-time state display** via WebSocket — state, pose, person presence
- **Stained glass visualization** — 6 SVG pieces with individual rotation animations
- **Pavilion plans** — 4 tabs (cameras with dimensions, pavilion with dimensions, clean variants)
- **Lightbox zoom** — click any plan to view full-size
- **Mode indicator** — PROTOTYPE (purple badge) / PRODUCTION (green badge)
- **Event log** — timestamped state transitions

---

## What Is Reused From Existing Projects

| Component | Source Repository | What Was Taken |
|-----------|------------------|----------------|
| Camera abstraction | [korview-ai](https://github.com/ferusnet/korview-ai) | `OpenCVSource` class — RTSP/file/webcam with reconnect |
| Person detection | [korview-ai](https://github.com/ferusnet/korview-ai) | `YoloDetector` → simplified to `PersonDetector` (person-only) |
| Pydantic config pattern | [korview-ai](https://github.com/ferusnet/korview-ai) | Nested config models with YAML loading |
| Pose detection backend | [exercises-counter](https://github.com/ChuprinaDaria/exercises-counter) | `MediaPipeBackend` + `Landmark` dataclass + model auto-download |
| Protocol-based design | Both repos | `CameraSource`, `PoseDetector`, `MotorController` protocols |
| FastAPI + WebSocket dashboard | [korview-ai](https://github.com/ferusnet/korview-ai) | Dashboard structure, WebSocket broadcast pattern |

**New code (not from existing repos):**
- Pose classifier (rule-based: photographing / phone_viewing / idle)
- State machine (ROTATING ↔ ASSEMBLED with timing)
- Motor control protocol and mock
- Stained glass SVG animation
- Demo simulation mode

---

## Prototype vs Production

### Prototype (Desktop Demo)

**Purpose:** Show the concept to Nadiia and stakeholders on a laptop.

| What | How |
|------|-----|
| Camera | Laptop webcam (`--source 0`) or pre-recorded video file |
| Person detection | YOLOv8n on CPU — works real-time on any modern laptop |
| Pose classification | MediaPipe Pose — lightweight, CPU-only |
| Motors | `MockMotorController` — logs to console, SVG animation in dashboard |
| Dashboard | `http://localhost:8080` — full UI with plans, animation, logs |
| Hardware needed | Just a laptop with a webcam |

**Quick start (no ML dependencies):**
```bash
python scripts/demo_dashboard.py --port 8080
```
This runs a simulation that cycles through states automatically — no camera or ML models needed.

**Full prototype (with real camera detection):**
```bash
pip install -e ".[web]"
python -m vitrazh --dashboard --source 0
```

### Production (Real Installation)

**Purpose:** Deployed in the physical pavilion with real motors and cameras.

| What | How |
|------|-----|
| Camera | IP camera via RTSP (`rtsp://192.168.x.x:554/stream`) |
| Compute | Raspberry Pi 5 (4GB+) or mini PC |
| Person detection | YOLOv8n — runs at ~15 FPS on RPi 5 with USB accelerator |
| Pose classification | MediaPipe Pose — runs on RPi 5 CPU |
| Motors | 6 stepper/servo motors via GPIO (RPi) or Arduino (serial) |
| Dashboard | Accessible on local network for monitoring |
| Power | 5V for RPi, 12V/24V for motors (separate PSU) |

**What needs to be built for production:**

1. **Motor controller implementation** (`vitrazh/motor/gpio.py`)
   - RPi.GPIO or pigpio for stepper motor control
   - PWM signals for speed control
   - Home position calibration routine

2. **Motor controller alternative** (`vitrazh/motor/serial_motor.py`)
   - Serial communication with Arduino
   - Arduino firmware for motor driving (separate repo)

3. **Camera calibration**
   - Mount position, FOV coverage of the pavilion area
   - Detection zone configuration (which area of the frame to monitor)

4. **Startup service**
   - systemd unit file for auto-start on boot
   - Watchdog for crash recovery

5. **Networking**
   - Static IP for RPi on pavilion network
   - Dashboard accessible via local WiFi for monitoring

---

## Hardware Requirements

### Prototype
- Any laptop with webcam
- Python 3.11+
- ~2 GB disk (for YOLO model + MediaPipe + dependencies)

### Production
- Raspberry Pi 5 (4GB RAM minimum, 8GB recommended)
- USB camera or IP camera with RTSP
- 6x stepper motors (NEMA 17 or similar) with drivers (A4988 / TMC2209)
- Motor driver board or Arduino Mega for motor control
- 12V/24V power supply for motors
- 5V/3A power supply for RPi
- Ethernet or WiFi connectivity

### Pavilion Specifications (from Nadiia's plans)
- 4 PDF plans provided: camera placement, pavilion layout (both with and without dimensions)
- 6 stained glass positions, each with ~63 individual pieces (PDF files for laser cutting)
- Reference photos for pose detection (person with phone, photographing poses)

---

## File Structure

```
nadya-vitrazh/
├── config/
│   └── config_example.yaml      # All configurable parameters
├── docs/
│   ├── concept.md               # Project concept (Ukrainian)
│   └── technical_overview.md    # This document
├── materials/                   # Nadiia's materials (not in git)
│   └── .gitkeep
├── scripts/
│   ├── convert_plans.py         # PDF → PNG converter for dashboard
│   └── demo_dashboard.py        # Standalone demo (no ML deps)
├── tests/
│   ├── test_motor_mock.py
│   └── test_state_machine.py
├── vitrazh/
│   ├── __main__.py              # CLI entry point
│   ├── models.py                # Pydantic models + enums
│   ├── pipeline.py              # Main pipeline: camera → detection → pose → state → motors
│   ├── state_machine.py         # ROTATING ↔ ASSEMBLED logic
│   ├── camera/
│   │   ├── base.py              # CameraSource protocol
│   │   └── opencv_source.py     # OpenCV implementation
│   ├── detection/
│   │   ├── person_detector.py   # YOLOv8 person detection
│   │   └── pose_classifier.py   # MediaPipe pose → photographing/phone/idle
│   ├── motor/
│   │   ├── base.py              # MotorController protocol
│   │   └── mock.py              # Mock for development
│   └── dashboard/
│       ├── server.py            # FastAPI + WebSocket server
│       └── static/
│           ├── index.html       # Dashboard UI
│           └── plans/           # Converted pavilion plan PNGs (not in git)
├── pyproject.toml
├── README.md
└── .gitignore
```

---

## Technology Summary

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.11+ | Fast prototyping, rich CV/ML ecosystem |
| Person Detection | YOLOv8n (Ultralytics) | Real-time, pre-trained, 6 MB model |
| Pose Estimation | MediaPipe Pose Landmarker | 33 landmarks, lightweight, no GPU needed |
| Camera | OpenCV VideoCapture | Universal: USB, RTSP, files |
| Web Framework | FastAPI + Uvicorn | Async, WebSocket support, modern |
| Real-time UI | WebSocket + Tailwind CSS | Live updates, no page reload |
| Config | Pydantic V2 + YAML | Type-safe, validated |
| Motor Control | Protocol-based (GPIO/Serial) | Swappable backends |
| Testing | pytest | Standard Python testing |
