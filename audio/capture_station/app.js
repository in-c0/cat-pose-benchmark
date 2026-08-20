const els = {
  config: document.querySelector("#config"),
  location: document.querySelector("#location"),
  objects: document.querySelector("#objects"),
  social: document.querySelector("#social"),
  environment: document.querySelector("#environment"),
  humanAudio: document.querySelector("#human-audio"),
  arm: document.querySelector("#arm"),
  disarm: document.querySelector("#disarm"),
  micState: document.querySelector("#mic-state"),
  start: document.querySelector("#start"),
  captureStatus: document.querySelector("#capture-status"),
  countdown: document.querySelector("#countdown"),
  outcomes: [...document.querySelectorAll(".outcome")],
  refresh: document.querySelector("#refresh"),
  resume: document.querySelector("#resume"),
  records: document.querySelector("#records"),
};

let config = null;
let stream = null;
let audioContext = null;
let recorderNode = null;
let silentGain = null;
let captureWaiter = null;
let activeEvent = null;
let countdownTimer = null;
let lastStatus = null;

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = { error: `HTTP ${response.status}` };
  }
  if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
  return body;
}

async function postJSON(url, payload) {
  return fetchJSON(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function parseJSONField(element, expected, label) {
  let value;
  try {
    value = JSON.parse(element.value);
  } catch (error) {
    throw new Error(`${label} is not valid JSON: ${error.message}`);
  }
  if (expected === "array" && !Array.isArray(value)) {
    throw new Error(`${label} must be a JSON array`);
  }
  if (expected === "object" && (value === null || Array.isArray(value) || typeof value !== "object")) {
    throw new Error(`${label} must be a JSON object`);
  }
  return value;
}

function currentContext() {
  return {
    location: els.location.value.trim() || null,
    objects: parseJSONField(els.objects, "array", "Objects"),
    social: parseJSONField(els.social, "array", "Social"),
    environment: parseJSONField(els.environment, "object", "Environment"),
  };
}

function writeASCII(view, offset, value) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function encodePCM16WAV(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeASCII(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeASCII(view, 8, "WAVE");
  writeASCII(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeASCII(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  let byteOffset = 44;
  for (let index = 0; index < samples.length; index += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[index]));
    const pcm = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    view.setInt16(byteOffset, Math.round(pcm), true);
    byteOffset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function beginFiveSecondCapture() {
  if (!recorderNode || !audioContext) throw new Error("Microphone is not armed");
  if (captureWaiter) throw new Error("An audio capture is already active");

  let resolveStarted;
  let rejectStarted;
  let resolveComplete;
  let rejectComplete;
  const started = new Promise((resolve, reject) => {
    resolveStarted = resolve;
    rejectStarted = reject;
  });
  const complete = new Promise((resolve, reject) => {
    resolveComplete = resolve;
    rejectComplete = reject;
  });
  captureWaiter = {
    resolveStarted,
    rejectStarted,
    resolveComplete,
    rejectComplete,
  };
  recorderNode.port.postMessage({
    type: "start",
    targetFrames: Math.round(audioContext.sampleRate * 5),
  });
  return { started, complete };
}

async function armMicrophone() {
  if (stream) return;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    throw new Error("Microphone capture requires a secure localhost context and getUserMedia support");
  }
  stream = await navigator.mediaDevices.getUserMedia({
    video: false,
    audio: {
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
      channelCount: 1,
    },
  });
  audioContext = new AudioContext();
  await audioContext.audioWorklet.addModule("/recorder-worklet.js");
  await audioContext.resume();
  const source = audioContext.createMediaStreamSource(stream);
  recorderNode = new AudioWorkletNode(audioContext, "a1-pcm-recorder");
  silentGain = audioContext.createGain();
  silentGain.gain.value = 0;
  source.connect(recorderNode);
  recorderNode.connect(silentGain);
  silentGain.connect(audioContext.destination);

  recorderNode.port.onmessage = (event) => {
    const message = event.data || {};
    if (!captureWaiter) return;
    if (message.type === "capture-started") {
      captureWaiter.resolveStarted(message);
      return;
    }
    if (message.type === "capture-complete") {
      captureWaiter.resolveComplete(message);
      captureWaiter = null;
      return;
    }
    if (message.type === "error") {
      const error = new Error(message.message || "AudioWorklet capture error");
      captureWaiter.rejectStarted(error);
      captureWaiter.rejectComplete(error);
      captureWaiter = null;
    }
  };

  els.micState.textContent = `Armed · ${audioContext.sampleRate} Hz mono PCM`;
  els.arm.disabled = true;
  els.disarm.disabled = false;
  els.start.disabled = Boolean(activeEvent);
}

async function disarmMicrophone() {
  if (activeEvent || captureWaiter) throw new Error("Cannot disarm during an active episode/capture");
  for (const track of stream?.getTracks?.() || []) track.stop();
  stream = null;
  recorderNode?.disconnect();
  silentGain?.disconnect();
  recorderNode = null;
  silentGain = null;
  if (audioContext) await audioContext.close();
  audioContext = null;
  els.micState.textContent = "Not armed";
  els.arm.disabled = false;
  els.disarm.disabled = true;
  els.start.disabled = true;
}

function setOutcomeEnabled(enabled) {
  for (const button of els.outcomes) button.disabled = !enabled;
}

function beginOutcomeClock(eventId, t0EpochMs) {
  if (countdownTimer) clearInterval(countdownTimer);
  activeEvent = { eventId, t0EpochMs };
  setOutcomeEnabled(false);
  els.start.disabled = true;

  const tick = () => {
    const elapsed = performance.timeOrigin + performance.now() - t0EpochMs;
    const remaining = Math.max(0, 60000 - elapsed);
    if (remaining > 0) {
      els.countdown.textContent = `Outcome window: ${(remaining / 1000).toFixed(1)} s remaining · ${eventId}`;
      setOutcomeEnabled(false);
    } else {
      els.countdown.textContent = `60 s reached · record terminated / continued / unknown · ${eventId}`;
      setOutcomeEnabled(true);
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  };
  tick();
  countdownTimer = setInterval(tick, 100);
}

async function startEpisode() {
  if (!audioContext || !recorderNode) throw new Error("Arm the microphone first");
  if (activeEvent) throw new Error("An episode is already active");
  if (audioContext.state !== "running") await audioContext.resume();

  const context = currentContext();
  const clickPerf = performance.now();
  const t0EpochMs = performance.timeOrigin + clickPerf;
  const audioTimeAtClick = audioContext.currentTime;
  const capture = beginFiveSecondCapture();
  els.captureStatus.textContent = "Episode t0 frozen. Waiting for first microphone frame…";
  els.start.disabled = true;

  const startRequest = postJSON("/api/start", {
    context,
    client_t0_epoch_ms: t0EpochMs,
    client_clock_uncertainty_ms: 25,
  });

  const [startedEvent, firstAudio] = await Promise.all([startRequest, capture.started]);
  const firstAudioContextSeconds = firstAudio.startFrame / firstAudio.sampleRate;
  const measuredOffsetMs = Math.max(
    0,
    Math.round((firstAudioContextSeconds - audioTimeAtClick) * 1000),
  );
  if (measuredOffsetMs >= config.sensor_cutoff_ms) {
    throw new Error(`Microphone first frame arrived too late (${measuredOffsetMs} ms)`);
  }

  beginOutcomeClock(startedEvent.event_id, t0EpochMs);
  els.captureStatus.textContent =
    `CT1 event ${startedEvent.event_id}\n` +
    `First microphone frame: +${measuredOffsetMs} ms\n` +
    "Reserving A1 evidence and capturing PCM…";

  await postJSON(`/api/reserve-audio/${encodeURIComponent(startedEvent.event_id)}`, {
    first_audio_offset_ms: measuredOffsetMs,
    human_audio_may_be_present: els.humanAudio.checked,
  });

  const completed = await capture.complete;
  const samples = new Float32Array(completed.samples);
  const wav = encodePCM16WAV(samples, completed.sampleRate);
  const upload = await fetchJSON(`/api/audio/${encodeURIComponent(startedEvent.event_id)}`, {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: wav,
  });
  els.captureStatus.textContent =
    `A1 sealed locally · ${startedEvent.event_id}\n` +
    `First microphone frame: +${measuredOffsetMs} ms\n` +
    `WAV: ${upload.media_metadata.duration_seconds.toFixed(3)} s · ${upload.media_metadata.sample_rate_hz} Hz\n` +
    `SHA-256: ${upload.sha256}`;
  await refreshStatus();
}

async function finalizeOutcome(outcome) {
  if (!activeEvent) throw new Error("No active episode");
  setOutcomeEnabled(false);
  const eventId = activeEvent.eventId;
  const result = await postJSON(`/api/finalize/${encodeURIComponent(eventId)}`, { outcome });
  els.countdown.textContent = `Finalized ${eventId} as ${outcome}.`;
  els.captureStatus.textContent +=
    `\nFinalized · A1 enriched event: ${result.a1_enriched_event_written ? "yes" : "no"}`;
  activeEvent = null;
  els.start.disabled = !audioContext;
  await refreshStatus();
}

async function refreshStatus() {
  lastStatus = await fetchJSON("/api/status");
  if (!lastStatus.events.length) {
    els.records.textContent = "No local capture events yet.";
    return;
  }
  els.records.textContent = lastStatus.events
    .map((row) => {
      if (row.integrity_error) return `${row.file}: INTEGRITY ERROR · ${row.integrity_error}`;
      return `${row.event_id}\n  ${row.start_time}\n  finalized=${row.finalized} audio=${row.audio_state || "none"} derived=${row.derived_audio_event}`;
    })
    .join("\n\n");
}

function resumeLatestOpen() {
  const rows = (lastStatus?.events || [])
    .filter((row) => !row.integrity_error && row.finalized === false)
    .sort((a, b) => Date.parse(b.start_time) - Date.parse(a.start_time));
  if (!rows.length) throw new Error("No open local episode to resume");
  const row = rows[0];
  const t0EpochMs = Date.parse(row.start_time);
  beginOutcomeClock(row.event_id, t0EpochMs);
  els.captureStatus.textContent = `Resumed outcome annotation for ${row.event_id}. Existing local audio state: ${row.audio_state || "none"}.`;
}

function reportError(error) {
  console.error(error);
  els.captureStatus.textContent = `ERROR: ${error.message || error}`;
}

els.arm.addEventListener("click", () => armMicrophone().catch(reportError));
els.disarm.addEventListener("click", () => disarmMicrophone().catch(reportError));
els.start.addEventListener("click", () => startEpisode().catch((error) => {
  reportError(error);
  if (!activeEvent) els.start.disabled = !audioContext;
}));
els.refresh.addEventListener("click", () => refreshStatus().catch(reportError));
els.resume.addEventListener("click", () => {
  try { resumeLatestOpen(); } catch (error) { reportError(error); }
});
for (const button of els.outcomes) {
  button.addEventListener("click", () => finalizeOutcome(button.dataset.outcome).catch(reportError));
}

async function init() {
  config = await fetchJSON("/api/config");
  els.config.textContent =
    `subject=${config.subject_id}\nhousehold=${config.household_id}\nsession=${config.session_id}\n` +
    `A1 evidence cutoff=${config.sensor_cutoff_ms} ms · outcome horizon=${config.target_horizon_ms} ms`;
  await refreshStatus();
}

init().catch(reportError);
