import pmt
import time
from gnuradio import gr
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets


class map_plotter(gr.basic_block):

    def __init__(self, home_lat=34.685, home_lon=-82.953):

        gr.basic_block.__init__(
            self,
            name="Map Plotter",
            in_sig=None,
            out_sig=None,
        )

        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

        self.home_lat = home_lat
        self.home_lon = home_lon

        self.planes = {}

        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

        self.win = pg.GraphicsLayoutWidget(title="ADS-B Aircraft Map")
        self.win.resize(900,700)
        self.win.show()

        self.plot = self.win.addPlot()
        self.plot.setLabel('left',"Latitude")
        self.plot.setLabel('bottom',"Longitude")
        self.plot.showGrid(x=True,y=True)

        self.scatter = pg.ScatterPlotItem(size=12)
        self.plot.addItem(self.scatter)

        self.labels = {}

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_map)
        self.timer.start(500)

    def handle_msg(self,msg_pmt):

        try:
            msg = pmt.to_python(msg_pmt)

            if not isinstance(msg,dict):
                return

            callsign = msg.get("callsign",msg.get("icao","UNK"))
            lat = msg.get("lat")
            lon = msg.get("lon")
            alt = msg.get("alt",0)

            if lat is None or lon is None:
                return

            self.planes[callsign] = {
                "lat":lat,
                "lon":lon,
                "alt":alt,
                "time":time.time()
            }

        except Exception:
            pass


    def altitude_color(self,alt):

        if alt < 10000:
            return (0,255,0)

        if alt < 25000:
            return (255,255,0)

        return (255,0,0)


    def update_map(self):

        now = time.time()

        spots = []

        for callsign,data in list(self.planes.items()):

            if now - data["time"] > 30:
                del self.planes[callsign]
                continue

            lat = data["lat"]
            lon = data["lon"]
            alt = data["alt"]

            color = self.altitude_color(alt)

            spots.append({
                "pos":(lon,lat),
                "brush":color
            })

            label = f"{callsign}\n{alt} ft"

            if callsign not in self.labels:
                text = pg.TextItem(label,anchor=(0,1))
                self.plot.addItem(text)
                self.labels[callsign] = text

            self.labels[callsign].setText(label)
            self.labels[callsign].setPos(lon,lat)

        self.scatter.setData(spots)