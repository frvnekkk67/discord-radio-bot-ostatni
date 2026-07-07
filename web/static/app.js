const state = {
  token: localStorage.getItem("dashboard_token") || "",
  guildId: null,
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${state.token}`,
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    logout();
    throw new Error("Nieprawidłowy token");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Błąd ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function showDashboard() {
  $("login-screen").classList.add("hidden");
  $("dashboard-screen").classList.remove("hidden");
}

function showLogin(message) {
  $("dashboard-screen").classList.add("hidden");
  $("login-screen").classList.remove("hidden");
  if (message) {
    $("login-error").textContent = message;
    $("login-error").classList.remove("hidden");
  }
  if (state.pollTimer) clearInterval(state.pollTimer);
}

function logout() {
  state.token = "";
  localStorage.removeItem("dashboard_token");
  showLogin();
}

async function login() {
  const token = $("token-input").value.trim();
  if (!token) return;
  state.token = token;
  try {
    const guilds = await api("/api/guilds");
    localStorage.setItem("dashboard_token", token);
    populateGuilds(guilds);
    showDashboard();
    startPolling();
  } catch (e) {
    $("login-error").textContent = "Nieprawidłowy token dostępu.";
    $("login-error").classList.remove("hidden");
  }
}

function populateGuilds(guilds) {
  const select = $("guild-select");
  select.innerHTML = "";
  guilds.forEach((g) => {
    const opt = document.createElement("option");
    opt.value = g.id;
    opt.textContent = g.name;
    select.appendChild(opt);
  });
  if (guilds.length) {
    state.guildId = guilds[0].id;
    loadVoiceChannels();
    refreshStatus();
    loadPlaylist();
  }
}

async function loadVoiceChannels() {
  if (!state.guildId) return;
  const channels = await api(`/api/voice_channels?guild_id=${state.guildId}`);
  const select = $("channel-select");
  select.innerHTML = "";
  channels.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    select.appendChild(opt);
  });
}

async function refreshStatus() {
  if (!state.guildId) return;
  try {
    const s = await api(`/api/status?guild_id=${state.guildId}`);
    $("now-playing").textContent = s.now_playing || "Nic teraz nie gra";
    $("channel-info").textContent = s.connected ? `Połączony: ${s.channel}` : "Niepołączony";
    $("volume-slider").value = s.volume;
    $("volume-value").textContent = s.volume;
    if (document.activeElement !== $("eq-select")) {
      $("eq-select").value = s.eq_preset;
    }

    const queueList = $("queue-list");
    queueList.innerHTML = "";
    (s.queue || []).forEach((q) => {
      const li = document.createElement("li");
      li.textContent = q;
      queueList.appendChild(li);
    });

    const countdown = $("pause-countdown");
    if (s.paused_until && s.paused_until * 1000 > Date.now()) {
      const secondsLeft = Math.max(0, Math.round((s.paused_until * 1000 - Date.now()) / 1000));
      countdown.textContent = `Wznowienie za ~${secondsLeft}s`;
      countdown.classList.remove("hidden");
    } else {
      countdown.classList.add("hidden");
    }
  } catch (e) {
    // ciche niepowodzenie odświeżenia - spróbujemy ponownie przy kolejnym pollu
  }
}

async function loadPlaylist() {
  if (!state.guildId) return;
  const playlist = await api(`/api/playlist?guild_id=${state.guildId}`);
  const list = $("playlist-list");
  list.innerHTML = "";
  playlist.forEach((t) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = t.title;
    const btn = document.createElement("button");
    btn.textContent = "✕";
    btn.onclick = async () => {
      await api(`/api/playlist/${t.id}?guild_id=${state.guildId}`, { method: "DELETE" });
      loadPlaylist();
    };
    li.appendChild(span);
    li.appendChild(btn);
    list.appendChild(li);
  });
}

async function loadEqPresets() {
  const { presets } = await api("/api/eq_presets");
  const select = $("eq-select");
  select.innerHTML = "";
  presets.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    select.appendChild(opt);
  });
}

function startPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(refreshStatus, 4000);
}

// ---------- Event listenery ----------

$("login-btn").onclick = login;
$("token-input").addEventListener("keydown", (e) => { if (e.key === "Enter") login(); });
$("logout-btn").onclick = logout;

$("guild-select").onchange = (e) => {
  state.guildId = e.target.value;
  loadVoiceChannels();
  refreshStatus();
  loadPlaylist();
};

$("skip-btn").onclick = () => api("/api/skip", { method: "POST", body: JSON.stringify({ guild_id: state.guildId }) }).then(refreshStatus);
$("resume-btn").onclick = () => api("/api/resume", { method: "POST", body: JSON.stringify({ guild_id: state.guildId }) }).then(refreshStatus);
$("pause-btn").onclick = () => {
  const minutes = parseFloat($("pause-minutes").value) || 1;
  api("/api/pause_temp", { method: "POST", body: JSON.stringify({ guild_id: state.guildId, minutes }) }).then(refreshStatus);
};

$("playnow-btn").onclick = async () => {
  const query = $("playnow-input").value.trim();
  if (!query) return;
  await api("/api/play_now", { method: "POST", body: JSON.stringify({ guild_id: state.guildId, query }) });
  $("playnow-input").value = "";
  refreshStatus();
};

$("connect-btn").onclick = async () => {
  const channel_id = $("channel-select").value;
  if (!channel_id) return;
  await api("/api/connect", { method: "POST", body: JSON.stringify({ guild_id: state.guildId, channel_id }) });
  refreshStatus();
};
$("disconnect-btn").onclick = () => api("/api/disconnect", { method: "POST", body: JSON.stringify({ guild_id: state.guildId }) }).then(refreshStatus);

let volumeDebounce;
$("volume-slider").oninput = (e) => {
  $("volume-value").textContent = e.target.value;
  clearTimeout(volumeDebounce);
  volumeDebounce = setTimeout(() => {
    api("/api/volume", { method: "POST", body: JSON.stringify({ guild_id: state.guildId, value: parseInt(e.target.value) }) });
  }, 300);
};

$("eq-select").onchange = (e) => {
  api("/api/eq", { method: "POST", body: JSON.stringify({ guild_id: state.guildId, preset: e.target.value }) });
};

$("playlist-add-btn").onclick = async () => {
  const url = $("playlist-url").value.trim();
  const title = $("playlist-title").value.trim();
  if (!url) return;
  await api("/api/playlist/add", { method: "POST", body: JSON.stringify({ guild_id: state.guildId, url, title: title || null }) });
  $("playlist-url").value = "";
  $("playlist-title").value = "";
  loadPlaylist();
};

// ---------- Start ----------

(async function init() {
  loadEqPresets();
  if (state.token) {
    try {
      const guilds = await api("/api/guilds");
      populateGuilds(guilds);
      showDashboard();
      startPolling();
      return;
    } catch (e) {
      // token nieważny - pokaż ekran logowania
    }
  }
  showLogin();
})();
