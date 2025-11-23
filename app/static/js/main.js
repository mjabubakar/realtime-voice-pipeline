let ws = null;
let messagesSent = 0;
let messagesReceived = 0;
let startTime = 0;
let currentTab = "tts";

function switchTab(tab) {
  currentTab = tab;
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.remove("active"));
  document
    .querySelectorAll(".tab-content")
    .forEach((c) => c.classList.remove("active"));

  event.target.classList.add("active");
  document.getElementById(tab + "-content").classList.add("active");
}

function addLog(message, type = "info") {
  const log = document.getElementById("log");
  const entry = document.createElement("div");
  entry.className = `log-entry log-${type}`;
  entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;
}

function updateStats() {
  document.getElementById("messagesSent").textContent = messagesSent;
  if (messagesReceived > 0) {
    const hitRate = Math.round((messagesReceived / messagesSent) * 100);
    document.getElementById("cacheHit").textContent = hitRate;
  }
}

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/voice`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    addLog("✓ WebSocket connected", "info");
    document.getElementById("status").textContent = "Connected";
    document.getElementById("status").className = "status status-connected";

    // Enable controls based on tab
    if (currentTab === "tts") {
      document.getElementById("ttsConnectBtn").disabled = true;
      document.getElementById("ttsDisconnectBtn").disabled = false;
      document.getElementById("ttsInput").disabled = false;
      document.getElementById("ttsSendBtn").disabled = false;
    } else if (currentTab === "stt") {
      document.getElementById("sttConnectBtn").disabled = true;
      document.getElementById("sttDisconnectBtn").disabled = false;
      document.getElementById("audioFile").disabled = false;
      document.getElementById("sttSendBtn").disabled = false;
    }
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    messagesReceived++;

    if (data.type === "audio") {
      const latency = Date.now() - startTime;
      addLog(
        `← TTS: Received audio (${data.duration?.toFixed(2)}s, cached: ${
          data.cached
        })`,
        "received"
      );

      if (data.sentiment) {
        addLog(
          `  Sentiment: ${data.sentiment.polarity.toFixed(2)} (${
            data.sentiment.label
          })`,
          "info"
        );
      }
    } else if (data.type === "transcript") {
      const latency = Date.now() - startTime;
      addLog(
        `← STT: "${data.text}" (${data.language}, ${latency}ms)`,
        "received"
      );
      document.getElementById("transcriptOutput").value = data.text;

      if (data.sentiment) {
        addLog(
          `  Sentiment: ${data.sentiment.polarity.toFixed(2)} (${
            data.sentiment.label
          })`,
          "info"
        );
      }
    } else if (data.type === "error") {
      addLog(`✗ Error: ${data.message}`, "error");
    }

    updateStats();
  };

  ws.onerror = (error) => {
    addLog("✗ WebSocket error", "error");
  };

  ws.onclose = () => {
    addLog("✗ WebSocket disconnected", "info");
    document.getElementById("status").textContent = "Disconnected";
    document.getElementById("status").className = "status status-disconnected";
    document.getElementById("ttsConnectBtn").disabled = false;
    document.getElementById("ttsDisconnectBtn").disabled = true;
    document.getElementById("ttsInput").disabled = true;
    document.getElementById("ttsSendBtn").disabled = true;

    document.getElementById("sttConnectBtn").disabled = false;
    document.getElementById("sttDisconnectBtn").disabled = true;
    document.getElementById("audioFile").disabled = true;
    document.getElementById("sttSendBtn").disabled = true;
  };
}

function disconnect() {
  if (ws) {
    ws.close();
    ws = null;
  }
}

function sendTTS() {
  const input = document.getElementById("ttsInput");
  const text = input.value.trim();

  if (!text) {
    addLog("✗ Please enter text", "error");
    return;
  }

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    addLog("✗ WebSocket not connected", "error");
    return;
  }

  startTime = Date.now();
  messagesSent++;

  ws.send(
    JSON.stringify({
      type: "text",
      text: text,
    })
  );

  addLog(`→ TTS: "${text}"`, "sent");
  input.value = "";
  updateStats();
}

function sendSTT() {
  const fileInput = document.getElementById("audioFile");
  const file = fileInput.files[0];

  if (!file) {
    addLog("✗ Please select an audio file", "error");
    return;
  }

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    addLog("✗ WebSocket not connected", "error");
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const base64Audio = e.target.result.split(",")[1];

    startTime = Date.now();
    messagesSent++;

    ws.send(
      JSON.stringify({
        type: "audio",
        audio: base64Audio,
      })
    );

    addLog(
      `→ STT: Uploaded ${file.name} (${(file.size / 1024).toFixed(1)} KB)`,
      "sent"
    );
    updateStats();
  };
  reader.readAsDataURL(file);
}

// Allow Enter key to send TTS
document.addEventListener("DOMContentLoaded", () => {
  const ttsInput = document.getElementById("ttsInput");
  if (ttsInput) {
    ttsInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        sendTTS();
      }
    });
  }
});
