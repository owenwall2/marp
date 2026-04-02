#!/usr/bin/env python3
"""
MARP — Multi-Application Radio Platform
webserver.py — Unified Flask/SocketIO server supporting ADS-B, FM, and Passive Radar
"""

from gevent import monkey
monkey.patch_all()

import time
import os
import json
from flask import Flask, request, send_from_directory, jsonify
from flask_socketio import SocketIO
from threading import Thread
import zmq.green as zmq
import numpy as np
from collections import deque

# # GNURadio-IIO and libiio hack
# import sys
# if "/usr/lib/python3.8/site-packages" not in sys.path:
#     sys.path.insert(0, "/usr/lib/python3.8/site-packages")

# import iio_hw


try:
    import pmt
    HAS_PMT = True
except ImportError:
    print("WARNING: pmt not available, ZMQ messages will be raw bytes")
    HAS_PMT = False

ZED_IP = "192.168.65.254"   # ZED board's IP over Ethernet
_iio_ctx = None

# ── Network config ────────────────────────────────────────────
HTTP_ADDRESS = "0.0.0.0"
HTTP_PORT    = 5000
ZMQ_ADDRESS  = "127.0.0.1"

# One ZMQ port per application (GNU Radio flowgraph ZMQ PUB sinks)
ZMQ_PORTS = {
    "adsb":  5001,
    "fm":    5002,
    "radar_ref": 5003,
    "radar_surv": 5004,
}

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# ── App state ─────────────────────────────────────────────────
state = {
    "mode":          "adsb",   # active application
    "zmq_connected": False,    # at least one ZMQ message received recently
    "params": {
        "adsb":  {"center_freq": 1090e6, "gain": 50},
        "fm":    {"center_freq":  96.7e6, "gain": 40, "volume": 80},
        "radar": {"center_freq":  95.0e6, "gain": 50, "integration_time": 1.0},
    }
}

# ── Flask / SocketIO ──────────────────────────────────────────
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config["SECRET_KEY"] = "marp-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')


# Radar buffers
radar_ref_buffer  = deque(maxlen=2_000_000)
radar_surv_buffer = deque(maxlen=2_000_000)


def _get_iio_context():
    """Lazy-connect to the ZED board's IIO daemon."""
    global _iio_ctx
    try:
        import iio
        if _iio_ctx is None:
            _iio_ctx = iio_hw.Context(f"ip:{ZED_IP}")
            print("IIO connected to ZED board at", ZED_IP)
        return _iio_ctx
    except Exception as e:
        print("IIO connection failed:", e)
        _iio_ctx = None
        return None

def apply_hardware_params(app_name, params):
    """Push parameter changes directly to FMCOMMS3 via libiio."""
    ctx = _get_iio_context()
    if ctx is None:
        print("IIO not available — skipping hardware update")
        return

    try:
        import iio
        phy = ctx.find_device("ad9361-phy")

        if "center_freq" in params:
            freq_hz = int(params["center_freq"])
            phy.find_channel("altvoltage0", True).attrs["frequency"].value = str(freq_hz)
            print("IIO: center_freq set to {} Hz".format(freq_hz))

        if "gain" in params:
            # Switch to manual gain mode first
            phy.find_channel("voltage0", False).attrs["gain_control_mode"].value = "manual"
            phy.find_channel("voltage0", False).attrs["hardwaregain"].value = str(int(params["gain"]))
            print("IIO: gain set to {} dB".format(params["gain"]))

        if "bandwidth" in params:
            bw_hz = int(params["bandwidth"])
            phy.find_channel("voltage0", False).attrs["rf_bandwidth"].value = str(bw_hz)
            print("IIO: bandwidth set to {} Hz".format(bw_hz))

    except Exception as e:
        print("IIO param apply error:", e)
        _iio_ctx = None   # force reconnect next time


