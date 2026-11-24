const $ = (id) => document.getElementById(id);
const LABEL = { scam: "🚨 SCAM SITE", suspicious: "⚠️ SUSPICIOUS", safe: "✅ LOOKS SAFE" };

function render(url, d) {
  $("url").textContent = url;
  $("verdict").textContent = LABEL[d.verdict];
  $("verdict").className = `verdict ${d.verdict}`;
  $("score").textContent = `Risk: ${Math.round(d.risk_score * 100)}%`;
  $("reasons").replaceChildren(...(d.reasons.length ? d.reasons : ["No phishing signs found."]).slice(0, 4)
    .map((r) => { const li = document.createElement("li"); li.textContent = r; return li; }));
}

async function checkActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url || !/^https?:/.test(tab.url)) {
    $("verdict").textContent = "Open a website to check it.";
    return;
  }
  $("verdict").textContent = "Checking…";
  try {
    render(tab.url, await checkUrl(tab.url));
  } catch (e) {
    $("verdict").textContent = "Could not reach ScamShield: " + e.message;
  }
}

(async () => {
  const { lastResult } = await chrome.storage.session.get("lastResult");
  if (lastResult) {
    render(lastResult.url, lastResult);
    await chrome.storage.session.remove("lastResult");
    await chrome.action.setBadgeText({ text: "" });
  } else {
    checkActiveTab();
  }
})();
$("recheck").addEventListener("click", checkActiveTab);
