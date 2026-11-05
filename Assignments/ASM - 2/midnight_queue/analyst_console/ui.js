"use strict";
/* Interface layer: synthesized sound feedback, a trailing cursor, and keyboard shortcuts.
   Everything here is additive — the console stays fully usable if this file fails to load. */
(() => {
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = matchMedia("(pointer: fine)");
  const canHover = matchMedia("(hover: hover)");

  /* ── sound ───────────────────────────────────────────────────────────── */

  const STORE_KEY = "mq-sound";
  const AMBIENCE_LEVEL_KEY = "mq-ambience-level";
  let enabled = true;
  let ambienceEnabled = false;
  let ambienceLevel = 0.32;
  try { enabled = localStorage.getItem(STORE_KEY) !== "off"; } catch (_) { /* storage blocked */ }
  try {
    const savedLevel = localStorage.getItem(AMBIENCE_LEVEL_KEY);
    if (savedLevel !== null) {
      const parsedLevel = Number(savedLevel);
      if (Number.isFinite(parsedLevel) && parsedLevel >= 0 && parsedLevel <= 1) ambienceLevel = parsedLevel;
    }
  } catch (_) { /* storage blocked */ }

  let audio = null, master = null, lastTick = 0;
  let ambienceBus = null, ambienceNodes = [], shimmerTimer = 0;
  let dialogueActive = false;
  const ambientTarget = () => ambienceLevel * 0.8 * (dialogueActive ? 0.14 : 1);

  addEventListener("mq:dialogue", event => {
    dialogueActive = Boolean(event.detail?.active);
    if (!ambienceBus || !audio) return;
    ambienceBus.gain.cancelScheduledValues(audio.currentTime);
    ambienceBus.gain.setTargetAtTime(ambientTarget(), audio.currentTime, dialogueActive ? 0.08 : 0.5);
  });

  function ensureAudio() {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    if (!audio) {
      audio = new Ctor();
      master = audio.createGain();
      master.gain.value = 0.48;
      const limiter = audio.createDynamicsCompressor();
      limiter.threshold.value = -18;
      limiter.knee.value = 16;
      limiter.ratio.value = 3;
      limiter.attack.value = 0.008;
      limiter.release.value = 0.2;
      master.connect(limiter).connect(audio.destination);
    }
    if (audio.state === "suspended") audio.resume();
    return audio;
  }

  function tone(freq, end, type, dur, gain, delay = 0) {
    const ac = ensureAudio();
    if (!ac) return;
    const t0 = ac.currentTime + delay;
    const osc = ac.createOscillator(), amp = ac.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    if (end !== freq) osc.frequency.exponentialRampToValueAtTime(Math.max(40, end), t0 + dur);
    amp.gain.setValueAtTime(0.0001, t0);
    amp.gain.exponentialRampToValueAtTime(gain, t0 + Math.min(0.018, dur / 3));
    amp.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(amp).connect(master);
    osc.start(t0);
    osc.stop(t0 + dur + 0.03);
  }

  function hiss(freq, dur, gain) {
    const ac = ensureAudio();
    if (!ac) return;
    const length = Math.max(1, Math.ceil(ac.sampleRate * dur));
    const buffer = ac.createBuffer(1, length, ac.sampleRate), data = buffer.getChannelData(0);
    for (let i = 0; i < length; i += 1) data[i] = (Math.random() * 2 - 1) * (1 - i / length);
    const source = ac.createBufferSource(), filter = ac.createBiquadFilter(), amp = ac.createGain();
    source.buffer = buffer;
    filter.type = "bandpass";
    filter.frequency.value = freq;
    filter.Q.value = 0.8;
    amp.gain.value = gain;
    source.connect(filter).connect(amp).connect(master);
    source.start();
  }

  const palette = {
    tick: () => tone(1120, 760, "sine", 0.045, 0.018),
    switch: () => { tone(640, 920, "sine", 0.08, 0.026); tone(960, 1180, "sine", 0.11, 0.012, 0.035); },
    start: () => { hiss(540, 0.38, 0.024); tone(110, 220, "sine", 0.52, 0.04); tone(330, 440, "sine", 0.48, 0.018, 0.12); },
    success: () => { tone(440, 440, "sine", 0.36, 0.035); tone(659.25, 659.25, "sine", 0.44, 0.028, 0.09); tone(880, 880, "sine", 0.62, 0.02, 0.2); },
    error: () => { tone(220, 164, "triangle", 0.32, 0.032); tone(164.81, 123.47, "sine", 0.42, 0.022, 0.07); },
    export: () => { hiss(2200, 0.12, 0.022); tone(880, 1320, "sine", 0.18, 0.028, 0.04); tone(1760, 1760, "sine", 0.26, 0.012, 0.12); },
    cancel: () => { tone(440, 330, "sine", 0.2, 0.028); tone(220, 165, "sine", 0.3, 0.018, 0.08); },
  };

  function play(name) {
    if (!enabled) return;
    const now = performance.now();
    if (name === "tick" && now - lastTick < 50) return;
    lastTick = now;
    ensureAudio();
    (palette[name] || palette.tick)();
  }

  window.mqSound = play;
  addEventListener("mq:sound", event => play(event.detail));

  const soundButton = document.getElementById("sound-toggle");
  const ambienceButton = document.getElementById("ambience-toggle");
  const ambienceSlider = document.getElementById("ambience-volume");

  function playShimmer() {
    if (!ambienceEnabled || !ambienceBus || !audio) return;
    shimmerTimer = setTimeout(playShimmer, 11000 + Math.random() * 8000);
    if (audio.state !== "running" || dialogueActive) return;
    const ac = audio, now = ac.currentTime;
    const osc = ac.createOscillator(), envelope = ac.createGain();
    const filter = ac.createBiquadFilter(), pan = ac.createStereoPanner();
    const delay = ac.createDelay(0.5), echo = ac.createGain();
    const notes = [659.25, 783.99, 987.77, 1174.66, 1318.51];
    osc.type = "sine";
    osc.frequency.value = notes[Math.floor(Math.random() * notes.length)];
    filter.type = "highpass";
    filter.frequency.value = 520;
    filter.Q.value = 0.55;
    pan.pan.value = Math.random() * 0.72 - 0.36;
    delay.delayTime.value = 0.19;
    echo.gain.value = 0.15;
    envelope.gain.setValueAtTime(0.0001, now);
    envelope.gain.exponentialRampToValueAtTime(0.012, now + 0.09);
    envelope.gain.exponentialRampToValueAtTime(0.0001, now + 1.45);
    osc.connect(envelope).connect(filter).connect(pan);
    pan.connect(ambienceBus);
    pan.connect(delay).connect(echo).connect(ambienceBus);
    osc.start(now);
    osc.stop(now + 1.5);
    osc.addEventListener("ended", () => {
      osc.disconnect(); envelope.disconnect(); filter.disconnect(); pan.disconnect(); delay.disconnect(); echo.disconnect();
    }, { once: true });
  }

  function startAmbience() {
    const ac = ensureAudio();
    if (!ac || ambienceBus) return;
    ambienceBus = ac.createGain();
    ambienceBus.gain.value = 0.0001;
    ambienceBus.connect(master);
    const lowPass = ac.createBiquadFilter();
    lowPass.type = "lowpass";
    lowPass.frequency.value = 410;
    lowPass.Q.value = 0.65;
    lowPass.connect(ambienceBus);
    const voices = [[55, "sine", 0.17], [82.41, "sine", 0.09], [110, "triangle", 0.035], [164.81, "sine", 0.018]];
    ambienceNodes = [lowPass];
    for (const [frequency, type, level] of voices) {
      const oscillator = ac.createOscillator(), gain = ac.createGain();
      oscillator.type = type;
      oscillator.frequency.value = frequency;
      gain.gain.value = level;
      oscillator.connect(gain).connect(lowPass);
      oscillator.start();
      ambienceNodes.push(oscillator, gain);
    }
    const drift = ac.createOscillator(), driftDepth = ac.createGain();
    drift.type = "sine";
    drift.frequency.value = 0.055;
    driftDepth.gain.value = 115;
    drift.connect(driftDepth).connect(lowPass.frequency);
    drift.start();
    ambienceNodes.push(drift, driftDepth);
    const now = ac.currentTime;
    ambienceBus.gain.setValueAtTime(0.0001, now);
    ambienceBus.gain.exponentialRampToValueAtTime(Math.max(0.0001, ambientTarget()), now + 2.4);
    shimmerTimer = setTimeout(playShimmer, 3200);
  }

  function stopAmbience() {
    clearTimeout(shimmerTimer);
    shimmerTimer = 0;
    if (!ambienceBus || !audio) return;
    const bus = ambienceBus, nodes = ambienceNodes;
    ambienceBus = null;
    ambienceNodes = [];
    const now = audio.currentTime;
    bus.gain.cancelScheduledValues(now);
    bus.gain.setTargetAtTime(0.0001, now, 0.16);
    setTimeout(() => {
      for (const node of nodes) {
        try { if (node instanceof OscillatorNode) node.stop(); } catch (_) { /* already stopped */ }
        try { node.disconnect(); } catch (_) { /* already disconnected */ }
      }
      try { bus.disconnect(); } catch (_) { /* already disconnected */ }
    }, 900);
  }

  function paintAmbienceButton() {
    if (!ambienceButton) return;
    const label = ambienceEnabled ? "Turn off ambient soundscape" : "Turn on ambient soundscape";
    ambienceButton.setAttribute("aria-pressed", String(ambienceEnabled));
    ambienceButton.setAttribute("aria-label", label);
    ambienceButton.title = label;
  }

  function setAmbience(next) {
    ambienceEnabled = next;
    paintAmbienceButton();
    if (ambienceEnabled) {
      startAmbience();
    } else stopAmbience();
  }

  function setAmbienceLevel(value) {
    ambienceLevel = Math.max(0, Math.min(1, Number(value) / 100));
    try { localStorage.setItem(AMBIENCE_LEVEL_KEY, String(ambienceLevel)); } catch (_) { /* storage blocked */ }
    if (ambienceBus && audio) {
      ambienceBus.gain.cancelScheduledValues(audio.currentTime);
      ambienceBus.gain.setTargetAtTime(ambientTarget(), audio.currentTime, 0.18);
    }
  }

  function paintSoundButton() {
    if (!soundButton) return;
    soundButton.classList.toggle("muted", !enabled);
    soundButton.setAttribute("aria-pressed", String(enabled));
    const label = enabled ? "Mute interface sounds (M)" : "Enable interface sounds (M)";
    soundButton.setAttribute("aria-label", label);
    soundButton.title = label;
  }

  function setSound(next, fromUser = false) {
    enabled = next;
    try { localStorage.setItem(STORE_KEY, enabled ? "on" : "off"); } catch (_) { /* storage blocked */ }
    paintSoundButton();
    if (enabled && fromUser) play("tick");
  }

  if (!(window.AudioContext || window.webkitAudioContext)) {
    soundButton?.remove();
    ambienceButton?.remove();
    ambienceSlider?.closest(".ambience-volume")?.remove();
  } else {
    paintSoundButton();
    soundButton?.addEventListener("click", () => setSound(!enabled, true));
    paintAmbienceButton();
    if (ambienceSlider) ambienceSlider.value = String(Math.round(ambienceLevel * 100));
    ambienceButton?.addEventListener("click", () => setAmbience(!ambienceEnabled));
    ambienceSlider?.addEventListener("input", event => setAmbienceLevel(event.currentTarget.value));
  }

  // Unlock the audio context on the first real gesture, whatever it is.
  const unlock = () => { if (enabled) ensureAudio(); removeEventListener("pointerdown", unlock); removeEventListener("keydown", unlock); };
  addEventListener("pointerdown", unlock, { once: true, passive: true });
  addEventListener("keydown", unlock, { once: true });

  // Delegated click feedback. Buttons with dedicated events are skipped.
  document.addEventListener("click", event => {
    const hit = event.target.closest("button, a");
    if (!hit || ["sound-toggle", "ambience-toggle", "voice-toggle", "dialogue-dismiss"].includes(hit.id)) return;
    if (hit.id === "run" || hit.id === "cancel" || hit.id === "export-queue") return;
    play(hit.classList.contains("nav-tab") ? "switch" : "tick");
  });

  /* ── trailing cursor ─────────────────────────────────────────────────── */

  const interactive = "a, button, input, select, textarea, label, [role='button'], tr, .segmented, .kpi-card";

  if (finePointer.matches && canHover.matches && !reduceMotion.matches) {
    const ring = document.createElement("div");
    const dot = document.createElement("div");
    ring.className = "mq-cursor-ring";
    dot.className = "mq-cursor-dot";
    ring.setAttribute("aria-hidden", "true");
    dot.setAttribute("aria-hidden", "true");
    document.body.append(ring, dot);

    let tx = -60, ty = -60, rx = -60, ry = -60, dx = -60, dy = -60;
    let visible = false, frame = 0;

    const render = () => {
      rx += (tx - rx) * 0.16;
      ry += (ty - ry) * 0.16;
      dx += (tx - dx) * 0.44;
      dy += (ty - dy) * 0.44;
      ring.style.transform = `translate3d(${rx}px,${ry}px,0) translate(-50%,-50%)`;
      dot.style.transform = `translate3d(${dx}px,${dy}px,0) translate(-50%,-50%)`;
      frame = requestAnimationFrame(render);
    };

    const show = () => {
      if (visible) return;
      visible = true;
      ring.classList.add("is-visible");
      dot.classList.add("is-visible");
      if (!frame) frame = requestAnimationFrame(render);
    };

    const hide = () => {
      visible = false;
      ring.classList.remove("is-visible", "is-hot", "is-down");
      dot.classList.remove("is-visible");
      if (frame) { cancelAnimationFrame(frame); frame = 0; }
    };

    addEventListener("pointermove", event => {
      if (event.pointerType !== "mouse") return;
      tx = event.clientX;
      ty = event.clientY;
      if (!visible) { rx = dx = tx; ry = dy = ty; show(); }
    }, { passive: true });

    document.addEventListener("pointerover", event => {
      ring.classList.toggle("is-hot", Boolean(event.target.closest(interactive)));
    });
    document.addEventListener("pointerout", event => {
      if (!event.relatedTarget) ring.classList.remove("is-hot");
    });
    addEventListener("pointerdown", event => {
      if (event.pointerType !== "mouse") return;
      ring.classList.add("is-down");
      const ripple = document.createElement("span");
      ripple.className = "mq-cursor-ripple";
      ripple.style.left = event.clientX + "px";
      ripple.style.top = event.clientY + "px";
      document.body.append(ripple);
      ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
    }, { passive: true });
    addEventListener("pointerup", () => ring.classList.remove("is-down"), { passive: true });
    document.documentElement.addEventListener("mouseleave", hide);
    addEventListener("blur", hide);
  }

  /* ── shortcuts ───────────────────────────────────────────────────────── */

  const typing = node => node && (/^(INPUT|TEXTAREA|SELECT)$/.test(node.tagName) || node.isContentEditable);

  addEventListener("keydown", event => {
    if (event.ctrlKey || event.metaKey || event.altKey || typing(document.activeElement)) return;
    if (event.key === "/") {
      event.preventDefault();
      document.getElementById("focus-search")?.click();
    } else if (event.key.toLowerCase() === "m" && soundButton) {
      event.preventDefault();
      soundButton.click();
    }
  });

  addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    const search = document.getElementById("queue-search");
    if (document.activeElement === search && search.value) {
      search.value = "";
      search.dispatchEvent(new Event("input", { bubbles: true }));
      search.blur();
    }
  });
})();

