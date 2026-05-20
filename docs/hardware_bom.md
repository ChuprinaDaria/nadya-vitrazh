# Hardware Bill of Materials (BOM)

Prices as of May 2026. All prices in EUR, sourced from European retailers where possible.

---

## Option A: Prototype (Desktop Demo)

Everything needed to demonstrate the concept on a laptop with webcam.

| # | Item | Qty | Unit Price | Total | Notes |
|---|------|-----|-----------|-------|-------|
| 1 | Laptop with webcam | 1 | (existing) | €0 | Any modern laptop, Python 3.11+ |
| | | | | **€0** | |

Software-only demo. No purchases needed. Run `python scripts/demo_dashboard.py` for simulation or `python -m vitrazh --dashboard --source 0` for real detection via webcam.

---

## Option B: Standalone Prototype (with real camera, no motors)

A self-contained unit that detects people and shows the dashboard, but without physical stained glass movement. Good for exhibitions or client presentations.

| # | Item | Qty | Unit Price | Total | Notes |
|---|------|-----|-----------|-------|-------|
| 1 | Raspberry Pi 5 (8 GB) | 1 | €190 | €190 | Main compute. Prices rose in 2026 due to RAM shortage |
| 2 | RPi 5 Official Case + Fan | 1 | €10 | €10 | Integrated 25mm fan for cooling |
| 3 | RPi 5 Power Supply (27W USB-C) | 1 | €12 | €12 | Official PSU recommended |
| 4 | MicroSD Card 64 GB (A2) | 1 | €12 | €12 | Samsung EVO Select or SanDisk Extreme |
| 5 | USB Wide-Angle Camera | 1 | €25–40 | €35 | ELP 1080p 120° FOV or Arducam IMX219 USB. UVC driver-free |
| 6 | Monitor + HDMI cable | 1 | (existing) | €0 | For dashboard display |
| 7 | Ethernet cable or WiFi | 1 | €5 | €5 | For remote dashboard access |
| | | | | **~€264** | |

---

## Option C: Full Production Installation

Complete pavilion setup with motors, camera, and compute.

### Compute & Camera

| # | Item | Qty | Unit Price | Total | Notes |
|---|------|-----|-----------|-------|-------|
| 1 | Raspberry Pi 5 (8 GB) | 1 | €190 | €190 | Runs YOLO + MediaPipe at ~15 FPS |
| 2 | RPi 5 Official Case + Fan | 1 | €10 | €10 | |
| 3 | RPi 5 Power Supply (27W USB-C) | 1 | €12 | €12 | |
| 4 | MicroSD Card 64 GB (A2) | 1 | €12 | €12 | |
| 5 | USB Wide-Angle Camera (1080p, 120°+) | 1 | €35 | €35 | Wide angle to cover pavilion entrance area |
| 6 | USB extension cable (5m, active) | 1 | €15 | €15 | If camera is mounted far from RPi |
| | **Subtotal Compute & Camera** | | | **€274** | |

### Motor Control (6 stained glass positions)

**Variant 1: Raspberry Pi GPIO direct** (simpler, fewer parts)

| # | Item | Qty | Unit Price | Total | Notes |
|---|------|-----|-----------|-------|-------|
| 7 | NEMA 17 Stepper Motor (42mm, 1.8°) | 6 | €10 | €60 | 40 N·cm torque sufficient for lightweight glass |
| 8 | TMC2209 Silent Stepper Driver | 6 | €10 | €60 | Ultra-quiet, StealthChop — important for art installation |
| 9 | Slip Ring (6-wire, 2A) | 6 | €8 | €48 | For continuous rotation without tangling wires |
| 10 | 12V 10A Power Supply (120W) | 1 | €25 | €25 | Powers all 6 motors |
| 11 | Wiring, connectors, DIN rail, terminal blocks | 1 | €30 | €30 | JST connectors, 18 AWG wire, heatshrink |
| 12 | Custom PCB or protoboard | 1 | €15 | €15 | To mount 6x TMC2209 drivers |
| | **Subtotal Motors (GPIO)** | | | **€238** | |

**Variant 2: Arduino/ESP32 motor controller** (more flexible, offloads RPi)

| # | Item | Qty | Unit Price | Total | Notes |
|---|------|-----|-----------|-------|-------|
| 7 | NEMA 17 Stepper Motor (42mm, 1.8°) | 6 | €10 | €60 | Same as above |
| 8 | TMC2209 Silent Stepper Driver | 6 | €10 | €60 | Same as above |
| 9 | Slip Ring (6-wire, 2A) | 6 | €8 | €48 | Same as above |
| 10 | ESP32-S3 DevKit | 1 | €12 | €12 | WiFi/BLE, receives commands from RPi over serial or WiFi |
| 11 | CNC Shield V3 (for Arduino Uno footprint) | 2 | €5 | €10 | Each drives 3-4 motors. Or use custom wiring to ESP32 |
| 12 | 12V 10A Power Supply (120W) | 1 | €25 | €25 | |
| 13 | Wiring, connectors, DIN rail | 1 | €30 | €30 | |
| | **Subtotal Motors (ESP32)** | | | **€245** | |

