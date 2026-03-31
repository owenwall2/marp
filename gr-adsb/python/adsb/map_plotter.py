import pmt
import math
import threading
from gnuradio import gr
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets


class map_plotter(gr.basic_block):
    """
    MARP Live 2D Aerial Map
    Receives ADS-B position messages and plots planes on a pyqtgraph map.
    Works with gr-adsb Decoder over xQuartz on Mac.
    """
    def __init__(self, home_lat=34.685, home_lon=-82.953):
        gr.basic_block.__init__(self, name="Aerial Map", in_sig=None, out_sig=None)

        self.home_lat = home_lat
        self.home_lon = home_lon
        self.planes   = {}   # icao -> (lat, lon, alt, callsign)
        self.labels   = {}   # icao -> pg.TextItem
        self.lock     = threading.Lock()

        # Register GNURadio message port
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

        # Only create QApplication if one doesn't already exist
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

        self.win = pg.GraphicsLayoutWidget(title="MARP Plane Tracker - Live 2D Aerial Map")
        self.win.resize(900, 700)
        self.win.show()

        self.plot = self.win.addPlot(title="Live Planes (1090 MHz ADS-B)")
        self.plot.setLabels(left="Latitude (°)", bottom="Longitude (°)")
        self.plot.setXRange(home_lon - 1.5, home_lon + 1.5)
        self.plot.setYRange(home_lat - 1.5, home_lat + 1.5)
        self.plot.showGrid(x=True, y=True)

        # Red dots for planes, green dot for home
        self.scatter = pg.ScatterPlotItem(
            size=10, pen=pg.mkPen(None), brush=pg.mkBrush(255, 50, 50, 220)
        )
        self.home_dot = pg.ScatterPlotItem(
            size=12, pen=pg.mkPen(None), brush=pg.mkBrush(0, 255, 0, 255)
        )
        self.plot.addItem(self.scatter)
        self.plot.addItem(self.home_dot)
        self.home_dot.setData([home_lon], [home_lat])

    def handle_msg(self, msg_pmt):
        """Called by GNURadio scheduler each time ADS-B Decoder sends a message."""
        try:
            car = pmt.to_python(pmt.car(msg_pmt)) if pmt.is_pair(msg_pmt) else pmt.to_python(msg_pmt)

            if not isinstance(car, dict):
                return

            lat      = car.get("latitude")
            lon      = car.get("longitude")
            alt      = car.get("altitude", 0)
            icao     = car.get("icao", "????")
            callsign = (car.get("callsign") or icao).strip()

            # Skip messages with no valid position
            if lat is None or lon is None:
                return
            if math.isnan(float(lat)) or math.isnan(float(lon)):
                return

            with self.lock:
                self.planes[icao] = (float(lat), float(lon), alt, callsign)

            # Redraw and pump Qt event loop from this thread
            self.update_map()
            self.app.processEvents()

        except Exception as e:
            import traceback
            with open("/tmp/map_plotter_debug.log", "a") as f:
                f.write(f"ERROR: {e}\n{traceback.format_exc()}\n")

    def update_map(self):
        """Redraw scatter plot and labels."""
        with self.lock:
            snapshot = dict(self.planes)

        if not snapshot:
            return

        lons = [v[1] for v in snapshot.values()]
        lats = [v[0] for v in snapshot.values()]
        self.scatter.setData(lons, lats)

        current_icaos = set(snapshot.keys())

        # Remove stale labels
        for icao in list(self.labels.keys()):
            if icao not in current_icaos:
                self.plot.removeItem(self.labels.pop(icao))

        # Add/update labels
        for icao, (lat, lon, alt, callsign) in snapshot.items():
            # Short label to avoid overlap: callsign + altitude on one line
            short = callsign[:8] if callsign else icao[:6]
            label_text = f"{short} {int(alt)}ft" if alt else short
            if icao not in self.labels:
                txt = pg.TextItem(label_text, color=(255, 255, 100), anchor=(0, 1))
                txt.setFont(QtCore.QFont("Arial", 7))
                self.plot.addItem(txt)
                self.labels[icao] = txt
            else:
                self.labels[icao].setText(label_text)
            self.labels[icao].setPos(lon + 0.01, lat)