// ============================================================
//  radar.js — Passive Radar module
//
//  Server emits "updateRadar" with:
//    data.map          — 2D array [doppler_rows][delay_cols], dB values
//                        rows = Doppler bins (downsampled x2 from num_blocks=64 → 32 rows)
//                        cols = delay bins   (downsampled x4 from nfft_delay=2047 → ~512 cols)
//    data.range_axis   — bistatic path difference in metres, one entry per col
//    data.doppler_bins — Doppler bin numbers, one entry per row
//
//  Matches plot_samples.py orientation:
//    X axis = Bistatic Path Difference (m)   [delay cols, left→right]
//    Y axis = Doppler bin                     [doppler rows, bottom→top, origin=lower]
//
//  Exposes: Radar.init(), Radar.update(data)
// ============================================================

var Radar = (function () {

  // Persistent colour scale — stabilises across frames like plot_samples' vmin/vmax
  var _globalMin  = null;
  var _globalMax  = null;
  var _frameCount = 0;
  var _WARM_FRAMES = 5;

  var _canvas = null;
  var _ctx    = null;

  // ── Public: init ───────────────────────────────────────────
  function init() {
    _canvas = document.getElementById('rd-canvas');
    _ctx    = _canvas.getContext('2d');
  }

  // ── Public: update ─────────────────────────────────────────
  function update(data) {
    if (!data.map || !Array.isArray(data.map) || data.map.length === 0) return;

    var matrix      = data.map;
    var rangeAxis   = data.range_axis   || null;
    var dopplerBins = data.doppler_bins || null;

    // Update global colour scale
    var flat     = [].concat.apply([], matrix);
    var frameMin = Math.min.apply(null, flat);
    var frameMax = Math.max.apply(null, flat);

    if (_globalMin === null) {
      _globalMin = frameMin;
      _globalMax = frameMax;
    } else {
      _globalMin = Math.min(_globalMin, frameMin);
      _globalMax = Math.max(_globalMax, frameMax);
    }
    _frameCount++;

    // Hide placeholder, update frame counter in title bar
    var ph = document.getElementById('rd-placeholder');
    if (ph) ph.style.display = 'none';

    var lbl = document.getElementById('radar-frame-label');
    if (lbl) lbl.textContent = 'FRAME ' + _frameCount;

    _drawHeatmap(matrix, rangeAxis, dopplerBins);
  }

  // ── Heatmap renderer ───────────────────────────────────────
  function _drawHeatmap(matrix, rangeAxis, dopplerBins) {
    // Sync canvas pixel size to CSS layout size
    var cssW = _canvas.offsetWidth  || 800;
    var cssH = _canvas.offsetHeight || 420;
    if (_canvas.width !== cssW || _canvas.height !== cssH) {
      _canvas.width  = cssW;
      _canvas.height = cssH;
    }

    var W = _canvas.width;
    var H = _canvas.height;

    var numRows = matrix.length;       // Doppler axis  (32 after x2 downsample)
    var numCols = matrix[0].length;    // Delay axis    (~512 after x4 downsample)

    var vmin   = _globalMin;
    var vmax   = _globalMax;
    var vrange = vmax - vmin || 1;

    // Layout margins
    var ML = 58,  MR = 52,  MT = 12,  MB = 38;
    var plotW = W - ML - MR;
    var plotH = H - MT - MB;

    // ── Render pixel data ──────────────────────────────────
    var imgData = _ctx.createImageData(plotW, plotH);

    for (var py = 0; py < plotH; py++) {
      // origin='lower' — py=0 is top of canvas, maps to highest row index
      var rowIdx = Math.round(((plotH - 1 - py) / (plotH - 1)) * (numRows - 1));
      rowIdx = Math.max(0, Math.min(rowIdx, numRows - 1));

      for (var px = 0; px < plotW; px++) {
        var colIdx = Math.round((px / (plotW - 1)) * (numCols - 1));
        colIdx = Math.max(0, Math.min(colIdx, numCols - 1));

        var norm = Math.max(0, Math.min(1, (matrix[rowIdx][colIdx] - vmin) / vrange));

        // Viridis colormap (matches matplotlib default)
        var r, g, b;
        if (norm < 0.25) {
          var t = norm / 0.25;
          r = Math.round(68  + t * (59  - 68));
          g = Math.round(1   + t * (82  - 1));
          b = Math.round(84  + t * (139 - 84));
        } else if (norm < 0.5) {
          var t = (norm - 0.25) / 0.25;
          r = Math.round(59  + t * (33  - 59));
          g = Math.round(82  + t * (145 - 82));
          b = Math.round(139 + t * (140 - 139));
        } else if (norm < 0.75) {
          var t = (norm - 0.5) / 0.25;
          r = Math.round(33  + t * (94  - 33));
          g = Math.round(145 + t * (201 - 145));
          b = Math.round(140 + t * (98  - 140));
        } else {
          var t = (norm - 0.75) / 0.25;
          r = Math.round(94  + t * (253 - 94));
          g = Math.round(201 + t * (231 - 201));
          b = Math.round(98  + t * (37  - 98));
        }

        var idx = (py * plotW + px) * 4;
        imgData.data[idx]     = r;
        imgData.data[idx + 1] = g;
        imgData.data[idx + 2] = b;
        imgData.data[idx + 3] = 255;
      }
    }

    // ── Composite ──────────────────────────────────────────
    _ctx.fillStyle = '#090d12';
    _ctx.fillRect(0, 0, W, H);

    // Blit pixel data via offscreen canvas (avoids putImageData offset bug)
    var tmp = document.createElement('canvas');
    tmp.width  = plotW;
    tmp.height = plotH;
    tmp.getContext('2d').putImageData(imgData, 0, 0);
    _ctx.drawImage(tmp, ML, MT);

    // Plot border
    _ctx.strokeStyle = '#1a2d44';
    _ctx.lineWidth   = 1;
    _ctx.strokeRect(ML, MT, plotW, plotH);

    // ── X axis — Bistatic Path Difference (m) ─────────────
    var xTicks = 8;
    _ctx.font      = '10px Share Tech Mono, monospace';
    _ctx.fillStyle = '#4a6a88';
    for (var i = 0; i <= xTicks; i++) {
      var frac = i / xTicks;
      var xPx  = ML + frac * plotW;

      _ctx.beginPath();
      _ctx.strokeStyle = '#4a6a88';
      _ctx.moveTo(xPx, MT + plotH);
      _ctx.lineTo(xPx, MT + plotH + 5);
      _ctx.stroke();

      var label;
      if (rangeAxis && rangeAxis.length > 0) {
        var ci = Math.round(frac * (rangeAxis.length - 1));
        label  = rangeAxis[ci].toFixed(0);
      } else {
        label = (frac * numCols).toFixed(0);
      }
      _ctx.textAlign = 'center';
      _ctx.fillText(label, xPx, MT + plotH + 18);
    }

    // X axis title
    _ctx.fillStyle = '#c8ddef';
    _ctx.font      = '11px Barlow Condensed, sans-serif';
    _ctx.textAlign = 'center';
    _ctx.fillText('Bistatic Path Difference (m)', ML + plotW / 2, H - 4);

    // ── Y axis — Doppler bin ───────────────────────────────
    var yTicks = 6;
    _ctx.font = '10px Share Tech Mono, monospace';
    for (var i = 0; i <= yTicks; i++) {
      var frac = i / yTicks;
      // origin=lower: frac 0→bottom, frac 1→top
      var yPx  = MT + plotH - frac * plotH;

      _ctx.beginPath();
      _ctx.strokeStyle = '#4a6a88';
      _ctx.moveTo(ML - 5, yPx);
      _ctx.lineTo(ML,     yPx);
      _ctx.stroke();

      var label;
      if (dopplerBins && dopplerBins.length > 0) {
        var ri = Math.round(frac * (dopplerBins.length - 1));
        label  = dopplerBins[ri].toString();
      } else {
        label = Math.round(frac * numRows - numRows / 2).toString();
      }
      _ctx.textAlign = 'right';
      _ctx.fillStyle = '#4a6a88';
      _ctx.fillText(label, ML - 8, yPx + 4);
    }

    // Y axis title — rotated
    _ctx.save();
    _ctx.translate(12, MT + plotH / 2);
    _ctx.rotate(-Math.PI / 2);
    _ctx.textAlign = 'center';
    _ctx.fillStyle = '#c8ddef';
    _ctx.font      = '11px Barlow Condensed, sans-serif';
    _ctx.fillText('Doppler Bin', 0, 0);
    _ctx.restore();

    // ── Colourbar ─────────────────────────────────────────
    var cbX = ML + plotW + 8;
    var cbW = 12;
    _drawColourbar(cbX, MT, cbW, plotH, vmin, vmax);
  }

  function _drawColourbar(x, y, w, h, vmin, vmax) {
    var grad = _ctx.createLinearGradient(x, y + h, x, y);  // bottom → top = low → high
    grad.addColorStop(0,    'rgb(68,1,84)');
    grad.addColorStop(0.25, 'rgb(59,82,139)');
    grad.addColorStop(0.5,  'rgb(33,145,140)');
    grad.addColorStop(0.75, 'rgb(94,201,98)');
    grad.addColorStop(1,    'rgb(253,231,37)');

    _ctx.fillStyle = grad;
    _ctx.fillRect(x, y, w, h);
    _ctx.strokeStyle = '#1a2d44';
    _ctx.strokeRect(x, y, w, h);

    // Tick labels
    _ctx.font      = '9px Share Tech Mono, monospace';
    _ctx.fillStyle = '#4a6a88';
    _ctx.textAlign = 'left';
    var ticks = [0, 0.25, 0.5, 0.75, 1.0];
    ticks.forEach(function (t) {
      var labelY = y + h - t * h;
      var db     = vmin + t * (vmax - vmin);
      _ctx.fillText(db.toFixed(0) + 'dB', x + w + 3, labelY + 3);
    });
    // Unit label above bar
    _ctx.fillText('dB', x, y - 3);
  }

  return { init: init, update: update };

})();