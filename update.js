"use strict";

// ---------- 새 버전 자동 적용 ----------
// 홈 화면 앱은 옛 화면(index.html)을 캐시에 들고 있어서 배포해도 바로 바뀌지 않는다.
// 앱을 열거나 다시 볼 때 version.json을 캐시 없이 받아서, 버전이 다르면
// 주소에 새 버전을 붙여 다시 열어 새 화면을 받는다.
function currentVersion() {
  const script = document.querySelector('script[src*="app.js"]');
  return script ? new URL(script.src).searchParams.get("v") : null;
}

async function checkForUpdate() {
  const cur = currentVersion();
  if (!cur || cur === "dev") return; // 내 컴퓨터에서 직접 열었을 때
  // 입력 중인 창이 열려 있으면 내용을 잃지 않도록 다음 기회에
  if (document.querySelector("dialog[open]")) return;
  try {
    const res = await fetch(`version.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return;
    const { version } = await res.json();
    if (!version || version === cur) return;
    const url = new URL(location.href);
    // 이미 새 버전 주소로 열었는데도 옛 화면이면 되풀이하지 않는다
    if (url.searchParams.get("v") === version) return;
    url.searchParams.set("v", version);
    location.replace(url.toString());
  } catch { /* 오프라인이면 다음에 */ }
}

document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") checkForUpdate(); });
checkForUpdate();