def make_adsb_zmq_thread():
    """Thread to receive ADS-B PMT messages from ZMQ and emit to SocketIO"""
    def _thread():
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        port = ZMQ_PORTS["adsb"]
        socket.connect(f"tcp://{ZMQ_ADDRESS}:{port}")
        print(f"ZMQ listener [ADSB ] connected to tcp://{ZMQ_ADDRESS}:{port}")

        while True:
            try:
                pdu_bin = socket.recv()
                state["zmq_connected"] = True
                socketio.emit("serverStatus", {"zmq_connected": True})

                if HAS_PMT:
                    pdu = pmt.deserialize_str(pdu_bin)
                    data = pmt.to_python(pmt.car(pdu))
                else:
                    data = {"raw": pdu_bin.hex(), "app": "adsb"}

                if state["mode"] == "adsb":
                    socketio.emit("updatePlane", data)

                print(f"[ADSB ] {data}")

            except Exception as e:
                print(f"ZMQ error [ADSB ]: {e}")
                time.sleep(1)

    return _thread


def make_fm_zmq_thread(port):
    def _thread():
        import numpy as np
        import base64

        context = zmq.Context()
        socket  = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.connect("tcp://{}:{:d}".format(ZMQ_ADDRESS, port))
        print("ZMQ listener [FM    ] connected to tcp://{}:{}".format(ZMQ_ADDRESS, port))

        spectrum_counter = 0

        while True:
            try:
                raw = socket.recv()          # raw float32 bytes from ZMQ PUB Sink
                state["zmq_connected"] = True
                socketio.emit("serverStatus", {"zmq_connected": True})

                if state["mode"] != "fm":
                    continue                 # still drain the socket, just don't emit

                samples = np.frombuffer(raw, dtype=np.float32)

                # Signal power
                power_db = float(10 * np.log10(np.mean(samples**2) + 1e-12))

                # Spectrum — only compute every 4th chunk to save CPU
                spectrum = None
                spectrum_counter += 1
                if spectrum_counter % 4 == 0:
                    window   = np.hanning(len(samples))
                    fft_vals = np.fft.rfft(samples * window)
                    spectrum = (20 * np.log10(np.abs(fft_vals) / len(samples) + 1e-12)).tolist()
                    spectrum = spectrum[::4]  # decimate for display

                # Audio — base64 encode raw float32 PCM for Web Audio API
                audio_b64 = base64.b64encode(raw).decode("ascii")

                socketio.emit("updateFM", {
                    "audio":      audio_b64,
                    "signal_db":  power_db,
                    "spectrum":   spectrum,   # None on skipped frames, frontend handles it
                    "center_freq": state["params"]["fm"]["center_freq"],
                })

            except Exception as e:
                print("ZMQ error [FM]: {}".format(e))
                time.sleep(0.1)   # short sleep — audio is time-sensitive

    return _thread

def radar_ref_handler(raw):
    radar_ref_buffer.extend(np.frombuffer(raw, dtype=np.complex64))

def radar_surv_handler(raw):
    radar_surv_buffer.extend(np.frombuffer(raw, dtype=np.complex64))

def make_radar_thread(port, handler):
    def _thread():
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.connect(f"tcp://{ZMQ_ADDRESS}:{port}")
        print(f"ZMQ listener [RADAR ] connected to tcp://{ZMQ_ADDRESS}:{port}")

        while True:
            try:
                raw = socket.recv()
                handler(raw)
            except Exception as e:
                print(f"ZMQ error [RADAR]: {e}")
                time.sleep(0.1)
    return _thread

