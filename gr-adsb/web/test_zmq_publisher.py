
import zmq

import time

import json

context = zmq.Context()

socket = context.socket(zmq.PUB)

socket.bind("tcp://127.0.0.1:5001")

# Give subscriber time to connect

time.sleep(1)

planes = [

    {

        'snr': 18.5, 'df': 17, 'icao': 'ab69dc',

        'datetime': '2026-03-27 18:02:36.583059 UTC',

        'timestamp': 1774634556.583059, 'num_msgs': 11,

        'longitude': -82.794, 'latitude': 34.623,

        'vertical_rate': 0, 'heading': 60.8,

        'speed': 108.7, 'altitude': 2950, 'callsign': 'DAL123'

    },

    {

        'snr': 20.5, 'df': 17, 'icao': 'ac7103',

        'datetime': '2026-03-27 18:02:39.275190 UTC',

        'timestamp': 1774634559.275, 'num_msgs': 5,

        'longitude': -82.810, 'latitude': 34.651,

        'vertical_rate': 768, 'heading': 145.5,

        'speed': 432.9, 'altitude': 35000, 'callsign': 'UAL456'

    }

]

print("Sending fake plane data every 2 seconds... (Ctrl+C to stop)")

while True:

    for plane in planes:

        # Shift position slightly each loop to animate on map

        plane['longitude'] += 0.001

        plane['latitude']  += 0.001

        socket.send_json(plane)

        print("Sent:", plane['icao'], plane['callsign'],

              plane['latitude'], plane['longitude'])

        time.sleep(2)

