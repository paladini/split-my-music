(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = { cfg: null, file: null, goal: 'vocals_music', model: null, format: 'wav', outputs: [], lastModelId: null, timer: null, poll: null, startedAt: 0 };
  const LIGHT_MODEL = 'uvr_mdx_inst_hq_3';
  const STAGE_ORDER = ['uploading', 'preparing', 'downloading_model', 'separating', 'exporting'];

  function el(tag, props, children) {
    const n = document.createElement(tag);
    Object.entries(props || {}).forEach(([k, v]) => {
      if (k === 'text') n.textContent = v;
      else if (k === 'class') n.className = v;
      else n.setAttribute(k, v);
    });
    (children || []).forEach((c) => n.appendChild(c));
    return n;
  }
  function fmtSize(b) { return b > 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB'; }
  function fmtTime(s) { s = Math.floor(s); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); }
  function show(id) { ['setup', 'progress', 'results', 'errorBox', 'emptyBox'].forEach((s) => { $(s).hidden = s !== id; }); }
  function goalObj(id) { return state.cfg.goals.find((g) => g.id === id); }
  function modelObj(id) { return state.cfg.models.find((m) => m.id === id); }
  function trackLabel(id) { return state.cfg.tracks[id].label; }

  /* ---------- setup ---------- */
  async function init() {
    try {
      const r = await fetch('/api/config');
      state.cfg = await r.json();
    } catch (e) {
      showError({ message: 'Could not reach the Split My Music server.', suggestion: 'Check that the server is running, then reload this page.' }, false);
      return;
    }
    const hw = state.cfg.hardware;
    $('deviceBadge').textContent = 'Processing on: ' + hw.device_label;
    $('limitMb').textContent = state.cfg.limits.max_upload_mb;
    $('limitMin').textContent = state.cfg.limits.max_duration_minutes;
    $('retention').textContent = state.cfg.limits.retention_hours;
    renderGoals();
    renderFormats();
    selectGoal(state.goal);
    updateStart();
  }

  function renderGoals() {
    const box = $('goals');
    box.textContent = '';
    state.cfg.goals.forEach((g) => {
      const input = el('input', { type: 'radio', name: 'goal', value: g.id });
      input.addEventListener('change', () => selectGoal(g.id));
      box.appendChild(el('label', { class: 'goal' }, [input, el('strong', { text: g.label }), el('span', { text: g.description })]));
    });
  }

  function renderFormats() {
    const box = $('formats');
    box.textContent = '';
    state.cfg.output_formats.forEach((f) => {
      const input = el('input', { type: 'radio', name: 'format', value: f.id });
      input.checked = f.id === state.format;
      input.addEventListener('change', () => { state.format = f.id; formatHelp(); });
      box.appendChild(el('label', { class: 'seg' }, [input, el('span', { text: f.label })]));
    });
    formatHelp();
  }
  function formatHelp() {
    const f = state.cfg.output_formats.find((x) => x.id === state.format);
    $('formatHelp').textContent = f.description;
  }

  function selectGoal(id) {
    state.goal = id;
    document.querySelectorAll('input[name=goal]').forEach((i) => { i.checked = i.value === id; });
    state.model = goalObj(id).default_model_id;
    renderModels();
    renderTracks();
  }

  function renderModels() {
    const sel = $('modelSelect');
    sel.textContent = '';
    state.cfg.models.forEach((m) => {
      const o = el('option', { value: m.id, text: m.name });
      if (m.id === state.model) o.selected = true;
      sel.appendChild(o);
    });
    sel.onchange = () => {
      state.model = sel.value;
      const m = modelObj(sel.value);
      if (m.goal !== state.goal) {
        state.goal = m.goal;
        document.querySelectorAll('input[name=goal]').forEach((i) => { i.checked = i.value === m.goal; });
      }
      renderTracks();
      modelInfo();
    };
    modelInfo();
  }

  function modelInfo() {
    const m = modelObj(state.model);
    const box = $('modelInfo');
    box.textContent = '';
    box.appendChild(el('div', { text: m.description }));
    const tags = el('div');
    tags.appendChild(el('span', { class: 'tag ' + (m.cached ? 'ok' : 'warn'), text: m.cache_status }));
    tags.appendChild(el('span', { class: 'tag neutral', text: m.architecture }));
    const gpuOnly = m.recommended_device === 'gpu_recommended';
    tags.appendChild(el('span', { class: 'tag ' + (gpuOnly ? 'warn' : 'ok'), text: gpuOnly ? 'GPU recommended (slow on CPU)' : 'Works on CPU and GPU' }));
    box.appendChild(tags);
    box.appendChild(el('div', { class: 'muted', text: 'Files it can create: ' + m.outputs.map(trackLabel).join(', ') + '. License: ' + m.license_note }));
  }

  function renderTracks() {
    const m = modelObj(state.model);
    const box = $('tracks');
    box.textContent = '';
    state.outputs = m.outputs.slice();
    m.outputs.forEach((t) => {
      const input = el('input', { type: 'checkbox', value: t });
      input.checked = true;
      input.addEventListener('change', () => {
        state.outputs = Array.from(box.querySelectorAll('input:checked')).map((i) => i.value);
        updateStart();
      });
      box.appendChild(el('label', { class: 'pill', title: state.cfg.tracks[t].description }, [input, el('span', { text: trackLabel(t) })]));
    });
    updateStart();
  }

  /* ---------- file ---------- */
  const dz = $('dropzone'), fi = $('fileInput');
  dz.addEventListener('click', () => fi.click());
  dz.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fi.click(); } });
  ['dragenter', 'dragover'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add('over'); }));
  ['dragleave', 'drop'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove('over'); }));
  dz.addEventListener('drop', (e) => { if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); });
  fi.addEventListener('change', () => { if (fi.files[0]) setFile(fi.files[0]); });

  function setFile(f) {
    const info = $('fileInfo');
    info.hidden = false;
    const ext = (f.name.split('.').pop() || '').toLowerCase();
    const okExt = ['mp3', 'wav', 'flac', 'm4a', 'aac', 'ogg', 'opus'].includes(ext);
    info.classList.remove('bad');
    state.file = null;
    if (!okExt) {
      info.classList.add('bad');
      info.textContent = 'That file type is not supported. Please choose an MP3, WAV, FLAC, M4A, AAC, OGG or OPUS file.';
    } else if (f.size === 0) {
      info.classList.add('bad');
      info.textContent = 'That file is empty. Please choose another one.';
    } else if (f.size > state.cfg.limits.max_upload_mb * 1048576) {
      info.classList.add('bad');
      info.textContent = 'That file is ' + fmtSize(f.size) + ', which is over the ' + state.cfg.limits.max_upload_mb + ' MB limit.';
    } else {
      state.file = f;
      info.textContent = 'Selected: ' + f.name + ' (' + fmtSize(f.size) + ')';
      $('dropMain').textContent = 'Change song';
    }
    updateStart();
  }

  function updateStart() {
    const btn = $('startBtn'), hint = $('startHint');
    let msg = '';
    if (!state.file) msg = 'Choose a song to begin.';
    else if (!state.outputs.length) msg = 'Pick at least one file you want to get.';
    btn.disabled = !!msg;
    hint.textContent = msg;
  }

  /* ---------- run ---------- */
  $('form').addEventListener('submit', (e) => { e.preventDefault(); start(); });

  function setStage(stage, message) {
    const idx = STAGE_ORDER.indexOf(stage);
    document.querySelectorAll('#stages li').forEach((li) => {
      const i = STAGE_ORDER.indexOf(li.dataset.stage);
      li.classList.remove('done', 'active', 'skipped');
      if (idx < 0) return;
      if (i < idx) li.classList.add('done');
      else if (i === idx) li.classList.add('active');
    });
    if (message) $('stageMsg').textContent = message;
  }

  function tick() { $('elapsed').textContent = fmtTime((Date.now() - state.startedAt) / 1000); }

  function start() {
    if (!state.file) return;
    state.lastModelId = state.model;
    show('progress');
    $('uploadBarWrap').hidden = false;
    $('uploadBar').style.width = '0%';
    setStage('uploading', 'Uploading your song…');
    state.startedAt = Date.now();
    clearInterval(state.timer);
    state.timer = setInterval(tick, 1000);
    tick();
    $('progTitle').focus && $('progTitle').setAttribute('tabindex', '-1');
    $('progTitle').focus();

    const fd = new FormData();
    fd.append('file', state.file);
    fd.append('goal', state.goal);
    fd.append('model', state.model);
    fd.append('outputs', state.outputs.join(','));
    fd.append('output_format', state.format);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/jobs');
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) $('uploadBar').style.width = Math.round((ev.loaded / ev.total) * 100) + '%';
    };
    xhr.onerror = () => fail({ message: 'The upload was interrupted.', suggestion: 'Check your connection to the server and try again.' });
    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText); } catch (e) { /* ignore */ }
      if (xhr.status === 202) {
        $('uploadBarWrap').hidden = true;
        poll(body.id);
      } else {
        fail(body.error || { message: 'The server could not accept this file.', suggestion: 'Try again with another file.' });
      }
    };
    xhr.send(fd);
  }

  function poll(id) {
    clearInterval(state.poll);
    const run = async () => {
      let job;
      try {
        const r = await fetch('/api/jobs/' + id);
        job = await r.json();
        if (!r.ok) throw job;
      } catch (e) {
        return; // transient; try again on next tick
      }
      if (job.status === 'completed') { clearInterval(state.poll); finish(job); }
      else if (job.status === 'failed') { clearInterval(state.poll); fail(job.error); }
      else setStage(job.stage === 'queued' ? 'uploading' : job.stage, job.stage === 'queued' ? 'Waiting for your turn in the queue…' : job.stage_message);
    };
    run();
    state.poll = setInterval(run, 1500);
  }

  function fail(err) {
    clearInterval(state.timer);
    clearInterval(state.poll);
    showError(err || {}, true);
  }

  function showError(err, canRetry) {
    $('errMsg').textContent = err.message || 'Something went wrong.';
    $('errHint').textContent = err.suggestion || '';
    $('errHint').hidden = !err.suggestion;
    $('retryBtn').hidden = !canRetry || !state.file;
    const heavy = state.lastModelId && state.lastModelId !== LIGHT_MODEL && ['OUT_OF_MEMORY', 'DEVICE_INCOMPATIBLE', 'PROCESSING_FAILED', 'MODEL_LOAD_FAILED', 'MODEL_DOWNLOAD_FAILED'].includes(err.code);
    $('lightBtn').hidden = !heavy;
    show('errorBox');
    $('errTitle').setAttribute('tabindex', '-1');
    $('errTitle').focus();
  }

  function finish(job) {
    clearInterval(state.timer);
    if (!job.files.length) { show('emptyBox'); return; }
    $('resMeta').textContent = 'Finished in ' + fmtTime(job.elapsed_seconds || 0) + ' · ' + job.model.name + ' · ' + job.files[0].format_label;
    $('zipBtn').href = job.zip_url;
    const list = $('trackList');
    list.textContent = '';
    job.files.forEach((f) => {
      const audio = el('audio', { controls: '', preload: 'none', src: f.stream_url, 'aria-label': 'Play ' + f.label });
      audio.addEventListener('play', () => document.querySelectorAll('#trackList audio').forEach((a) => { if (a !== audio) a.pause(); }));
      const dl = el('a', { class: 'btn ghost small', href: f.download_url, text: 'Download', 'aria-label': 'Download ' + f.label });
      list.appendChild(el('article', { class: 'track' }, [
        el('div', {}, [el('h3', { text: f.label }), el('div', { class: 'meta', text: f.description + ' · ' + f.format_label + ' · ' + fmtSize(f.size_bytes) })]),
        dl, audio,
      ]));
    });
    show('results');
    $('resTitle').setAttribute('tabindex', '-1');
    $('resTitle').focus();
  }

  function reset(clearFile) {
    if (clearFile) {
      state.file = null; fi.value = ''; $('fileInfo').hidden = true; $('dropMain').textContent = 'Drop an audio file here, or browse';
    }
    // refresh cache badges after a run
    fetch('/api/config').then((r) => r.json()).then((c) => { state.cfg = c; modelInfo(); }).catch(() => {});
    show('setup');
    updateStart();
  }

  $('againBtn').addEventListener('click', () => reset(true));
  $('emptyBtn').addEventListener('click', () => reset(true));
  $('otherBtn').addEventListener('click', () => reset(true));
  $('retryBtn').addEventListener('click', () => start());
  $('lightBtn').addEventListener('click', () => { selectGoal('vocals_music'); $('modelSelect').value = LIGHT_MODEL; start(); });

  init();
})();
