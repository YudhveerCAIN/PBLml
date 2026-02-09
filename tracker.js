// Generate a simple session ID
const sessionId = "sess_" + Math.random().toString(36).substring(2, 10);

// Store all behavior events
const events = [];

function logEvent(event) {
  events.push(event);
}

// Mouse movement tracking
document.addEventListener("mousemove", (e) => {
  logEvent({
    type: "mousemove",
    x: e.clientX,
    y: e.clientY,
    timestamp: Date.now()
  });
});

// Click tracking
document.addEventListener("click", (e) => {
  logEvent({
    type: "click",
    x: e.clientX,
    y: e.clientY,
    timestamp: Date.now()
  });
});

// Scroll tracking
window.addEventListener("scroll", () => {
  logEvent({
    type: "scroll",
    scrollY: window.scrollY,
    timestamp: Date.now()
  });
});

// Keyboard timing tracking
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

// Periodically log summary (for testing only)
setInterval(() => {
  if (events.length === 0) return;

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
    console.log("Sent to server:", data);
    events.length = 0; // clear after sending
  })
  .catch(err => console.error("Error sending data", err));
}, 5000);
