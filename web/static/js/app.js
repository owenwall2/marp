// ============================================================
//  app.js — MARP glue layer
//  Owns: SocketIO connection, mode switching, param apply,
//        status pills, sidebar log.
//  Depends on: ADSB, FM, Radar modules (loaded before this)
//  MUST be loaded last.
// ============================================================

(function () {

  var currentApp = 'adsb';

  // ── Init all modules ──────────────────────────────────────
  ADSB.init();
  FM.init();
  Radar.init();

  // ── Socket.IO ─────────────────────────────────────────────
  var socket = io();

  socket.on('connect', function () {
    log('WebSocket connected', 'ok');
    _setWsStatus(true);
  });

  socket.on('disconnect', function () {
    log('WebSocket disconnected', 'err');
    _setWsStatus(false);
  });

  socket.on('serverStatus', function (data) {
    _setZmqStatus(data.zmq_connected);
  });

  // Route incoming data to the correct module
  socket.on('updatePlane', function (data) {
    if (currentApp !== 'adsb') return;
    ADSB.update(data);
  });

  socket.on('updateFM', function (data) {
    // FM audio engine always receives data so buffer stays warm,
    // but visual updates only happen when FM panel is active.
    if (currentApp !== 'fm') return;
    FM.update(data);
  });

  socket.on('updateRadar', function (data) {
    if (currentApp !== 'radar') return;
    Radar.update(data);
  });

  // ── Mode / Sidebar switching ───────────────────────────────
  document.querySelectorAll('.app-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      _switchApp(btn.dataset.app);
    });
  });

  function _switchApp(app) {
    if (app === currentApp) return;

    // Notify current module it's losing focus
    if (currentApp === 'fm') FM.onDeactivate();

    currentApp = app;

    // Update sidebar active state
    document.querySelectorAll('.app-btn').forEach(function (b) {
      b.classList.toggle('active', b.dataset.app === app);
    });

    // Swap visible panel
    document.querySelectorAll('.app-panel').forEach(function (p) {
      p.classList.toggle('active', p.id === 'panel-' + app);
    });

    // Swap param block
    document.querySelectorAll('[id^="params-"]').forEach(function (b) {
      b.style.display = (b.id === 'params-' + app) ? 'block' : 'none';
    });

    // Notify new module it's gaining focus
    if (app === 'adsb')  ADSB.invalidateSize();   // fix Leaflet tile rendering
    if (app === 'fm')    FM.onActivate();

    // Tell the server — so it gates which ZMQ stream to forward
    fetch('/api/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: app })
    })
    .then(function (r) { return r.json(); })
    .then(function ()  { log('Mode → ' + app.toUpperCase(), 'info'); })
    .catch(function (e){ log('Mode switch error: ' + e, 'err'); });
  }

  // ── Parameter Apply ────────────────────────────────────────
  // Wire up APPLY buttons defined in HTML
  var adsbApplyBtn  = document.getElementById('adsb-apply-btn');
  var fmApplyBtn    = document.getElementById('fm-apply-btn');
  var radarApplyBtn = document.getElementById('radar-apply-btn');

  if (adsbApplyBtn)  adsbApplyBtn.addEventListener ('click', function () { _applyParams('adsb');  });
  if (fmApplyBtn)    fmApplyBtn.addEventListener   ('click', function () { _applyParams('fm');    });
  if (radarApplyBtn) radarApplyBtn.addEventListener('click', function () { _applyParams('radar'); });

  function _applyParams(app) {
    var params = {};

    if (app === 'adsb') {
      params = {
        center_freq: parseFloat(document.getElementById('adsb-freq').value) * 1e6,
        gain:        parseFloat(document.getElementById('adsb-gain').value)
      };
    } else if (app === 'fm') {
      params = {
        center_freq: parseFloat(document.getElementById('fm-freq-param').value) * 1e6,
        gain:        parseFloat(document.getElementById('fm-gain').value)
      };
    } else if (app === 'radar') {
      params = {
        center_freq:      parseFloat(document.getElementById('radar-ref-freq').value) * 1e6,
        gain:             parseFloat(document.getElementById('radar-gain').value),
        integration_time: parseFloat(document.getElementById('radar-int-time').value)
      };
    }

  fetch('/api/params', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app: app, params: params })
  })
  .then(function (r) { return r.json(); })
  .then(function (d) {
      if (d.ok) {
          // Green: server accepted + hardware confirmed
          log('Params sent → ' + app.toUpperCase(), 'ok');
          if (d.hw_msg) log(d.hw_msg, 'ok');
      } else {
          // Orange: request reached server but hardware failed
          log('Params sent → ' + app.toUpperCase(), 'ok');
          log(d.hw_msg || d.error || 'Hardware update failed', 'err');
      }
  })
  .catch(function (e) {
      // Red: never reached the server (network drop, double-press race, etc.)
      log('Param send FAILED: ' + e, 'err');
  });
  } 
  

  // ── Status helpers ─────────────────────────────────────────
  function _setWsStatus(connected) {
    var pill = document.getElementById('ws-status');
    var txt  = document.getElementById('ws-status-text');
    pill.classList.toggle('live', connected);
    txt.textContent = connected ? 'WS LIVE' : 'WS DISCONNECTED';
  }

  function _setZmqStatus(connected) {
    var pill = document.getElementById('zmq-status');
    var txt  = document.getElementById('zmq-status-text');
    pill.classList.toggle('live', connected);
    txt.textContent = connected ? 'ZMQ LIVE' : 'ZMQ DISCONNECTED';
  }

  // ── Sidebar log ────────────────────────────────────────────
  function log(msg, type) {
    var el   = document.getElementById('connection-log');
    var line = document.createElement('span');
    line.className   = 'log-line ' + (type || '');
    line.textContent = new Date().toLocaleTimeString('en-US', { hour12: false }) + ' ' + msg;
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
    while (el.children.length > 30) el.removeChild(el.firstChild);
  }

  // Expose log globally so modules can call it if needed
  window.marpLog = log;

})();