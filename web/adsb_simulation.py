#!/usr/bin/env python3
import zmq
import time
import pmt

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://127.0.0.1:5001")
time.sleep(1.0)

print("Clean MARP ADS-B Simulator — PDU cons pair (matches real gr-iio-marp flowgraph)")

base_planes = [
    {
        "icao": "ab69dc",
        "callsign": "DAL123",
        "latitude": 34.623,
        "longitude": -82.794,
        "altitude": 2950,
        "heading": 60.8,
        "speed": 108.7,
        "vertical_rate": 0
    },
    {
        "icao": "ac7103",
        "callsign": "UAL456",
        "latitude": 34.651,
        "longitude": -82.810,
        "altitude": 35000,
        "heading": 145.5,
        "speed": 432.9,
        "vertical_rate": 768
    }
]

while True:
    for plane in base_planes:
        plane["latitude"]  += 0.0012
        plane["longitude"] += 0.0018
        plane["timestamp"] = time.time()
        plane["datetime"]  = time.strftime("%Y-%m-%d %H:%M:%S UTC")

        # === Match real GNU Radio PDU format: cons(metadata_dict, data_vector) ===
        metadata = pmt.to_pmt({k: v for k, v in plane.items() if k != "datetime"})
        pdu = pmt.cons(metadata, pmt.make_u8vector(0, 0))

        serialized = pmt.serialize_str(pdu)
        socket.send(serialized)
        print(f"Sent PDU → {plane['icao']} {plane['callsign']} @ {plane['latitude']:.4f}, {plane['longitude']:.4f}")

    time.sleep(1.8)