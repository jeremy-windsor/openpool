// ---------- Theme toggle (Light -> Dark -> Outdoor) ----------
(function () {
  var THEMES = ["light", "dark", "outdoor"];
  var META = { light: "#0E7CA6", dark: "#0F2230", outdoor: "#FFFFFF" };

  function current() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("op-theme", theme); } catch (e) {}
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta && META[theme]) meta.setAttribute("content", META[theme]);
    var btn = document.getElementById("theme-toggle");
    if (btn) btn.title = "Theme: " + theme + " (tap to change)";
  }

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    apply(current());
    toggle.addEventListener("click", function () {
      var next = THEMES[(THEMES.indexOf(current()) + 1) % THEMES.length];
      apply(next);
    });
  }
})();

// ---------- Humanize pool-local timestamps ----------
// data-localtime holds an ISO string already in the pool's local wall time,
// e.g. "2026-06-07T17:02:19-07:00". We only format the wall-clock portion.
(function () {
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function format(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || "");
    if (!m) return null;
    var y = +m[1], mo = +m[2] - 1, d = +m[3], h = +m[4], min = +m[5];
    var ampm = h < 12 ? "AM" : "PM";
    var h12 = h % 12 || 12;
    var time = h12 + ":" + (min < 10 ? "0" + min : min) + " " + ampm;

    var now = new Date();
    var sameYear = y === now.getFullYear();
    var sameDay = sameYear && mo === now.getMonth() && d === now.getDate();
    var yest = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
    var isYest = y === yest.getFullYear() && mo === yest.getMonth() && d === yest.getDate();

    if (sameDay) return "Today, " + time;
    if (isYest) return "Yesterday, " + time;
    var date = MONTHS[mo] + " " + d + (sameYear ? "" : ", " + y);
    return date + ", " + time;
  }

  var nodes = document.querySelectorAll("[data-localtime]");
  for (var i = 0; i < nodes.length; i++) {
    var pretty = format(nodes[i].getAttribute("data-localtime"));
    if (pretty) nodes[i].textContent = pretty;
  }
})();

// ---------- Prefill the addition form from query params ----------
// Lets a dashboard/calculator "Log this dose" link carry chemical/amount/unit
// into the form without a backend round-trip. Only fills empty fields.
(function () {
  var form = document.querySelector('form[action="/additions/new"]');
  if (!form) return;
  var params = new URLSearchParams(location.search);
  ["chemical", "amount", "unit", "reason", "strength_percent"].forEach(function (name) {
    if (!params.has(name)) return;
    var field = form.elements[name];
    if (!field) return;
    // Selects always report a value (the first option), so set them directly.
    if (field.tagName === "SELECT" || !field.value) field.value = params.get(name);
  });
})();

// ---------- Prefill the maintenance form event type from query params ----------
(function () {
  var form = document.querySelector('form[action="/maintenance/new"]');
  if (!form) return;
  var params = new URLSearchParams(location.search);
  if (params.has("event_type") && form.elements.event_type) {
    form.elements.event_type.value = params.get("event_type");
  }
})();

// ---------- Calculator: show only the fields the chosen goal uses ----------
// Elements with data-goals="raise_fc slam_fc" are visible only for those
// goals; everything without data-goals is always visible.
(function () {
  var goalSelect = document.getElementById("calc-goal");
  var form = document.getElementById("calc-form");
  if (!goalSelect || !form) return;

  function update() {
    var goal = goalSelect.value;
    var nodes = form.querySelectorAll("[data-goals]");
    for (var i = 0; i < nodes.length; i++) {
      var show = nodes[i].getAttribute("data-goals").split(" ").indexOf(goal) !== -1;
      nodes[i].style.display = show ? "" : "none";
    }
  }

  goalSelect.addEventListener("change", update);
  update();
})();

// ---------- Service worker ----------
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/static/sw.js").catch(function () {});
  });
}