def radar_processing_thread():
    fs = 583e6
    c  = 299792458.0

    N = 1024
    step = 1024
    num_blocks = 64
    nfft_delay = 2 * N - 1

    lags = np.arange(-(N - 1), N)
    path_diff_m = c * lags / fs

    while True:
        try:
            if len(radar_ref_buffer) < (num_blocks * step + N):
                time.sleep(0.05)
                continue

            if len(radar_surv_buffer) < (num_blocks * step + N):
                time.sleep(0.05)
                continue

            # Pull synchronized chunks
            ref  = np.array([radar_ref_buffer.popleft()  for _ in range(num_blocks * step + N)])
            surv = np.array([radar_surv_buffer.popleft() for _ in range(num_blocks * step + N)])

            corr_matrix = np.zeros((num_blocks, nfft_delay), dtype=np.complex64)

            for i in range(num_blocks):
                start = i * step
                stop  = start + N

                block_ref  = ref[start:stop]
                block_surv = surv[start:stop]

                X = np.fft.fft(block_ref, nfft_delay)
                Y = np.fft.fft(block_surv, nfft_delay)

                corr = np.fft.ifft(Y * np.conj(X))
                corr_matrix[i, :] = corr

            doppler_map = np.fft.fftshift(
                np.fft.fft(corr_matrix, axis=0),
                axes=0
            )

            rd_map = 20 * np.log10(np.abs(doppler_map) + 1e-12)

            # Downsample for web (VERY IMPORTANT)
            rd_small = rd_map[::2, ::4].tolist()

            if state["mode"] == "radar":
                socketio.emit("updateRadar", {
                    "map": rd_small,
                    "range_axis": path_diff_m[::4].tolist(),
                    "doppler_bins": list(range(-num_blocks//2, num_blocks//2, 2))
                })

        except Exception as e:
            print("Radar processing error:", e)
            time.sleep(0.1)

# ── REST API ──────────────────────────────────────────────────

@app.route("/api/mode", methods=["GET"])
def get_mode():
    return jsonify({"mode": state["mode"]})



VALID_MODES = ["adsb", "fm", "radar"]
@app.route("/api/mode", methods=["POST"])
def set_mode():
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "").lower()
    if mode not in VALID_MODES:
        return jsonify({"error": "Unknown mode. Choose: {}".format(VALID_MODES)}), 400
    state["mode"] = mode
    print("Mode switched to:", mode)
    socketio.emit("modeChanged", {"mode": mode})
    return jsonify({"mode": mode, "ok": True})


@app.route("/api/params", methods=["GET"])
def get_params():
    return jsonify({"params": state["params"], "mode": state["mode"]})


@app.route("/api/params", methods=["POST"])
def set_params():
    body = request.get_json(silent=True) or {}
    app_name = body.get("app", state["mode"]).lower()
    params   = body.get("params", {})

    if app_name not in state["params"]:
        return jsonify({"error": "Unknown app"}), 400

    # Merge incoming params
    state["params"][app_name].update(params)

    # Direct hardware control — no ZMQ needed
    apply_hardware_params(app_name, params)

    return jsonify({"ok": True, "app": app_name, "params": state["params"][app_name]})


@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "mode":          state["mode"],
        "zmq_connected": state["zmq_connected"],
        "zmq_ports":     ZMQ_PORTS,
        "control_port":  ZMQ_CONTROL_PORT,
    })


# ── Static file serving ───────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:filename>")
def static_fallback(filename):
    return send_from_directory(STATIC_DIR, filename)


# ── SocketIO events ───────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    print("Client connected:", request.sid)
    # Send current state to newly connected client
    socketio.emit("serverStatus", {"zmq_connected": state["zmq_connected"]}, room=request.sid)
    socketio.emit("modeChanged",  {"mode": state["mode"]},                   room=request.sid)


@socketio.on("disconnect")
def on_disconnect():
    print("Client disconnected:", request.sid)


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Static dir:", STATIC_DIR)
    print("Starting MARP server on {}:{}".format(HTTP_ADDRESS, HTTP_PORT))

# ── ADS-B (PMT messages) ───────────────────────────────
    Thread(
        target=make_adsb_zmq_thread(), 
        daemon=True
    ).start()

    # ── FM (raw float32 stream) ────────────────────────────
    Thread(
        target=make_fm_zmq_thread(ZMQ_PORTS["fm"]),
        daemon=True
    ).start()

    # ── Radar streams (complex64) ──────────────────────────
    Thread(
        target=make_radar_thread(ZMQ_PORTS["radar_ref"], radar_ref_handler),
        daemon=True
    ).start()

    Thread(
        target=make_radar_thread(ZMQ_PORTS["radar_surv"], radar_surv_handler),
        daemon=True
    ).start()

    # ── Radar processing ───────────────────────────────────
    Thread(
        target=radar_processing_thread,
        daemon=True
    ).start()

    socketio.run(app, host=HTTP_ADDRESS, port=HTTP_PORT,
                 debug=True, use_reloader=False)