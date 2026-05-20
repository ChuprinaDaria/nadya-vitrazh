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

## Detailed Interaction Flow

This section explains exactly how the system behaves in every scenario — from a single person approaching one installation to a crowd walking through a space with 10 installations.

### How a Person Is Detected in a Specific Vitrazh Zone

Each stained glass installation has its own **activation zone** — a polygon drawn on the camera's field of view. This is the same zone evaluation technique used in the [korview-ai](https://github.com/ferusnet/korview-ai) perimeter security system.

```
Camera FOV (full frame)
┌─────────────────────────────────────────────────┐
│                                                   │
│     ┌──────────┐                ┌──────────┐     │
│     │ Zone #1  │                │ Zone #2  │     │
│     │ Vitrazh  │   (corridor)   │ Vitrazh  │     │
│     │ "Sunrise"│                │ "Forest" │     │
│     └──────────┘                └──────────┘     │
│                                                   │
│     ┌──────────┐                ┌──────────┐     │
│     │ Zone #3  │                │ Zone #4  │     │
│     │ Vitrazh  │                │ Vitrazh  │     │
│     │ "River"  │                │ "Birds"  │     │
│     └──────────┘                └──────────┘     │
│                                                   │
└─────────────────────────────────────────────────┘
```

**Step-by-step detection:**

1. **YOLOv8 detects all persons** in the frame → produces bounding boxes with `(x, y, w, h)` normalized to `[0, 1]`.

2. **Center point extraction** — the bottom-center of each bounding box is used as the person's "foot position":
   ```
   foot_x = bbox.x + bbox.w / 2
   foot_y = bbox.y + bbox.h          # bottom of bounding box
   ```

3. **Point-in-polygon test** — for each person's foot point, a ray-casting algorithm checks which zone (if any) contains that point. This is the same algorithm from korview-ai's `ZoneEvaluator`.

4. **Zone → Installation mapping** — each zone is linked to a specific stained glass installation. If `foot_point ∈ Zone #3`, that means the person is standing in front of Vitrazh "River".

5. **Each installation has its own state machine** — Zone #1 can be in `ASSEMBLED` while Zone #3 is in `ROTATING`. They are fully independent.

**Zone configuration** is stored in a JSON file with normalized coordinates:
```json
{
  "zones": [
    {
      "zone_id": "vitrazh_1",
      "name": "Sunrise",
      "polygon": [[0.05, 0.1], [0.25, 0.1], [0.25, 0.45], [0.05, 0.45]]
    },
    {
      "zone_id": "vitrazh_2",
      "name": "Forest",
      "polygon": [[0.55, 0.1], [0.75, 0.1], [0.75, 0.45], [0.55, 0.45]]
    }
  ]
}
```

Zones are calibrated once during installation using the dashboard — draw polygons on the camera feed to mark the area in front of each stained glass piece.

---

### Single Person Scenario (1 person, 1 vitrazh)

This is the basic interaction flow:

```
Time    Event                           State Machine          Motors
─────   ─────                           ─────────────          ──────
0.0s    Person enters Zone #3           ROTATING               All 6 pieces spinning
0.0s    Presence timer starts           ROTATING               Still spinning
2.0s    presence_delay reached          ROTATING → ASSEMBLING  Motors decelerate
2.3s    Transition complete             ASSEMBLING → ASSEMBLED Motors hold at home position
        ...person admires the artwork...
        Person is IDLE (standing)       ASSEMBLED              Holding still
15.0s   Person walks away               ASSEMBLED              Still holding
15.0s   Absence timer starts            ASSEMBLED              Still holding
18.0s   absence_delay (3s) reached      ASSEMBLED → DISASSEM.  Motors accelerate
18.3s   Transition complete             DISASSEMBLING → ROTAT. Full speed spinning
```

**Key detail:** The 2-second `presence_delay` prevents the glass from reacting to people just walking past. Only someone who stops and stands in the zone triggers assembly.