### Enclosure & Mounting

| # | Item | Qty | Unit Price | Total | Notes |
|---|------|-----|-----------|-------|-------|
| 14 | Weatherproof enclosure (IP65, ~300x200x150mm) | 1 | €25 | €25 | For RPi + drivers if outdoors |
| 15 | Camera mount (articulating arm or bracket) | 1 | €15 | €15 | Adjustable angle for optimal detection |
| 16 | Cable glands (PG9/PG11) | 6 | €1 | €6 | Waterproof cable entry |
| 17 | DIN rail + terminal blocks | 1 | €10 | €10 | Clean wiring inside enclosure |
| | **Subtotal Enclosure** | | | **€56** | |

### Display (for Nadiia's dashboard)

| # | Item | Qty | Unit Price | Total | Notes |
|---|------|-----|-----------|-------|-------|
| 18 | Monitor 10–15" (HDMI) | 1 | €80 | €80 | Optional — can use any tablet/laptop on WiFi instead |
| 19 | HDMI cable (2m) | 1 | €8 | €8 | If using direct HDMI from RPi |
| | **Subtotal Display** | | | **€88** | |

---

## Total Cost Summary

| Configuration | Total | Description |
|--------------|-------|-------------|
| **A. Prototype (laptop)** | **€0** | Software demo on existing laptop |
| **B. Standalone prototype** | **~€264** | RPi + camera + dashboard on monitor, no motors |
| **C. Full production (GPIO)** | **~€656** | RPi + camera + 6 motors + enclosure + display |
| **C. Full production (ESP32)** | **~€663** | RPi + camera + ESP32 motor controller + 6 motors + enclosure + display |

> **Note:** Display (€88) is optional in production — Nadiia can monitor via any device on local WiFi at `http://raspberry-ip:8000`. Without display: **~€568–575**.

---

## Where to Buy (Europe)

| Retailer | URL | Good for |
|----------|-----|----------|
| Botland (PL) | botland.com.pl | RPi, motors, drivers — fast EU shipping |
| Electrokit (SE) | electrokit.com | ESP32, CNC shields, slip rings |
| Berrybase (DE) | berrybase.de | Raspberry Pi + accessories |
| The Pi Hut (UK) | thepihut.com | Official RPi accessories |
| TME (PL) | tme.eu | Electronic components, bulk pricing |
| Mouser (EU) | mouser.eu | Professional components, wide catalog |
| Amazon.de | amazon.de | Quick delivery, misc parts |
| AliExpress | aliexpress.com | Budget stepper motors, slip rings (2-3 week delivery) |

---

## Motor Selection Notes

**Why NEMA 17 steppers:**
- Precise positioning — glass pieces must align exactly when "assembled"
- Sufficient torque for lightweight stained glass pieces on spindles
- Silent with TMC2209 drivers (StealthChop mode) — critical for art installation
- Standard size, widely available, easy to mount

**Why TMC2209 drivers:**
- StealthChop2 — virtually silent operation below 100 RPM
- SpreadCycle — smooth rotation at higher speeds
- UART configuration — tunable current limit, microstepping, stall detection
- Overcurrent and overtemperature protection

**Why slip rings:**
- Stained glass pieces rotate continuously (360°+)
- Without slip rings, wires would tangle and break
- 6-wire slip rings handle motor power (2 wires) + optional LED lighting (4 wires)

---

## Camera Selection Notes

**Requirements for this project:**
- Wide angle (120°+) — must cover the pavilion entrance area
- 1080p minimum — enough resolution for person detection at 3–5m
- USB (UVC compatible) — plug-and-play with RPi, no CSI ribbon cable needed
- Indoor/outdoor capable — depending on pavilion design

**Recommended models:**
- **ELP 1080p USB (120° wide angle)** — ~€25–35, good balance of quality and price
- **Arducam IMX219 USB (175° ultra-wide)** — ~€35–45, excellent FOV but may need barrel distortion correction
- **Logitech C920/C922** — ~€50–70, proven quality but only 78° FOV (may need to mount further back)

**Detection range:** YOLOv8n reliably detects persons at 1–10m from camera. At 15 FPS on RPi 5, detection latency is ~70ms — imperceptible for this application.

---

## Power Budget

| Component | Voltage | Current (max) | Power |
|-----------|---------|--------------|-------|
| Raspberry Pi 5 | 5V | 5A | 25W |
| 6x NEMA 17 motors | 12V | 6 × 1.5A = 9A | 108W |
| USB camera | 5V (from RPi) | 0.5A | 2.5W |
| ESP32 (if used) | 5V (from 12V reg) | 0.5A | 2.5W |
| **Total** | | | **~138W** |

A 12V/10A (120W) PSU covers all motors with headroom. The RPi has its own 5V/5A PSU. Total wall power: ~160W.
