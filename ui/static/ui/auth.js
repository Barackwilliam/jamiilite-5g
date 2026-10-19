// JamiiLite 5G: kuingia na kujisajili.
// Simu ya mmiliki inapokea mauzo, password inaweza kuonyeshwa, na nguvu yake inapimwa.
(function () {
  "use strict";

  var body = document.body;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var money = function (n) { return Math.round(n).toLocaleString("en-US"); };

  // ---- Matukio kwenye simu ya mmiliki ----
  var feed = document.querySelector("[data-auth-feed]");
  var tpl = document.querySelector("[data-auth-events]");
  var balanceEl = document.querySelector("[data-auth-balance]");
  if (feed && tpl && balanceEl && !reduceMotion) {
    var events = Array.prototype.slice.call(tpl.content.children);
    var balance = parseInt(balanceEl.textContent.replace(/,/g, ""), 10) || 0;
    var next = 0;
    var countUp = function (from, to) {
      var start = performance.now();
      (function step(now) {
        var p = Math.min(1, (now - start) / 700);
        balanceEl.textContent = money(from + (to - from) * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(step);
      })(start);
      var box = balanceEl.parentNode;
      box.classList.remove("is-bump"); void box.offsetWidth; box.classList.add("is-bump");
    };
    setInterval(function () {
      if (document.hidden) return;
      var li = events[next % events.length].cloneNode(true);
      next += 1;
      feed.insertBefore(li, feed.firstChild);
      while (feed.children.length > 2) feed.removeChild(feed.lastChild);
      var amount = parseInt(li.dataset.amount || "0", 10);
      if (amount) { countUp(balance, balance + amount); balance += amount; }
    }, 2800);
  }

  // ---- Onyesha / ficha password ----
  var EYE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var EYE_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l18 18"/><path d="M10.6 5.1A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.1M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7a9.9 9.9 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
  document.querySelectorAll('.auth-card input[type="password"]').forEach(function (input) {
    var wrap = document.createElement("span");
    wrap.className = "pw-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    input.setAttribute("data-pw", "");
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pw-toggle";
    var render = function () {
      var shown = input.type === "text";
      btn.innerHTML = shown ? EYE_OFF : EYE;
      btn.setAttribute("aria-label", shown ? body.dataset.hideLabel : body.dataset.showLabel);
      btn.setAttribute("aria-pressed", String(shown));
    };
    btn.addEventListener("click", function () {
      input.type = input.type === "password" ? "text" : "password";
      render();
      input.focus();
    });
    render();
    wrap.appendChild(btn);
  });

  // ---- Nguvu ya password (kwenye kujisajili tu) ----
  var form = document.querySelector(".auth-card form[data-strength]");
  var pw = document.getElementById("id_password1");
  if (form && pw) {
    var labels = form.dataset.strength.split("|");
    var meter = document.createElement("div");
    meter.className = "pw-meter";
    meter.setAttribute("aria-live", "polite");
    meter.innerHTML = '<span class="pw-meter-bars"><i></i><i></i><i></i><i></i></span><span data-pw-label></span>';
    pw.closest(".pw-wrap").insertAdjacentElement("afterend", meter);
    var label = meter.querySelector("[data-pw-label]");
    var score = function (v) {
      if (!v) return 0;
      var s = 0;
      if (v.length >= 8) s++;
      if (v.length >= 12) s++;
      if (/[a-z]/.test(v) && /[A-Z]/.test(v)) s++;
      if (/\d/.test(v)) s++;
      if (/[^A-Za-z0-9]/.test(v)) s++;
      if (v.length < 8) s = Math.min(s, 1);
      return Math.max(1, Math.min(4, s));
    };
    var update = function () {
      var level = score(pw.value);
      meter.dataset.level = level;
      label.textContent = level ? labels[level - 1] : "";
    };
    pw.addEventListener("input", update);
    update();
  }

  // ---- Kitufe kinazunguka wakati fomu inatumwa ----
  document.querySelectorAll(".auth-card form").forEach(function (f) {
    f.addEventListener("submit", function () {
      var b = f.querySelector(".auth-submit");
      if (b) b.classList.add("is-loading");
    });
  });
  // Ukirudi kwa "back", kitufe kisibaki kinazunguka.
  window.addEventListener("pageshow", function () {
    document.querySelectorAll(".auth-submit.is-loading").forEach(function (b) { b.classList.remove("is-loading"); });
  });
})();