---

### Photo Pose Scenario (person tries to photograph)

```
Time    Event                           State Machine          Motors
─────   ─────                           ─────────────          ──────
0.0s    Person in zone, IDLE            ASSEMBLED              Holding still
3.0s    Person raises phone/camera      ASSEMBLED              Still holding
3.0s    Pose = PHOTOGRAPHING detected   ASSEMBLED              Still holding
3.0s    Photo timer starts              ASSEMBLED              Still holding
4.5s    photo_resume_delay (1.5s) hit   ASSEMBLED → DISASSEM.  Motors start spinning
4.8s    Transition complete             DISASSEMBLING → ROTAT. Full speed — artwork "escapes"
        ...person lowers phone...
5.0s    Pose = IDLE again               ROTATING               Still spinning
5.0s    Presence timer restarts         ROTATING               Still spinning
7.0s    presence_delay (2s) reached     ROTATING → ASSEMBLING  Decelerating again
7.3s    ASSEMBLED again                 ASSEMBLED              Holding still
```

**The artwork plays a game with the viewer:** it assembles when you just look, but breaks apart when you try to capture it. This creates a loop:
1. Stand still → glass assembles (2s)
2. Raise phone → glass spins away (1.5s)
3. Lower phone → glass assembles again (2s)
4. Repeat

**Why 1.5 seconds for photo detection?** Short enough to feel responsive, long enough to avoid false triggers from scratching your face or gesturing.

**How pose detection works technically:**

| Pose | MediaPipe Check | Threshold |
|------|----------------|-----------|
| `PHOTOGRAPHING` | At least one arm: elbow angle 30°–150° AND wrist above elbow AND wrist at face height (`\|wrist.y - nose.y\| < 0.15`) | Configurable in `classifier` section |
| `PHONE_VIEWING` | Wrist-to-nose distance < 0.15 (normalized) — holding phone close to face | Lower threshold = more sensitive |
| `IDLE` | Neither of the above | Default state |

MediaPipe provides 33 landmarks per person. The classifier only uses 7 key points: nose, both shoulders, both elbows, both wrists. This makes it fast (~2ms per classification) and reliable.

---

### Multi-Person Scenario (2+ people at one vitrazh)

```
Time    Event                           State Machine          Behavior
─────   ─────                           ─────────────          ────────
0.0s    Person A enters Zone #3         ROTATING               Spinning
2.0s    Person A waited 2s → ASSEMBLED  ASSEMBLED              Holding still
5.0s    Person B also enters Zone #3    ASSEMBLED              Still holding (A is IDLE)
8.0s    Person A raises phone           ASSEMBLED              Check: is ANY person IDLE?
```

**Multi-person rules:**

| Scenario | Behavior | Rationale |
|----------|----------|-----------|
| 1 person IDLE in zone | ASSEMBLED — glass holds | Standard behavior |
| 2 people, both IDLE | ASSEMBLED — glass holds | More viewers = keep showing art |
| 2 people, one PHOTOGRAPHING, one IDLE | **ASSEMBLED — glass holds** | At least one person is genuinely looking |
| 2 people, both PHOTOGRAPHING | **DISASSEMBLING → ROTATING** | Everyone is trying to capture — glass escapes |
| 1 person leaves, 1 stays IDLE | ASSEMBLED — glass holds | Still has an audience |
| All people leave | Absence timer starts → ROTATING after 3s | No audience left |

**Implementation:** The state machine counts persons in the zone and checks poses for ALL of them:
- `person_present = len(persons_in_zone) > 0`
- `all_photographing = all(pose != IDLE for pose in persons_in_zone)` — only triggers rotation if EVERY person is photographing
- This means a single genuine viewer "protects" the artwork from disassembling

