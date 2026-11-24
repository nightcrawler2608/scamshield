// Right-click any link -> "Check link with ScamShield". Shows the result as a badge + notification-like popup.
importScripts("api.js");

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "check-link", title: "Check link with ScamShield", contexts: ["link"] });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== "check-link" || !info.linkUrl) return;
  try {
    const d = await checkUrl(info.linkUrl);
    const text = { scam: "SCAM", suspicious: "RISK", safe: "OK" }[d.verdict];
    const color = { scam: "#d92d20", suspicious: "#dc8a00", safe: "#12a150" }[d.verdict];
    await chrome.action.setBadgeText({ text });
    await chrome.action.setBadgeBackgroundColor({ color });
    await chrome.storage.session.set({ lastResult: { url: info.linkUrl, ...d } });
  } catch (e) {
    await chrome.action.setBadgeText({ text: "ERR" });
  }
});
