(() => {
  const $ = (id) => document.getElementById(id);
  const API = window.API_BASE.replace(/\/$/, "");
  const COLORS = { N: "#39ff6a", S: "#ffc83d", V: "#ff4d4d", F: "#d96bff", Q: "#8fa39a" };
  const CLASS_NAMES = { N: "Normal", S: "Supraventricular", V: "Ventricular", F: "Fusion", Q: "Unclassifiable" };
  const WINDOW_SEC = 8;
  const show = (el, on) => (el.hidden = !on);
  let data = null, sweep = 1, offset = 0, raf = 0, scale = { lo: -1, hi: 1 };

  /* ---------- status ---------- */
  async function ping() {
    const el = $("status");
    try {
      if (!(await fetch(API + "/health", { cache: "no-store" })).ok) throw 0;
      el.className = "status ok"; el.lastElementChild.textContent = "API ONLINE";
    } catch {
      el.className = "status bad"; el.lastElementChild.textContent = "API OFFLINE · " + API;
      setTimeout(ping, 4000);
    }
  }
  ping();

  /* ---------- input ---------- */
  const drop = $("drop");
  ["dragenter", "dragover"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => e.dataTransfer.files[0] && analyse(e.dataTransfer.files[0]));
  $("file").addEventListener("change", (e) => e.target.files[0] && analyse(e.target.files[0]));
  $("fs").addEventListener("change", () => ($("fsLabel").textContent = $("fs").value + " Hz"));
  document.querySelectorAll("[data-sample]").forEach((b) => b.addEventListener("click", async () => {
    setError("");
    try {
      const txt = await (await fetch(`${API}/arrhythmia/samples/${b.dataset.sample}`)).text();
      $("fs").value = "360";
      analyse(new File([txt], b.dataset.sample + ".csv", { type: "text/csv" }));
    } catch { setError(`Cannot reach the API at ${API}. Is the backend running?`); }
  }));

  const setError = (m) => { $("error").textContent = m || ""; show($("error"), !!m); };

  async function post(path, body, isForm) {
    const r = await fetch(API + path, { method: "POST", headers: isForm ? undefined : { "Content-Type": "application/json" }, body: isForm ? body : JSON.stringify(body) });
    let j = null; try { j = await r.json(); } catch {}
    if (!r.ok) throw new Error((j && j.detail) || `Request failed (${r.status})`);
    return j;
  }

  async function analyse(file) {
    setError(""); show($("notice"), false);
    show($("busy"), true); $("busyText").textContent = "UPLOADING";
    try {
      const fd = new FormData(); fd.append("file", file);
      const { file_url } = await post("/uploads", fd, true);
      $("busyText").textContent = "ANALYSING";
      const res = await post("/arrhythmia/predict", { file_url, sampling_rate: parseInt($("fs").value, 10) });
      render(res);
    } catch (e) {
      setError(e.message === "Failed to fetch" ? `Cannot reach the API at ${API}. Is the backend running?` : e.message);
    } finally { show($("busy"), false); }
  }

  /* ---------- results ---------- */
  function render(r) {
    if (r.rhythm_type === "unknown") {
      $("notice").innerHTML = "The model weights are not installed, so no analysis was produced. Run <code>scripts/fetch_weights</code> (or place <code>model.onnx</code> and <code>feature_stats.json</code> in <code>backend/app/arrhythmia/weights/</code>) and restart the API.";
      show($("notice"), true); return;
    }
    data = r;
    const sorted = [...r.signal].sort((a, b) => a - b);
    scale = { lo: sorted[Math.floor(sorted.length * 0.005)], hi: sorted[Math.floor(sorted.length * 0.995)] };
    const pad = (scale.hi - scale.lo) * 0.25 || 1; scale.lo -= pad; scale.hi += pad;

    show(drop, false);
    $("hr").textContent = r.heart_rate_bpm ? Math.round(r.heart_rate_bpm) : "--";
    $("rhythm").textContent = r.rhythm_type;
    const crit = (r.rhythm_alerts || []).some((a) => a.severity === "critical");
    const warn = (r.rhythm_alerts || []).length > 0 || /Ectopic/.test(r.rhythm_type);
    $("banner").className = "banner " + (crit ? "crit" : warn ? "warn" : r.beats.length ? "ok" : "idle");
    $("conf").textContent = r.beats.length ? (r.confidence * 100).toFixed(1) + "%" : "--";

    const counts = $("counts"); counts.innerHTML = "";
    ["N", "S", "V", "F", "Q"].forEach((c) => {
      const d = document.createElement("div"); d.style.setProperty("--c", COLORS[c]);
      d.innerHTML = `<b>${(r.beat_summary || {})[c] ?? 0}</b><small>${c}</small>`; counts.appendChild(d);
    });

    const al = $("alerts"); al.innerHTML = "";
    if (!(r.rhythm_alerts || []).length) al.innerHTML = '<li class="muted">No rhythm alerts</li>';
    (r.rhythm_alerts || []).forEach((a) => {
      const li = document.createElement("li"); li.className = a.severity;
      li.innerHTML = `<span>${a.type}</span><span>${a.start.toFixed(1)}–${a.end.toFixed(1)} s</span>`; al.appendChild(li);
    });

    const bl = $("beats"); bl.innerHTML = "";
    $("nflag").textContent = r.flagged_beats.length ? `(${r.flagged_beats.length})` : "";
    if (!r.flagged_beats.length) bl.innerHTML = '<li class="muted">No abnormal beats</li>';
    r.flagged_beats.forEach((b) => {
      const li = document.createElement("li"); li.style.setProperty("--c", COLORS[b.class]);
      li.innerHTML = `<span>${b.class} · ${CLASS_NAMES[b.class]}</span><span>${b.time_sec.toFixed(2)} s · ${(b.confidence * 100).toFixed(0)}%</span>`;
      li.addEventListener("click", () => jumpTo(b.time_sec)); bl.appendChild(li);
    });

    if (r.warnings && r.warnings.length) { $("notice").textContent = r.warnings.join(" "); show($("notice"), true); }

    const maxOff = Math.max(0, r.duration_sec - WINDOW_SEC);
    const pos = $("pos"); pos.max = Math.round(maxOff * 100); pos.value = 0; offset = 0;
    show($("pan"), maxOff > 0.01);
    sweep = 0; cancelAnimationFrame(raf);
    const t0 = performance.now();
    const step = (t) => { sweep = Math.min((t - t0) / 1800, 1); draw(); if (sweep < 1) raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
  }

  $("pos").addEventListener("input", (e) => { offset = e.target.value / 100; draw(); });
  function jumpTo(t) {
    if (!data) return;
    const maxOff = Math.max(0, data.duration_sec - WINDOW_SEC);
    offset = Math.min(Math.max(t - WINDOW_SEC / 2, 0), maxOff); $("pos").value = Math.round(offset * 100); draw();
  }

  /* ---------- canvas ---------- */
  const cv = $("cv"), ctx = cv.getContext("2d");
  function sizeCanvas() {
    const r = cv.getBoundingClientRect(), d = window.devicePixelRatio || 1;
    cv.width = Math.round(r.width * d); cv.height = Math.round(r.height * d); ctx.setTransform(d, 0, 0, d, 0, 0);
    return { w: r.width, h: r.height };
  }

  function draw() {
    const { w, h } = sizeCanvas();
    ctx.clearRect(0, 0, w, h);
    const span = data ? Math.min(WINDOW_SEC, data.duration_sec) : WINDOW_SEC;

    // graph paper
    const px = w / span;                       // pixels per second
    ctx.lineWidth = 1;
    for (let t = 0; t <= span + 0.001; t += 0.04) {
      const x = t * px, major = Math.abs(t / 0.2 - Math.round(t / 0.2)) < 1e-6;
      ctx.strokeStyle = major ? "rgba(57,255,106,.16)" : "rgba(57,255,106,.06)";
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 0; y <= h; y += h / 10) {
      ctx.strokeStyle = "rgba(57,255,106,.08)"; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }
    if (!data) return;

    const fs = data.signal_fs, i0 = Math.floor(offset * fs), i1 = Math.min(data.signal.length, Math.ceil((offset + span) * fs));
    const y = (v) => h - ((v - scale.lo) / (scale.hi - scale.lo)) * h;
    const lim = offset * 1 + span * sweep;      // sweep reveal
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, (lim - offset) * px, h); ctx.clip();
    ctx.strokeStyle = "#39ff6a"; ctx.lineWidth = 1.8; ctx.shadowColor = "#39ff6a"; ctx.shadowBlur = 6; ctx.lineJoin = "round";
    ctx.beginPath();
    for (let i = i0; i < i1; i++) {
      const x = (i / fs - offset) * px;
      i === i0 ? ctx.moveTo(x, y(data.signal[i])) : ctx.lineTo(x, y(data.signal[i]));
    }
    ctx.stroke(); ctx.restore();

    // beat markers
    ctx.font = "600 13px 'Barlow Condensed', sans-serif"; ctx.textAlign = "center";
    data.beats.forEach((b) => {
      if (b.time_sec < offset || b.time_sec > offset + span || b.time_sec > lim) return;
      const x = (b.time_sec - offset) * px, col = COLORS[b.class];
      ctx.strokeStyle = col; ctx.globalAlpha = b.class === "N" ? 0.35 : 0.9; ctx.lineWidth = b.class === "N" ? 1 : 1.6;
      ctx.beginPath(); ctx.moveTo(x, 22); ctx.lineTo(x, h - 6); ctx.stroke(); ctx.globalAlpha = 1;
      ctx.fillStyle = col; ctx.fillText(b.class, x, 15);
    });

    // window label
    $("winLabel").textContent = `${offset.toFixed(1)} – ${(offset + span).toFixed(1)} s of ${data.duration_sec.toFixed(1)} s`;
  }
  window.addEventListener("resize", draw);
  draw();

  /* tooltip */
  cv.addEventListener("mousemove", (e) => {
    if (!data) return;
    const r = cv.getBoundingClientRect(), span = Math.min(WINDOW_SEC, data.duration_sec);
    const t = offset + ((e.clientX - r.left) / r.width) * span;
    let best = null, bd = 0.18;
    data.beats.forEach((b) => { const d = Math.abs(b.time_sec - t); if (d < bd) { bd = d; best = b; } });
    const tip = $("tip");
    if (!best) return show(tip, false);
    tip.textContent = `${best.class} · ${CLASS_NAMES[best.class]} · ${(best.confidence * 100).toFixed(0)}% · ${best.time_sec.toFixed(2)} s`;
    show(tip, true);
    const sr = $("screen").getBoundingClientRect();
    tip.style.left = Math.min(e.clientX - sr.left + 12, sr.width - tip.offsetWidth - 8) + "px"; tip.style.top = Math.max(e.clientY - sr.top - 34, 4) + "px";
  });
  cv.addEventListener("mouseleave", () => show($("tip"), false));
})();
