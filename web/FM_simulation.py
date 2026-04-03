#!/usr/bin/env python3
"""
MARP FM Simulator
Sends raw float32 PCM audio chunks on ZMQ port 5002,
exactly as GNU Radio's ZMQ PUB Sink would.

Run alongside webserver.py to test the FM panel without hardware.
"""

import zmq
import numpy as np
import time

SAMPLE_RATE = 48000   # must match GNU Radio audio sink rate
CHUNK_SIZE  = 4096    # samples per ZMQ send — adjust if you hear glitching
CENTER_FREQ = 96.7e6  # simulated station frequency

# ── Tone parameters ──────────────────────────────────────────
# Two tones mixed to simulate real audio content
TONE_A_HZ   = 440.0   # A4
TONE_B_HZ   = 554.4   # C#5 — makes a major third with A4

context = zmq.Context()
socket  = context.socket(zmq.PUB)
socket.bind("tcp://127.0.0.1:5002")
time.sleep(0.5)   # let subscribers connect

print("FM Simulator — ZMQ PUB on tcp://127.0.0.1:5002")
print("Sample rate : {} Hz".format(SAMPLE_RATE))
print("Chunk size  : {} samples ({:.1f} ms)".format(CHUNK_SIZE, 1000 * CHUNK_SIZE / SAMPLE_RATE))
print("Simulating  : {:.1f} MHz".format(CENTER_FREQ / 1e6))
print("Press Ctrl+C to stop.\n")

chunk_idx   = 0
t_chunk     = CHUNK_SIZE / SAMPLE_RATE   # seconds per chunk

while True:
    loop_start = time.time()

    # Sample indices for this chunk (continuous — no phase reset)
    t = (np.arange(CHUNK_SIZE) + chunk_idx * CHUNK_SIZE) / SAMPLE_RATE

    # Stereo-ish mix of two tones with a slow amplitude envelope
    envelope = 0.5 + 0.3 * np.sin(2 * np.pi * 0.3 * t)   # 0.3 Hz LFO
    signal   = (0.5 * np.sin(2 * np.pi * TONE_A_HZ * t)
              + 0.3 * np.sin(2 * np.pi * TONE_B_HZ * t)) * envelope

    # Clip to [-1, 1] and cast to float32
    signal = np.clip(signal, -1.0, 1.0).astype(np.float32)

    # Send raw bytes — same format as GR ZMQ PUB Sink with Vec Length=1
    socket.send(signal.tobytes())
    chunk_idx += 1

    if chunk_idx % 50 == 0:
        power_db = 10 * np.log10(np.mean(signal**2) + 1e-12)
        print("Chunk {:6d} | power {:.1f} dBFS | queue nominal".format(chunk_idx, power_db))

    # Pace to real-time so the server queue doesn't blow up
    elapsed = time.time() - loop_start
    sleep_t = t_chunk - elapsed
    if sleep_t > 0:
        time.sleep(sleep_t)