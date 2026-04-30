(() => {
  "use strict";

  const chatMessages = document.getElementById("chat-messages");
  const chatInput = document.getElementById("chat-input");
  const sendBtn = document.getElementById("send-btn");
  const micBtn = document.getElementById("mic-btn");
  const connStatus = document.getElementById("connection-status");

  let ws = null;
  let reconnectTimer = null;
  let recognition = null;
  let isRecording = false;

  // ─── Device Toggles ───

  const TOGGLE_KEY = "sonus_disabled_devices";

  function getDisabledDevices() {
    try { return JSON.parse(localStorage.getItem(TOGGLE_KEY)) || []; }
    catch { return []; }
  }

  function setDisabledDevices(list) {
    localStorage.setItem(TOGGLE_KEY, JSON.stringify(list));
  }

  function initToggles() {
    const disabled = getDisabledDevices();
    document.querySelectorAll("[data-toggle]").forEach(cb => {
      const devId = cb.dataset.toggle;
      const card = cb.closest(".device-card");
      if (disabled.includes(devId)) {
        cb.checked = false;
        if (card) card.classList.add("disabled");
      }
      cb.addEventListener("change", () => {
        const list = getDisabledDevices();
        if (cb.checked) {
          const idx = list.indexOf(devId);
          if (idx !== -1) list.splice(idx, 1);
          if (card) card.classList.remove("disabled");
        } else {
          if (!list.includes(devId)) list.push(devId);
          if (card) card.classList.add("disabled");
        }
        setDisabledDevices(list);
        syncDisabledDevices();
      });
    });
    syncDisabledDevices();
  }

  function syncDisabledDevices() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "set_disabled_devices",
        devices: getDisabledDevices(),
      }));
    }
  }

  // ─── WebSocket ───

  function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws`;

    ws = new WebSocket(url);

    ws.onopen = () => {
      connStatus.textContent = "Connected";
      connStatus.className = "status connected";
      syncDisabledDevices();
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    ws.onclose = () => {
      connStatus.textContent = "Disconnected";
      connStatus.className = "status disconnected";
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        console.error("Bad WS message:", e);
      }
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, 3000);
  }

  function sendMessage(text) {
    if (!text.trim()) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      addMessage("Not connected to Sonus. Trying to reconnect...", "system");
      connect();
      return;
    }
    addMessage(text, "user");
    ws.send(JSON.stringify({ type: "chat", content: text }));
    chatInput.value = "";
  }

  // ─── Message Handling ───

  let thinkingEl = null;

  function handleMessage(data) {
    switch (data.type) {
      case "chat_start":
        showThinking();
        break;

      case "chat_complete":
        hideThinking();
        addMessage(data.content, "assistant");
        checkTokenUsage();
        break;

      case "chat_chunk":
        break;

      case "device_update":
        updateDevice(data.device_id, data.state, data.device_type);
        break;

      case "tool_call":
        addMessage(formatToolCall(data.tool, data.params), "system");
        break;

      case "reminder":
        addMessage(`Reminder: ${data.title}${data.description ? " — " + data.description : ""}`, "reminder");
        break;

      case "error":
        hideThinking();
        addMessage(`Error: ${data.message}`, "system");
        break;

      case "pong":
        break;
    }
  }

  function formatToolCall(tool, params) {
    const labels = {
      control_device: () => {
        const id = params.device_id || "";
        const dev = id.split(".").pop();
        return `Controlling ${dev}: ${params.action}${params.value != null ? " → " + params.value : ""}`;
      },
      get_weather: () => "Checking weather...",
      get_calendar_events: () => "Checking calendar...",
      create_calendar_event: () => `Adding to calendar: "${(params.title || "").substring(0, 50)}"`,
      update_calendar_event: () => `Updating calendar event...`,
      delete_calendar_event: () => `Removing calendar event...`,
      search_calendar_events: () => `Searching calendar for "${(params.query || "").substring(0, 40)}"...`,
      get_canvas_assignments: () => "Checking Canvas assignments...",
      store_memory: () => `Remembering: "${(params.content || "").substring(0, 60)}"`,
      recall_memories: () => `Searching memories for "${(params.query || "").substring(0, 40)}"`,
      get_device_states: () => "Checking device states...",
      create_reminder: () => `Setting reminder: "${params.title}"`,
      get_reminders: () => "Checking reminders...",
      get_tasks: () => "Checking your to-do list...",
      create_task: () => `Adding task: "${(params.title || "").substring(0, 40)}"`,
      complete_task: () => "Completing task...",
      delete_task: () => "Deleting task...",
      get_unread_emails: () => "Checking unread emails...",
      get_recent_emails: () => "Checking recent emails...",
      read_email: () => "Reading email...",
      search_emails: () => `Searching emails for "${(params.query || "").substring(0, 40)}"...`,
      send_notification: () => `Sending notification: "${(params.message || "").substring(0, 40)}"`,
      search_food: () => `Looking up nutrition for "${(params.query || "").substring(0, 40)}"...`,
      get_food_nutrition: () => "Getting detailed nutrition info...",
      spotify_play: () => params.query ? `Playing "${(params.query || "").substring(0, 50)}"...` : "Resuming playback...",
      spotify_pause: () => "Pausing music...",
      spotify_skip: () => `Skipping ${params.direction === "previous" ? "back" : "forward"}...`,
      spotify_volume: () => `Setting volume to ${params.volume}%...`,
      spotify_now_playing: () => "Checking what's playing...",
      spotify_search: () => `Searching Spotify for "${(params.query || "").substring(0, 40)}"...`,
      spotify_play_playlist: () => `Playing playlist "${(params.query || "").substring(0, 40)}"...`,
      spotify_shuffle: () => `Turning shuffle ${params.state ? "on" : "off"}...`,
      spotify_devices: () => "Listing Spotify devices...",
      spotify_transfer: () => "Transferring playback...",
    };

    const fn = labels[tool];
    return fn ? fn() : `${tool}(${JSON.stringify(params)})`;
  }

  function addMessage(text, type) {
    const div = document.createElement("div");
    div.className = `message ${type}`;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function showThinking() {
    if (thinkingEl) return;
    thinkingEl = document.createElement("div");
    thinkingEl.className = "thinking";
    thinkingEl.innerHTML = "<span></span><span></span><span></span>";
    chatMessages.appendChild(thinkingEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function hideThinking() {
    if (thinkingEl) {
      thinkingEl.remove();
      thinkingEl = null;
    }
  }

  // ─── Device UI ───

  function updateDevice(deviceId, state, deviceType) {
    const card = document.getElementById(`card-${deviceId}`);
    const stateEl = document.getElementById(`state-${deviceId}`);
    const iconEl = document.getElementById(`icon-${deviceId}`);

    if (!card || !stateEl) return;

    card.className = "device-card";

    if (deviceType === "lock") {
      const locked = state.locked;
      card.classList.add(locked ? "locked" : "unlocked");
      stateEl.textContent = locked ? "Locked" : "Unlocked";

      const shackle = card.querySelector(".lock-shackle");
      if (shackle) {
        shackle.setAttribute("d", locked
          ? "M7 11V7a5 5 0 0 1 10 0v4"
          : "M7 11V7a5 5 0 0 1 9-1"
        );
      }
    }

    if (deviceType === "bulb") {
      const on = state.on;
      card.classList.toggle("active", on);

      const colorTempHex = { warm: "#ffb347", neutral: "#fff4e0", cool: "#87ceeb" };
      const activeColor = state.color || colorTempHex[state.color_temp] || colorTempHex.warm;
      const bulbBody = card.querySelector(".bulb-body");
      const colorDot = document.getElementById(`color-${deviceId}`);

      if (iconEl) {
        iconEl.style.color = "";
        iconEl.style.background = "";
      }

      if (on) {
        if (iconEl) {
          iconEl.style.color = activeColor;
        }
        if (bulbBody) {
          bulbBody.setAttribute("fill", hexToRgba(activeColor, 0.25));
        }
        if (colorDot) {
          colorDot.style.background = activeColor;
          colorDot.style.borderColor = activeColor;
          colorDot.style.boxShadow = `0 0 6px ${hexToRgba(activeColor, 0.5)}`;
        }
      } else {
        if (bulbBody) bulbBody.setAttribute("fill", "none");
        if (colorDot) {
          colorDot.style.background = "";
          colorDot.style.borderColor = "";
          colorDot.style.boxShadow = "";
        }
      }

      let label = on ? "On" : "Off";
      if (on) {
        const colorLabel = state.color
          ? state.color.toUpperCase()
          : capitalize(state.color_temp || "warm");
        label += ` · ${state.brightness}% · ${colorLabel}`;
      }
      stateEl.textContent = label;
    }

    if (deviceType === "fan") {
      const on = state.on;
      card.classList.toggle("active", on);
      if (on) {
        iconEl.classList.add("fan-spinning");
        iconEl.classList.remove("speed-low", "speed-medium", "speed-high");
        iconEl.classList.add(`speed-${state.speed || "medium"}`);
      } else {
        iconEl.classList.remove("fan-spinning", "speed-low", "speed-medium", "speed-high");
      }
      stateEl.textContent = on ? `On · ${capitalize(state.speed || "medium")}` : "Off";
    }

    if (deviceType === "ac") {
      const on = state.on;
      card.classList.toggle("active", on);
      if (on) {
        const mode = capitalize(state.mode || "cool");
        const temp = state.target_temp || 72;
        const fan = state.fan_speed || "auto";
        stateEl.textContent = `${temp}°F · ${mode} · Fan ${capitalize(fan)}`;
        if (iconEl) {
          const modeColors = { cool: "#87ceeb", heat: "#ff7043", fan: "#aaa", auto: "#8bc34a", dry: "#ffca28" };
          iconEl.style.color = modeColors[state.mode] || "#87ceeb";
        }
      } else {
        stateEl.textContent = "Off";
        if (iconEl) iconEl.style.color = "";
      }
    }
  }

  function capitalize(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function hexToRgba(hex, alpha) {
    const c = hex.replace("#", "");
    const r = parseInt(c.substring(0, 2), 16) || 0;
    const g = parseInt(c.substring(2, 4), 16) || 0;
    const b = parseInt(c.substring(4, 6), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  // ─── Speech Recognition ───

  function initSpeech() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      micBtn.title = "Speech not supported in this browser";
      micBtn.style.opacity = "0.4";
      micBtn.style.cursor = "not-allowed";
      return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      chatInput.value = transcript;
      sendMessage(transcript);
    };

    recognition.onend = () => {
      isRecording = false;
      micBtn.classList.remove("recording");
    };

    recognition.onerror = (event) => {
      isRecording = false;
      micBtn.classList.remove("recording");
      if (event.error !== "no-speech" && event.error !== "aborted") {
        console.error("Speech error:", event.error);
      }
    };
  }

  function toggleRecording() {
    if (!recognition) return;
    if (isRecording) {
      recognition.stop();
    } else {
      recognition.start();
      isRecording = true;
      micBtn.classList.add("recording");
    }
  }

  // ─── Event Listeners ───

  sendBtn.addEventListener("click", () => sendMessage(chatInput.value));

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(chatInput.value);
    }
  });

  micBtn.addEventListener("click", toggleRecording);

  // ─── Keepalive ───

  setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ping" }));
    }
  }, 30000);

  // ─── Spotify Status ───

  async function checkSpotifyStatus() {
    try {
      const res = await fetch("/api/spotify/status");
      const data = await res.json();
      const card = document.getElementById("card-spotify");
      const stateEl = document.getElementById("state-spotify");
      const iconEl = document.getElementById("icon-spotify");
      if (!card || !stateEl) return;

      const npEl = document.getElementById("now-playing");
      const volBar = document.getElementById("volume-bar");
      const volFill = document.getElementById("volume-fill");
      card.className = "device-card";

      if (data.authenticated) {
        card.classList.add("active");
        if (data.now_playing) {
          const np = data.now_playing;
          stateEl.textContent = np.is_playing ? "Playing" : "Paused";
          if (npEl) npEl.textContent = `${np.track} — ${np.artist}`;
          if (iconEl) iconEl.style.color = "#1db954";
          if (volBar && volFill && np.volume != null) {
            volBar.classList.add("visible");
            volFill.style.width = np.volume + "%";
          }
        } else {
          stateEl.textContent = "Connected";
          if (npEl) npEl.textContent = "";
          if (iconEl) iconEl.style.color = "";
          if (volBar) volBar.classList.remove("visible");
        }
      } else if (data.configured) {
        stateEl.innerHTML = '<a href="/api/spotify/login" style="color:#888;text-decoration:underline">Click to connect</a>';
        if (npEl) npEl.textContent = "";
        if (volBar) volBar.classList.remove("visible");
      } else {
        stateEl.textContent = "Not configured";
        if (npEl) npEl.textContent = "";
        if (volBar) volBar.classList.remove("visible");
      }
    } catch (e) {
      /* ignore */
    }
  }

  // ─── Token Usage ───

  async function checkTokenUsage() {
    try {
      const res = await fetch("/api/token-usage");
      if (!res.ok) return;
      const data = await res.json();
      const el = document.getElementById("token-usage");
      const fillEl = document.getElementById("token-usage-fill");
      const wrapEl = document.querySelector(".token-usage-wrap");
      if (!el || !wrapEl) return;

      const tooltip = `${data.total_tokens.toLocaleString()} tokens used | Prompt: ${data.prompt_tokens.toLocaleString()} | Completion: ${data.completion_tokens.toLocaleString()} | Cost: $${data.cost.toFixed(4)} | Requests: ${data.requests}${!data.budget ? " — Set DAILY_TOKEN_BUDGET for %" : ""}`;
      wrapEl.title = tooltip;

      if (data.budget && data.budget > 0) {
        const pct = Math.min((data.total_tokens / data.budget) * 100, 100);
        const pctStr = pct < 0.1 ? "0%" : pct < 1 ? pct.toFixed(1) + "%" : Math.round(pct) + "%";
        el.textContent = pctStr;
        if (fillEl) fillEl.style.width = pct + "%";
        wrapEl.classList.remove("warning", "danger");
        if (pct >= 90) wrapEl.classList.add("danger");
        else if (pct >= 70) wrapEl.classList.add("warning");
      } else {
        el.textContent = "—";
        if (fillEl) fillEl.style.width = "0%";
        wrapEl.classList.remove("warning", "danger");
      }
    } catch { /* ignore */ }
  }

  // ─── Boot ───

  initToggles();
  initSpeech();
  connect();
  checkSpotifyStatus();
  setInterval(checkSpotifyStatus, 10000);
  checkTokenUsage();
  setInterval(checkTokenUsage, 15000);
})();