/* Original mission-control dialogue. Speech follows real queue lifecycle events;
   it never holds up the worker, changes its timing, or invents analysis results. */
(() => {
  const button = document.getElementById("voice-toggle");
  const panel = document.getElementById("system-dialogue");
  const caption = document.getElementById("dialogue-line");
  const phase = document.getElementById("dialogue-phase");
  const dismiss = document.getElementById("dialogue-dismiss");
  if (!button || !panel || !caption || !phase) return;

  const synth = window.speechSynthesis;
  const canSpeak = Boolean(synth && window.SpeechSynthesisUtterance);
  let voiceEnabled = true;
  try { voiceEnabled = localStorage.getItem("mq-voice") !== "off"; } catch (_) { /* storage blocked */ }
  let active = null, pending = null, epoch = 0;
  let captionTimer = 0, watchdog = 0, progressTimer = 0;
  let runActive = false;
  const previous = new Map();
  const labels = { start: "Initializing", processing: "Building queue", success: "Reference verified", cancel: "Cancelled", error: "Attention", export: "Export complete", preview: "Standing by" };
  const dialogue = {
    start: [
      "Midnight protocol engaged. Bring order to the noise.",
      "The signal is buried in the noise. Let's bring it into focus.",
      "Queue sequence initiated. Every position has to earn its place.",
      "From noise to order. Ranking sequence engaged.",
    ],
    processing: ["Queue build in progress. The sequence continues."],
    success: [
      "Queue verified. Order restored.",
      "Sequence complete. Every position, verified.",
      "The noise is ordered. Your queue is ready.",
    ],
    cancel: ["Sequence interrupted. Control is yours.", "Operation cancelled. Standing by for your command."],
    error: ["Sequence halted. Check the console before the next move."],
    export: ["Queue exported. The next move is yours."],
    preview: ["Midnight online. Awaiting your command."],
  };

  function choose(kind) {
    const lines = dialogue[kind];
    const choices = lines.map((_, index) => index).filter(index => lines.length === 1 || index !== previous.get(kind));
    const index = choices[Math.floor(Math.random() * choices.length)];
    previous.set(kind, index);
    return { kind, text: lines[index] };
  }

  function selectVoice() {
    if (!canSpeak) return null;
    const english = synth.getVoices().filter(voice => /^en(?:[-_]|$)/i.test(voice.lang));
    const score = voice => (voice.localService ? 30 : 0)
      + (/David|Mark|Daniel|George|James|Guy/i.test(voice.name) ? 45 : 0)
      + (/natural|neural/i.test(voice.name) ? 20 : 0)
      + (/en-(US|GB)/i.test(voice.lang) ? 10 : 0)
      + (voice.default ? 5 : 0);
    return english.sort((a, b) => score(b) - score(a))[0] || null;
  }

  function duck(active) {
    dispatchEvent(new CustomEvent("mq:dialogue", { detail: { active } }));
    panel.classList.toggle("is-speaking", active);
  }

  function stopDialogue() {
    epoch += 1;
    clearTimeout(captionTimer);
    clearTimeout(watchdog);
    clearTimeout(progressTimer);
    active = pending = null;
    runActive = false;
    if (canSpeak) synth.cancel();
    duck(false);
    panel.hidden = true;
  }

  function present(line) {
    if (!voiceEnabled || document.hidden) return;
    clearTimeout(captionTimer);
    clearTimeout(watchdog);
    const token = ++epoch;
    active = line;
    caption.textContent = line.text;
    phase.textContent = labels[line.kind];
    panel.dataset.phase = line.kind;
    panel.hidden = false;
    let finished = false;

    const finish = () => {
      if (finished || token !== epoch) return;
      finished = true;
      clearTimeout(watchdog);
      active = null;
      duck(false);
      const next = pending;
      pending = null;
      if (next) present(next);
      else captionTimer = setTimeout(() => { if (token === epoch) panel.hidden = true; }, 1600);
    };

    const fallback = () => {
      duck(false);
      clearTimeout(watchdog);
      watchdog = setTimeout(finish, Math.max(3200, line.text.split(/\s+/).length * 310));
    };

    if (!canSpeak) { fallback(); return; }
    const utterance = new SpeechSynthesisUtterance(line.text);
    // Retain the utterance while speaking, including engines that release unreferenced speech.
    line.utterance = utterance;
    const selected = selectVoice();
    if (selected) utterance.voice = selected;
    utterance.lang = selected?.lang || "en-US";
    utterance.rate = 0.92;
    utterance.pitch = 0.86;
    utterance.volume = 0.85;
    utterance.onstart = () => { if (token === epoch && !finished) duck(true); };
    utterance.onend = finish;
    utterance.onerror = () => { if (token === epoch && !finished) fallback(); };
    // A stalled engine cannot leave the ambience ducked or the narrator queue locked.
    watchdog = setTimeout(() => {
      if (token !== epoch || finished) return;
      utterance.onend = utterance.onerror = null;
      synth.cancel();
      finish();
    }, 15000);
    try { synth.speak(utterance); } catch (_) { fallback(); }
  }

  function narrate(kind) {
    if (!voiceEnabled || document.hidden) return;
    const line = choose(kind);
    if (active) pending = line;
    else present(line);
  }

  function paintButton() {
    button.setAttribute("aria-pressed", String(voiceEnabled));
    const medium = canSpeak ? "cinematic voice" : "cinematic captions";
    const label = `${voiceEnabled ? "Mute" : "Enable"} ${medium} (V)`;
    button.setAttribute("aria-label", label);
    button.title = label;
  }

  button.addEventListener("click", () => {
    voiceEnabled = !voiceEnabled;
    try { localStorage.setItem("mq-voice", voiceEnabled ? "on" : "off"); } catch (_) { /* storage blocked */ }
    stopDialogue();
    paintButton();
    if (voiceEnabled) narrate("preview");
  });
  dismiss?.addEventListener("click", stopDialogue);

  addEventListener("mq:sound", event => {
    const kind = event.detail;
    if (kind === "start") {
      stopDialogue();
      runActive = true;
      narrate("start");
      progressTimer = setTimeout(() => { if (runActive && !pending) narrate("processing"); }, 12000);
    } else if (["success", "cancel", "error"].includes(kind)) {
      clearTimeout(progressTimer);
      runActive = false;
      if (kind !== "success") stopDialogue();
      narrate(kind);
    } else if (kind === "export" && !active && !runActive) narrate("export");
  });
  addEventListener("keydown", event => {
    const target = document.activeElement;
    if (event.repeat || event.ctrlKey || event.metaKey || event.altKey || target?.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target?.tagName || "")) return;
    if (event.key.toLowerCase() === "v") { event.preventDefault(); button.click(); }
    else if (event.key === "Escape" && !panel.hidden) stopDialogue();
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) stopDialogue(); });
  addEventListener("pagehide", stopDialogue);
  paintButton();
})();
