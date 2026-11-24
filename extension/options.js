const input = document.getElementById("api");
chrome.storage.sync.get("apiUrl").then(({ apiUrl }) => { input.value = apiUrl || "http://127.0.0.1:8000"; });
document.getElementById("save").addEventListener("click", async () => {
  await chrome.storage.sync.set({ apiUrl: input.value.trim() });
  document.getElementById("ok").textContent = "Saved ✓";
});