**Pose classification for multiple persons:** MediaPipe runs on the cropped bounding box of the person closest to the center of the zone (the "primary" person). If there are multiple persons, the system evaluates the one who has been in the zone the longest (based on `tracking_id`). In the multi-person upgrade, pose classification runs for ALL persons in the zone.

---

### Scaling to 10 Installations in One Space

A pavilion or gallery with 10 stained glass installations along the perimeter, each independent:

```
┌─────────────────────────────────────────────────────────────┐
│                     PAVILION PERIMETER                       │
│                                                               │
│  [V1]   [V2]   [V3]   [V4]   [V5]   [V6]   [V7]   [V8]   │
│                                                               │
│                    ← visitor path →                           │
│                                                               │
│                         [V9]   [V10]                          │
│                                                               │
│       CAM-1 (covers V1–V5)      CAM-2 (covers V6–V10)       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

#### Architecture: 1 RPi per camera, central coordinator

```
┌──────────┐   ┌──────────┐
│ Camera 1 │   │ Camera 2 │         (USB or RTSP)
└────┬─────┘   └────┬─────┘
     │               │
┌────▼─────┐   ┌────▼─────┐
│  RPi #1  │   │  RPi #2  │         (1 RPi per 5 installations)
│ YOLO +   │   │ YOLO +   │
│ MediaPipe│   │ MediaPipe│
│ Zones    │   │ Zones    │
│ 1–5      │   │ 6–10     │
└────┬─────┘   └────┬─────┘
     │               │
     │   WiFi / Ethernet
     │               │
┌────▼───────────────▼────┐
│   Central Coordinator    │         (optional — can be one of the RPis)
│   - Dashboard            │
│   - Aggregated state     │
│   - Monitoring           │
└──────────┬──────────────┘
           │
     ┌─────▼─────┐
     │  Motor     │
     │  Controllers│    (ESP32 or GPIO — one per RPi, controls 5 motors each)
     └───────────┘
```

#### Data Flow for 10 Installations

**Per-frame processing on each RPi (~67ms per frame at 15 FPS):**

```
Frame capture             ~5ms    (OpenCV read)
     │
YOLOv8n inference        ~45ms    (person detection, all persons in view)
     │
Zone assignment           ~0.1ms  (point-in-polygon for each detection)
     │
For each occupied zone:
  MediaPipe pose          ~15ms   (per person, run only for occupied zones)
  Pose classification     ~0.1ms  (rule-based, negligible)
  State machine update    ~0.01ms (pure logic)
     │
Motor command (if changed) ~1ms   (GPIO write or serial TX)
     │
WebSocket broadcast       ~0.5ms  (dashboard update)
```

**Total per frame: ~67ms** — fits within the 15 FPS budget (66.7ms per frame).

**Communication between RPis (if multi-RPi setup):**

| Protocol | When | Payload | Latency |
|----------|------|---------|---------|
| MQTT | State change events | `{"zone": "vitrazh_3", "state": "assembled", "persons": 2}` | ~5ms LAN |
| WebSocket | Dashboard live updates | Same JSON, broadcast to all dashboard clients | ~10ms |
| Serial/GPIO | Motor commands | `SET_STATE vitrazh_3 ASSEMBLED` | ~1ms |

**MQTT topic structure for 10 installations:**
```
vitrazh/cam1/zone1/state    → "assembled"
vitrazh/cam1/zone1/persons  → 2
vitrazh/cam1/zone1/pose     → "idle"
vitrazh/cam2/zone6/state    → "rotating"
...
```

#### Scaling Considerations

| Factor | 1 installation | 5 installations (1 camera) | 10 installations (2 cameras) |
|--------|---------------|---------------------------|------------------------------|
| RPi units | 1 | 1 | 2 |
| Cameras | 1 | 1 (wide-angle) | 2 |
| YOLO runs/frame | 1 | 1 (detects all persons in view) | 1 per camera |
| MediaPipe runs/frame | 0–1 | 0–5 (only occupied zones) | 0–5 per camera |
| ESP32/motor controllers | 1 | 1 (6 channels) | 2 (6 channels each, 2 spare) |
| Network | None needed | None needed | LAN switch + optional MQTT |

**Key insight:** YOLO runs ONCE per frame regardless of how many installations are in view. It detects ALL persons at once. The per-zone overhead is only MediaPipe (for occupied zones) + state machine (negligible). So going from 1 to 5 installations on one camera adds almost zero compute cost if only 1 zone is occupied at a time.

**Worst case:** all 5 zones occupied simultaneously = 5× MediaPipe runs per frame = ~75ms additional. At 15 FPS this would drop to ~10 FPS — still acceptable. If needed, MediaPipe can be skipped for distant persons (pose only matters when close enough to photograph).

---

### Data Processing Summary

**What happens every frame (66ms cycle):**

```
1. CAPTURE          Camera → BGR frame (numpy array, ~1920×1080×3 = 6 MB)
                    ↓
