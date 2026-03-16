// ===============================
// Persistent Session ID
// ===============================
let sessionId = localStorage.getItem("bot_session_id");

if (!sessionId) {
  sessionId = "sess_" + Math.random().toString(36).substring(2, 10);
  localStorage.setItem("bot_session_id", sessionId);
}

// ===============================
// Event Buffer
// ===============================
let events = [];
let isBlocked = false;

function logEvent(event) {
  if (!isBlocked) {
    events.push(event);
  }
}

// ===============================
// Mouse Move (THROTTLED)
// ===============================
let lastMouseTime = 0;

document.addEventListener("mousemove", (e) => {
  const now = Date.now();

  // Only log every 50ms (prevents 1000+ events/sec)
  if (now - lastMouseTime > 50) {
    lastMouseTime = now;

    logEvent({
      type: "mousemove",
      x: e.clientX,
      y: e.clientY,
      timestamp: now
    });
  }
});

// ===============================
// Click Tracking
// ===============================
document.addEventListener("click", (e) => {
  logEvent({
    type: "click",
    x: e.clientX,
    y: e.clientY,
    timestamp: Date.now()
  });
});

// ===============================
// Scroll Tracking (THROTTLED)
// ===============================
let lastScrollTime = 0;

window.addEventListener("scroll", () => {
  const now = Date.now();

  if (now - lastScrollTime > 100) {
    lastScrollTime = now;

    logEvent({
      type: "scroll",
      scrollY: window.scrollY,
      timestamp: now
    });
  }
});

// ===============================
// Keyboard Timing
// ===============================
let lastKeyTime = null;

document.addEventListener("keydown", () => {
  const now = Date.now();
  let delay = null;

  if (lastKeyTime !== null) {
    delay = now - lastKeyTime;
  }

  lastKeyTime = now;

  logEvent({
    type: "keydown",
    keyDelay: delay,
    timestamp: now
  });
});

// ===============================
// Send Data Every 3 Seconds
// ===============================
setInterval(() => {
  if (events.length === 0 || isBlocked) return;

  fetch("http://127.0.0.1:8000/collect", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      session_id: sessionId,
      events: events
    })
  })
    .then(res => res.json())
    .then(data => {
      console.log("Server response:", data);

      // If backend says BOT → stop tracking
      if (data.prediction === "BOT") {
        console.warn("Bot detected. Blocking session.");
        isBlocked = true;

        // Optional: disable page interaction
        document.body.innerHTML = "<h1>Access Denied</h1>";
      }

      events = []; // Clear buffer
    })
    .catch(err => console.error("Error sending data", err));

}, 3000);
