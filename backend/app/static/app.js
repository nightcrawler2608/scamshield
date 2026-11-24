// ScamShield web client. Uses textContent everywhere (never innerHTML with user data) to prevent XSS.
const $ = (id) => document.getElementById(id);
let currentId = null;
const SEGMENTS = 20;

// build the pixel risk meter once
$("meter").replaceChildren(...Array.from({ length: SEGMENTS }, () => document.createElement("span")));

function setScreen(state, label) {
  $("screen").className = `screen ${state || ""}`;
  const s = $("screen-state");
  s.textContent = label + " ";
  const c = document.createElement("span");
  c.className = "cursor";
  s.appendChild(c);
}

function selectTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === `form-${name}`));
}
document.querySelectorAll(".tab").forEach((btn) => btn.addEventListener("click", () => selectTab(btn.dataset.tab)));

// example chips + scam gallery cards fill the message box
document.querySelectorAll("[data-ex]").forEach((b) =>
  b.addEventListener("click", () => {
    selectTab("text");
    $("text").value = b.dataset.ex;
    if (b.classList.contains("case")) {
      $("scan").scrollIntoView({ behavior: "smooth" });
      $("form-text").requestSubmit();
    }
  }));

function show(id, on) { $(id).classList.toggle("hidden", !on); }

async function call(url, options) {
  show("error", false); show("result", false); show("empty", false); show("loading", true);
  setScreen("", "SCANNING");
  try {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong.");
    render(data);
  } catch (err) {
    $("error").textContent = "ERROR: " + err.message;
    show("error", true); show("empty", true);
    setScreen("", "ERROR");
  } finally {
    show("loading", false);
  }
}

function fillList(el, items) {
  el.replaceChildren(...items.map((t) => { const li = document.createElement("li"); li.textContent = t; return li; }));
}

function render(d) {
  currentId = d.analysis_id;
  const labels = { scam: "SCAM!", suspicious: "SUSPICIOUS", safe: "LOOKS SAFE" };
  const icons = { scam: "warning", suspicious: "search", safe: "shield" };

  const badge = $("badge");
  badge.className = `verdict ${d.verdict}`;
  const icon = document.createElement("i");
  icon.dataset.pixel = icons[d.verdict];
  icon.dataset.size = "40";
  const txt = document.createElement("span");
  txt.textContent = labels[d.verdict];
  badge.replaceChildren(icon, txt);
  renderPixels(badge);

  const pct = Math.min(99, Math.round(d.risk_score * 100)); // never claim 100% certainty
  const lit = Math.max(1, Math.round((pct / 100) * SEGMENTS));
  [...$("meter").children].forEach((s, i) => (s.className = i < lit ? `on ${d.verdict}` : ""));
  $("score-text").textContent = `RISK SCORE: ${pct}%`;
  $("explanation").textContent = d.explanation;
  fillList($("reasons"), d.reasons.length ? d.reasons : ["No known scam patterns found."]);
  fillList($("advice"), d.advice);
  fillList($("links"), d.urls.map((u) => `${u.url} → ${Math.min(99, Math.round(u.score * 100))}% risk`));
  show("links-block", d.urls.length > 0);
  $("ocr").textContent = d.extracted_text || "";
  show("ocr-block", !!d.extracted_text);
  show("fb-thanks", false);
  document.querySelectorAll(".fb").forEach((b) => (b.disabled = false));
  show("result", true);
  setScreen(d.verdict, labels[d.verdict]);
}

$("form-text").addEventListener("submit", (e) => {
  e.preventDefault();
  call("/api/analyze/text", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: $("text").value, channel: "web" }) });
});

$("form-url").addEventListener("submit", (e) => {
  e.preventDefault();
  call("/api/analyze/url", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: $("url").value, channel: "web" }) });
});

$("form-image").addEventListener("submit", (e) => {
  e.preventDefault();
  const fd = new FormData();
  fd.append("file", $("image").files[0]);
  fd.append("channel", "web");
  call("/api/analyze/image", { method: "POST", body: fd });
});

document.querySelectorAll(".fb").forEach((b) =>
  b.addEventListener("click", async () => {
    if (!currentId) return;
    document.querySelectorAll(".fb").forEach((x) => (x.disabled = true));
    await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: currentId, is_correct: b.dataset.ok === "true" }) });
    show("fb-thanks", true);
  }));

// show the real text-model F1 on the CRT badge
fetch("/api/stats").then((r) => r.json()).then((s) => {
  const f1 = s.models?.text?.f1;
  if (f1) $("res-f1").textContent = `${Math.round(f1 * 100)}% F1`;
}).catch(() => {});
