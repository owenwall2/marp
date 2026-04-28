#!/usr/bin/env python3
import time
import numpy as np
import zmq

# ── Hardcoded settings ───────────────────────────────────────
NPZ_FILE = "equalized_passive_radar_maps.npz"
ARRAY_NAME = "maps_pos"
ZMQ_HOST = "127.0.0.1"
ZMQ_PORT = 5003

REPEAT = True
FRAME_INTERVAL_SEC = 0.05
TRANSPOSE = False


def main():
    print(f"Loading {NPZ_FILE} ...")
    with np.load(NPZ_FILE, allow_pickle=False) as z:
        if ARRAY_NAME not in z:
            raise KeyError(f"Array '{ARRAY_NAME}' not found. Available keys: {list(z.keys())}")
        data = np.asarray(z[ARRAY_NAME], dtype=np.float32)

    if data.ndim == 2:
        frames = data[None, ...]
    elif data.ndim == 3:
        frames = data
    else:
        raise ValueError(f"Expected 2D or 3D array, got shape {data.shape}")

    print(f"Loaded array {ARRAY_NAME} with shape {frames.shape}")

    ctx = zmq.Context()
    sock = ctx.socket(zmq.PUB)
    sock.bind(f"tcp://{ZMQ_HOST}:{ZMQ_PORT}")
    print(f"Publishing on tcp://{ZMQ_HOST}:{ZMQ_PORT}")

    time.sleep(0.5)  # let subscribers connect

    idx = 8000
    total = frames.shape[0]

    threshold = 20
    gain = 100

    while True:
        frame = frames[idx]

        mask = frame > threshold
        frame[mask] = threshold + gain * (frame[mask] - threshold)


        if TRANSPOSE:
            frame = frame.T

        frame = np.asarray(frame, dtype=np.float32)

        # No resizing. Send the original frame.
        sock.send(frame.tobytes())

        # print(f"Sent frame {idx + 1}/{total} shape={frame.shape}")
        idx += 10

        if idx >= total:
            if REPEAT:
                idx = 8000
            else:
                break

        time.sleep(FRAME_INTERVAL_SEC)

    sock.close()
    ctx.term()


if __name__ == "__main__":
    main()