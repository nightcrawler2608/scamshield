// Shared helper: reads the API address from extension settings (default = local backend).
const DEFAULT_API = "http://127.0.0.1:8000";

async function getApi() {
  const { apiUrl } = await chrome.storage.sync.get("apiUrl");
  return (apiUrl || DEFAULT_API).replace(/\/$/, "");
}

async function checkUrl(url) {
  const api = await getApi();
  const res = await fetch(`${api}/api/analyze/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, channel: "extension" }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
  return res.json();
}
