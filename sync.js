"use strict";

// ---------- PC·휴대폰 동기화 (비공개 GitHub 저장소의 ledger.json) ----------
// 각 기기는 자기 브라우저에 저장하고, 바뀔 때마다 저장소의 파일과 합친다.
// 내역마다 updatedAt(수정 시각)을, 삭제는 state.deleted에 시각을 남겨 최신 쪽을 고른다.
const SYNC_KEY = "ledger.sync.v1";
const SYNC_FILE = "ledger.json";
const SYNC_DEFAULT_REPO = "z7j5r9hz2j-ui/ledger-data";

const sync = {
  cfg: loadSyncCfg(),
  running: false,
  again: false,
  timer: null,
  lastOk: null,
  error: "",
};

function loadSyncCfg() {
  try { return JSON.parse(localStorage.getItem(SYNC_KEY) || "null"); } catch { return null; }
}
function saveSyncCfg(cfg) {
  try { cfg ? localStorage.setItem(SYNC_KEY, JSON.stringify(cfg)) : localStorage.removeItem(SYNC_KEY); }
  catch { /* 무시 */ }
}

class GhError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function gh(path, opts = {}) {
  const { repo, token } = sync.cfg;
  const res = await fetch(`https://api.github.com/repos/${repo}${path}`, {
    ...opts,
    cache: "no-store",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(opts.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  if (!res.ok) throw new GhError(res.status, await res.text().catch(() => ""));
  return res.json();
}

function b64encode(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}
function b64decode(b64) {
  const bin = atob(b64.replace(/\s/g, ""));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}

async function pullRemote() {
  try {
    const f = await gh(`/contents/${SYNC_FILE}`);
    // 1MB가 넘는 파일은 content가 비어 오므로 blob으로 받는다
    const content = f.content || (await gh(`/git/blobs/${f.sha}`)).content;
    return { data: JSON.parse(b64decode(content)), sha: f.sha };
  } catch (e) {
    if (e.status !== 404) throw e;
    await gh(""); // 저장소 자체가 없으면 여기서 404가 난다
    return { data: null, sha: null };
  }
}

// 두 쪽 내역을 합친다: 같은 id면 더 최근에 수정된 것, 삭제가 더 나중이면 삭제
function mergeData(a, b) {
  const deleted = {};
  for (const src of [b?.deleted, a?.deleted]) {
    for (const [id, ts] of Object.entries(src || {})) deleted[id] = Math.max(deleted[id] || 0, ts);
  }
  const byId = new Map();
  for (const t of [...(b?.tx || []), ...(a?.tx || [])]) {
    const cur = byId.get(t.id);
    if (!cur || (t.updatedAt || 0) >= (cur.updatedAt || 0)) byId.set(t.id, t);
  }
  const tx = [...byId.values()]
    .filter((t) => !(deleted[t.id] >= (t.updatedAt || 0)))
    .sort((x, y) => (x.date + x.id).localeCompare(y.date + y.id));
  const exported = [...new Set([...(b?.exported || []), ...(a?.exported || [])])].sort();
  const sortedDeleted = Object.fromEntries(Object.entries(deleted).sort(([x], [y]) => x.localeCompare(y)));
  return { version: 2, tx, deleted: sortedDeleted, exported };
}

const localData = () => ({ tx: state.tx, deleted: state.deleted, exported: loadExported() });
const same = (x, y) => JSON.stringify(mergeData(x, null)) === JSON.stringify(mergeData(y, null));

function applyMerged(merged) {
  // 네트워크를 기다리는 동안 이 기기에서 바뀐 내용도 잃지 않도록 한 번 더 합친다
  const final = mergeData(localData(), merged);
  state.tx = final.tx;
  state.deleted = final.deleted;
  try { localStorage.setItem(EXPORT_KEY, JSON.stringify(final.exported)); } catch { /* 무시 */ }
  persistLocal();
  render();
}

const deviceName = () => (/Mobi|Android|iPhone/i.test(navigator.userAgent) ? "휴대폰" : "PC");

async function syncNow() {
  if (!sync.cfg) return;
  if (sync.running) { sync.again = true; return; }
  sync.running = true;
  renderSyncStatus("syncing");
  try {
    for (let attempt = 0; ; attempt++) {
      const remote = await pullRemote();
      const merged = mergeData(localData(), remote.data);
      if (!same(merged, localData())) applyMerged(merged);
      if (remote.data && same(merged, remote.data)) break;
      try {
        await gh(`/contents/${SYNC_FILE}`, {
          method: "PUT",
          body: JSON.stringify({
            message: `가계부 업데이트 (${deviceName()})`,
            content: b64encode(JSON.stringify(merged)),
            ...(remote.sha ? { sha: remote.sha } : {}),
          }),
        });
        break;
      } catch (e) {
        // 그 사이 다른 기기가 먼저 저장했으면 다시 받아서 합친다
        if ((e.status === 409 || e.status === 422) && attempt < 3) continue;
        throw e;
      }
    }
    sync.lastOk = new Date();
    sync.error = "";
  } catch (e) {
    sync.error = syncErrorMessage(e);
  } finally {
    sync.running = false;
    renderSyncStatus();
    if (sync.again) { sync.again = false; syncNow(); }
  }
}

function syncErrorMessage(e) {
  if (e instanceof GhError) {
    if (e.status === 401) return "토큰이 올바르지 않거나 만료됐어요. 새 토큰을 입력하세요.";
    if (e.status === 403) return "토큰 권한이 부족해요. Contents 읽기·쓰기 권한을 주세요.";
    if (e.status === 404) return "저장소를 찾을 수 없어요. 저장소 이름과 토큰의 접근 저장소를 확인하세요.";
    return `GitHub 오류 (${e.status})`;
  }
  return "인터넷에 연결할 수 없어요. 이 기기에 저장해두고 연결되면 동기화해요.";
}

function scheduleSync() {
  if (!sync.cfg) return;
  clearTimeout(sync.timer);
  sync.timer = setTimeout(syncNow, 1500);
}

// ---------- 화면 ----------
function renderSyncStatus(mode) {
  const btn = $("#btn-sync");
  let label, cls = "";
  if (!sync.cfg) label = "동기화 설정";
  else if (mode === "syncing") label = "동기화 중…";
  else if (sync.error) { label = "동기화 오류"; cls = "error"; }
  else if (sync.lastOk) { label = `동기화됨 ${pad(sync.lastOk.getHours())}:${pad(sync.lastOk.getMinutes())}`; cls = "ok"; }
  else label = "동기화 대기";
  btn.textContent = label;
  btn.className = `btn sync-btn ${cls}`;

  const status = $("#sync-status");
  if (status) {
    status.textContent = !sync.cfg ? "" : sync.error || (sync.lastOk ? `마지막 동기화: ${sync.lastOk.toLocaleString("ko-KR")}` : "");
    status.className = `sync-status ${sync.error ? "error" : ""}`;
  }
}

const syncDialog = $("#sync-dialog");
const syncForm = $("#sync-form");

function normalizeRepo(v) {
  const m = String(v).trim().replace(/\.git$/, "").match(/([\w.-]+)\/([\w.-]+)\/?$/);
  return m ? `${m[1]}/${m[2]}` : "";
}

$("#btn-sync").onclick = () => {
  syncForm.repo.value = sync.cfg?.repo || SYNC_DEFAULT_REPO;
  syncForm.token.value = "";
  syncForm.token.placeholder = sync.cfg ? "저장됨 (바꿀 때만 입력)" : "github_pat_...";
  syncForm.token.required = !sync.cfg;
  $("#sync-disconnect").hidden = !sync.cfg;
  $("#sync-now").hidden = !sync.cfg;
  renderSyncStatus();
  syncDialog.showModal();
};

syncForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const repo = normalizeRepo(syncForm.repo.value);
  if (!repo) return toast("저장소는 '아이디/저장소이름' 형태로 입력하세요");
  const token = syncForm.token.value.trim() || sync.cfg?.token;
  if (!token) return toast("토큰을 입력하세요");
  const prev = sync.cfg;
  sync.cfg = { repo, token };
  sync.lastOk = null;
  await syncNow();
  if (sync.error && !sync.lastOk) {
    // 연결에 실패하면 예전 설정으로 되돌리고 창을 열어둔다
    sync.cfg = prev;
    const msg = sync.error;
    sync.error = "";
    renderSyncStatus();
    $("#sync-status").textContent = msg;
    $("#sync-status").className = "sync-status error";
    return;
  }
  saveSyncCfg(sync.cfg);
  syncDialog.close();
  toast("동기화를 연결했어요");
});

$("#sync-now").onclick = () => syncNow();
$("#sync-disconnect").onclick = () => {
  if (!confirm("이 기기의 동기화 연결을 끊을까요? (내역은 이 기기와 저장소에 그대로 남아요)")) return;
  sync.cfg = null;
  sync.error = "";
  sync.lastOk = null;
  saveSyncCfg(null);
  renderSyncStatus();
  syncDialog.close();
};

// 앱을 열 때, 다시 볼 때, 인터넷이 돌아올 때, 그리고 켜둔 동안 2분마다 받아온다
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") syncNow(); });
window.addEventListener("online", () => syncNow());
setInterval(() => { if (document.visibilityState === "visible") syncNow(); }, 120000);

renderSyncStatus();
syncNow();
