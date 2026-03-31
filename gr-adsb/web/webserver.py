#!/usr/bin/env python3
from gevent import monkey
monkey.patch_all()

import time
import os
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO
from threading import Thread
import zmq.green as zmq

import json

# Try to import pmt, but don't crash if it's missing
try:
    import pmt
    HAS_PMT = True
except ImportError:
    print("WARNING: pmt not available, ZMQ messages will be raw bytes")
    HAS_PMT = False

HTTP_ADDRESS = "0.0.0.0"
HTTP_PORT    = 5000
ZMQ_ADDRESS  = "127.0.0.1"   # same container = localhost
ZMQ_PORT     = 5001

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')



def zmq_thread():
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE, b"")
    socket.connect("tcp://{:s}:{:d}".format(ZMQ_ADDRESS, ZMQ_PORT))
    print("ZMQ thread started, connected to tcp://{}:{}".format(ZMQ_ADDRESS, ZMQ_PORT))

    while True:
        try:
            pdu_bin = socket.recv()
            print("Received ZMQ message ({} bytes)".format(len(pdu_bin)))

            if HAS_PMT:
                pdu   = pmt.deserialize_str(pdu_bin)
                plane = pmt.to_python(pmt.car(pdu))
            else:
                # Fallback: emit raw for debugging
                plane = {"raw": pdu_bin.hex()}

            print(plane)
            socketio.emit("updatePlane", plane)

        except Exception as e:
            print("ZMQ error:", e)
            time.sleep(1)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

# Catch-all for assets referenced without /static/ prefix (e.g. /js/map.js)
@app.route("/<path:filename>")
def static_fallback(filename):
    return send_from_directory(STATIC_DIR, filename)


@socketio.on("connect")
def connect():
    print("Client connected", request.sid)


@socketio.on("disconnect")
def disconnect():
    print("Client disconnected", request.sid)


if __name__ == "__main__":
    print("Static dir:", STATIC_DIR)
    print("Starting server on {}:{}".format(HTTP_ADDRESS, HTTP_PORT))

    thread = Thread(target=zmq_thread)
    thread.daemon = True
    thread.start()

    socketio.run(app, host=HTTP_ADDRESS, port=HTTP_PORT,
                 debug=True, use_reloader=False)