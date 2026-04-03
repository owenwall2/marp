// ============================================================
//  adsb.js — ADS-B plane tracking module
//  Exposes: ADSB.init(), ADSB.update(plane)
// ============================================================

var ADSB = (function () {

  var map;
  var planes = {};

  // Altitude colormap (rainbow, 1000 ft bands)
  var colormap = [
    '#ff0000','#ff1209','#ff2512','#ff3b1d','#ff4d27','#ff5f30','#ff733b','#ff8344','#ff954e',
    '#ffa457','#ffb260','#f2c16a','#e6cd73','#d8d97c','#cce284','#c0ea8c','#b2f295','#a6f79d',
    '#98fba5','#8cfeac','#80feb3','#72febb','#66fbc1','#58f7c8','#4cf2ce','#40ecd3','#32e2d9',
    '#26d9de','#18cde3','#0cc1e7','#00b4eb','#0da4ef','#1995f2','#2783f5','#3373f8','#3f61fa',
    '#4d4dfb','#593bfd','#6725fe','#7312fe','#7f00ff'
  ];

  var planeIcon = null;

  function init() {
    // Build Leaflet map
    map = L.map('map');
    map.locate({ setView: true });

    var darkTile = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      subdomains: 'abcd', maxZoom: 19
    });
    var voyager = L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      subdomains: 'abcd', maxZoom: 19
    });
    var imagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; Esri'
    });
    var osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
    });

    voyager.addTo(map);
    L.control.layers({
      'CartoDB Dark Matter': darkTile,
      'CartoDB Voyager':     voyager,
      'ESRI World Imagery':  imagery,
      'OpenStreetMap':       osm
    }, {}).addTo(map);

    planeIcon = L.icon({ iconUrl: './img/airliner.png', iconSize: [20, 20] });
  }

  function invalidateSize() {
    if (map) map.invalidateSize();
  }

  function update(plane) {
    if (planes[plane.icao] === undefined) _addPlane(plane);
    else                                   _movePlane(plane);

    document.getElementById('plane-count').textContent = Object.keys(planes).length;
  }

  function _addPlane(plane) {
    var latlng = [plane.latitude, plane.longitude];
    if (Object.keys(planes).length === 0) map.setView(latlng, 9);

    planes[plane.icao] = {};
    planes[plane.icao].marker = L.marker(latlng, {
      icon: planeIcon,
      rotationAngle: -plane.heading,
      rotationOrigin: 'center center'
    }).addTo(map);
    planes[plane.icao].tooltip = L.tooltip(_formatTooltip(plane));
    planes[plane.icao].popup   = L.popup(_formatPopup(plane));
    planes[plane.icao].marker.bindTooltip(planes[plane.icao].tooltip);
    planes[plane.icao].marker.bindPopup(planes[plane.icao].popup);
    planes[plane.icao].track         = L.layerGroup();
    planes[plane.icao].last_location = latlng;
  }

  function _movePlane(plane) {
    var latlng = [plane.latitude, plane.longitude];
    var p = planes[plane.icao];
    p.marker.setLatLng(latlng);
    p.marker.setRotationAngle(-plane.heading);
    p.tooltip.setContent(_formatTooltip(plane));
    p.popup.setContent(_formatPopup(plane));
    p.track.addLayer(L.polyline([p.last_location, latlng], { color: _altColor(plane.altitude) }).addTo(map));
    p.last_location = latlng;
  }

  function _formatTooltip(plane) {
    return plane.icao + ': ' + plane.callsign;
  }

  function _formatPopup(plane) {
    var dt = plane.datetime || new Date(plane.timestamp * 1000).toUTCString();
    return '<table>' +
      '<tr><td><b>ICAO</b></td><td>' + plane.icao + '</td></tr>' +
      '<tr><td><b>Callsign</b></td><td><a href="http://flightaware.com/live/flight/' + plane.callsign + '" target="_blank">' + plane.callsign + '</a></td></tr>' +
      '<tr><td><b>Datetime</b></td><td>' + dt + '</td></tr>' +
      '<tr><td><b>Altitude</b></td><td>' + plane.altitude + ' ft</td></tr>' +
      '<tr><td><b>Vertical Rate</b></td><td>' + plane.vertical_rate + ' ft/min</td></tr>' +
      '<tr><td><b>Speed</b></td><td>' + plane.speed.toFixed(0) + ' kt</td></tr>' +
      '<tr><td><b>Heading</b></td><td>' + plane.heading.toFixed(0) + ' deg</td></tr>' +
      '<tr><td><b>Latitude</b></td><td>' + plane.latitude.toFixed(8) + '</td></tr>' +
      '<tr><td><b>Longitude</b></td><td>' + plane.longitude.toFixed(8) + '</td></tr>' +
      '</table>';
  }

  function _altColor(altitude) {
    if (altitude !== undefined && altitude !== -1) {
      var idx = Math.max(0, Math.min(Math.floor(altitude / 1000), colormap.length - 1));
      return colormap[idx];
    }
    return 'black';
  }

  return { init: init, update: update, invalidateSize: invalidateSize };

})();