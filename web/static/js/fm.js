// ============================================================
//  fm.js — FM Radio module
//  Web Audio engine + spectrum display + signal meter
//  Exposes: FM.init(), FM.update(data), FM.onActivate(), FM.onDeactivate()
// ============================================================

var FM = (function () {

  // ── Audio engine state ──────────────────────────────────
  var audioCtx    = null;   // AudioContext — created on first user gesture
  var gainNode    = null;   // master volume
  var isPlaying   = false;  // user intent
  var sampleRate  = 48000;  // must match GNU Radio audio rate

  // Buffer queue — chunks wait here until scheduled
  var audioQueue  = [];
  var nextPlayTime = 0;     // AudioContext time for next chunk
  var MAX_QUEUE   = 20;     // drop oldest if queue blows up
  var TARGET_LATENCY = 0.1; // seconds of pre-roll before first chunk plays

  // ── DOM refs (set in init) ──────────────────────────────
  var playBtn, volSlider, volVal;
  var signalBar, signalVal;
  var bufferBar, bufferVal;
  var freqDisplay, rdsText;
  var specCanvas, specPlaceholder;

  function init() {
    playBtn        = document.getElementById('fm-play-btn');
    volSlider      = document.getElementById('fm-vol-slider');
    volVal         = document.getElementById('fm-vol-val');
    signalBar      = document.getElementById('fm-signal-bar');
    signalVal      = document.getElementById('fm-signal-val');
    bufferBar      = document.getElementById('fm-buffer-bar');
    bufferVal      = document.getElementById('fm-buffer-val');
    freqDisplay    = document.getElementById('fm-freq-display');
    rdsText        = document.getElementById('fm-rds-text');
    specCanvas     = document.getElementById('fm-spectrum-canvas');
    specPlaceholder= document.getElementById('fm-spectrum-placeholder');

    // Play/stop toggle
    playBtn.addEventListener('click', function () {
      if (!isPlaying) _startAudio();
      else            _stopAudio();
    });

    // Volume slider
    volSlider.addEventListener('input', function () {
      var v = parseInt(volSlider.value);
      volVal.textContent = v + '%';
      if (gainNode) gainNode.gain.setTargetAtTime(v / 100, audioCtx.currentTime, 0.05);
    });

    // Animate buffer health bar every 200 ms
    setInterval(_updateBufferUI, 200);
  }

  // ── Called when FM panel becomes active ────────────────
  function onActivate() {
    // Nothing needed — audio continues or waits for PLAY press
  }

  // ── Called when switching away from FM ─────────────────
  function onDeactivate() {
    // Keep audio context alive so it can keep draining;
    // user can explicitly press STOP. No forced stop here.
  }

  // ── Main update — called on every updateFM socket event ─
  function update(data) {
    // 1. Frequency display
    if (data.center_freq !== undefined) {
      var mhz = (data.center_freq / 1e6).toFixed(2);
      freqDisplay.innerHTML = mhz + '<span class="fm-freq-unit">MHz</span>';
    }

    // 2. RDS text
    if (data.rds_station || data.rds_text) {
      rdsText.textContent = [data.rds_station, data.rds_text].filter(Boolean).join(' — ');
    }

    // 3. Signal level meter
    if (data.signal_db !== undefined) {
      var db  = Math.max(-80, Math.min(0, data.signal_db));
      var pct = ((db + 80) / 80 * 100).toFixed(1);
      signalBar.style.width  = pct + '%';
      signalVal.textContent  = db.toFixed(1) + ' dBFS';
    }

    // 4. Spectrum
    if (data.spectrum && Array.isArray(data.spectrum)) {
      _drawSpectrum(data.spectrum);
    }

    // 5. Audio — enqueue PCM chunk if playing
    if (data.audio) {
      _enqueueAudio(data.audio);
    }
  }

  // ── Audio engine ────────────────────────────────────────

  function _startAudio() {
    // AudioContext must be created inside a user gesture
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: sampleRate });
      gainNode = audioCtx.createGain();
      gainNode.gain.value = parseInt(volSlider.value) / 100;
      gainNode.connect(audioCtx.destination);
    }
    if (audioCtx.state === 'suspended') audioCtx.resume();

    isPlaying    = true;
    nextPlayTime = audioCtx.currentTime + TARGET_LATENCY;

    playBtn.textContent = '⏹ STOP';
    playBtn.classList.add('playing');
  }

  function _stopAudio() {
    isPlaying = false;
    audioQueue = [];
    nextPlayTime = 0;
    playBtn.textContent = '▶ PLAY';
    playBtn.classList.remove('playing');
  }

  function _enqueueAudio(base64) {
    if (!isPlaying) return;

    // Decode base64 → Float32Array
    var binary = atob(base64);
    var bytes   = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    var samples = new Float32Array(bytes.buffer);

    // Drop oldest chunks if queue is backed up (keeps latency bounded)
    if (audioQueue.length >= MAX_QUEUE) {
      audioQueue.shift();
    }
    audioQueue.push(samples);

    _drainQueue();
  }

  function _drainQueue() {
    if (!audioCtx || !isPlaying) return;

    while (audioQueue.length > 0) {
      var samples = audioQueue.shift();
      var numFrames = samples.length;

      var buffer = audioCtx.createBuffer(1, numFrames, sampleRate);
      buffer.copyToChannel(samples, 0);

      var src = audioCtx.createBufferSource();
      src.buffer = buffer;
      src.connect(gainNode);

      // Schedule gaplessly
      var startAt = Math.max(nextPlayTime, audioCtx.currentTime);
      src.start(startAt);
      nextPlayTime = startAt + buffer.duration;
    }
  }

  function _updateBufferUI() {
    var depth = audioQueue.length;
    var pct   = Math.min(100, (depth / MAX_QUEUE) * 100);

    // Color shifts: green → yellow → red as buffer fills
    var color = depth < MAX_QUEUE * 0.5  ? 'var(--accent3)'
              : depth < MAX_QUEUE * 0.85 ? '#ffcc00'
              : 'var(--accent2)';

    bufferBar.style.width      = pct + '%';
    bufferBar.style.background = color;
    bufferVal.textContent      = depth + ' chunks';
  }

  // ── Spectrum renderer ────────────────────────────────────

  function _drawSpectrum(bins) {
    specPlaceholder.style.display = 'none';
    specCanvas.style.display      = 'block';

    var ctx = specCanvas.getContext('2d');
    specCanvas.width  = specCanvas.offsetWidth;
    specCanvas.height = specCanvas.offsetHeight;
    var w = specCanvas.width, h = specCanvas.height;
    var MIN_DB = -80, MAX_DB = 0;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0d1520';
    ctx.fillRect(0, 0, w, h);

    // Grid lines
    ctx.strokeStyle = '#1a2d44'; ctx.lineWidth = 1;
    for (var i = 0; i <= 4; i++) {
      var gy = (i / 4) * h;
      ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(w, gy); ctx.stroke();
    }

    // dB labels
    ctx.fillStyle = '#4a6a88';
    ctx.font = '9px Share Tech Mono, monospace';
    ctx.textAlign = 'left';
    var dbLabels = [0, -20, -40, -60, -80];
    dbLabels.forEach(function (db) {
      var ly = ((db - MAX_DB) / (MIN_DB - MAX_DB)) * h;
      ctx.fillText(db + 'dB', 4, ly + 10);
    });

    // Spectrum fill + line
    function binToY(v) {
      var norm = Math.max(0, Math.min(1, (v - MIN_DB) / (MAX_DB - MIN_DB)));
      return h - norm * h;
    }

    var grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0,   '#00d4ff');
    grad.addColorStop(1,   'rgba(0,212,255,0.08)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(0, h);
    bins.forEach(function (v, i) {
      var x = (i / (bins.length - 1)) * w;
      ctx.lineTo(x, binToY(v));
    });
    ctx.lineTo(w, h);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = '#00d4ff'; ctx.lineWidth = 1.5;
    ctx.beginPath();
    bins.forEach(function (v, i) {
      var x = (i / (bins.length - 1)) * w;
      if (i === 0) ctx.moveTo(x, binToY(v));
      else         ctx.lineTo(x, binToY(v));
    });
    ctx.stroke();
  }

  return { init: init, update: update, onActivate: onActivate, onDeactivate: onDeactivate };

})();