2. DETECT           YOLOv8n → list of person bounding boxes + tracking IDs
                    Time: ~45ms | Output: [{bbox, confidence, track_id}, ...]
                    ↓
3. ASSIGN ZONES     For each detection → point-in-polygon → zone_id or None
                    Time: ~0.1ms | Output: {zone_id: [detections]}
                    ↓
4. CLASSIFY POSE    For each occupied zone → crop frame to bbox → MediaPipe → landmarks → classify
                    Time: ~15ms per person | Output: {zone_id: PoseClass}
                    ↓
5. UPDATE STATE     For each zone → state_machine.update(person_present, pose)
                    Time: ~0.01ms | Output: {zone_id: InstallationState}
                    ↓
6. COMMAND MOTORS   If state changed → send command to motor controller
                    Time: ~1ms | Protocol: GPIO pin write / serial TX / MQTT publish
                    ↓
7. BROADCAST        Send state to dashboard via WebSocket
                    Time: ~0.5ms | Format: JSON over WS
```

**What is NOT transmitted over network:**
- Raw video frames (stay local on RPi, never sent anywhere)
- Bounding box images (not saved unless debug mode)
- Landmark coordinates (processed in-memory, discarded)

**What IS transmitted:**
- State changes: `{zone_id, state, person_count, pose}` — ~100 bytes per event
- Motor commands: `{zone_id, target_state}` — ~50 bytes per command
- Dashboard updates: same JSON as state changes — ~100 bytes at 15 FPS = ~1.5 KB/s

**Privacy:** No images or video leave the device. No facial recognition. No data storage. The system only knows: "a person-shaped object is in zone X with pose Y". All processing is local, GDPR-compliant by design.

---

### Edge Cases and Failure Modes

| Situation | System Behavior |
|-----------|----------------|
| Camera disconnects | Exponential backoff reconnect (1s → 2s → 4s → ... → 30s max). All installations freeze in last known state. |
| Person partially in two zones | Foot point determines zone. One person = one zone assignment. |
| Person detected but no landmarks (back to camera) | Pose = IDLE (default). Glass stays assembled — benefit of the doubt. |
| Two people swap zones | ByteTrack maintains tracking IDs. Each zone re-evaluates independently. |
| Very fast walk-through (< 2s in zone) | `presence_delay` prevents trigger. Glass stays rotating. |
| Child (small bounding box) | YOLOv8 detects children. Smaller bbox = foot point closer to center. Works normally. |
| Wheelchair user | YOLOv8 detects seated persons. MediaPipe landmarks may have lower visibility for legs, but upper body (arms, phone) still classified correctly. |
| Night / low light | Depends on camera. With IR camera or adequate pavilion lighting — works normally. Very dark = detection confidence drops, `confidence` threshold filters out false positives. |
| RPi overheats | Throttles CPU → lower FPS. Active cooler recommended. State machines continue with lower update rate. |

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
