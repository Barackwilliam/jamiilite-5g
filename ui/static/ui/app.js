// JamiiLite 5G dashboards: tooltip za chati, kunakili, kuthibitisha na kuchapisha.
(function () {
  "use strict";

  // Tooltip ya kila bar: inaonekana ukipita na kipanya au ukifika kwa Tab.
  document.querySelectorAll("[data-chart]").forEach(function (chart) {
    var tip = chart.querySelector(".chart-tooltip");
    if (!tip) return;
    var label = tip.querySelector("strong");
    var value = tip.querySelector("span");

    function show(bar) {
      var box = chart.getBoundingClientRect();
      var mark = (bar.querySelector(".chart-mark") || bar.querySelector(".chart-hit")).getBoundingClientRect();
      label.textContent = bar.dataset.label;
      value.textContent = bar.dataset.value;
      tip.hidden = false;
      var half = tip.offsetWidth / 2;
      var x = mark.left + mark.width / 2 - box.left;
      tip.style.left = Math.min(Math.max(x, half), box.width - half) + "px";
      tip.style.top = Math.max(mark.top - box.top, 24) + "px";
    }
    function hide() { tip.hidden = true; }

    chart.querySelectorAll(".chart-bar").forEach(function (bar) {
      bar.addEventListener("mouseenter", function () { show(bar); });
      bar.addEventListener("focus", function () { show(bar); });
      bar.addEventListener("mouseleave", hide);
      bar.addEventListener("blur", hide);
    });
  });

  // Kunakili maandishi, mfano mstari wa usanidi wa MikroTik.
  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var source = document.querySelector(button.dataset.copy);
      if (!source) return;
      var text = source.textContent.trim();
      var done = function () {
        var span = button.querySelector("span");
        var before = span ? span.textContent : "";
        button.classList.add("is-copied");
        if (span) span.textContent = button.dataset.copied || "Imenakiliwa";
        setTimeout(function () {
          button.classList.remove("is-copied");
          if (span) span.textContent = before;
        }, 1800);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done);
      } else {
        // http (maabara ya ndani): clipboard API haipo, tumia njia ya zamani.
        var area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        try { document.execCommand("copy"); done(); } finally { area.remove(); }
      }
    });
  });

  // Vitendo vizito vinaomba uthibitisho kwanza.
  document.addEventListener("click", function (event) {
    var target = event.target.closest("[data-confirm]");
    if (target && !window.confirm(target.dataset.confirm)) event.preventDefault();
  });

  document.querySelectorAll("[data-print]").forEach(function (button) {
    button.addEventListener("click", function () { window.print(); });
  });

  // Funga menyu ya simu ukibonyeza Esc.
  document.addEventListener("keydown", function (event) {
    var toggle = document.getElementById("nav-toggle");
    if (event.key === "Escape" && toggle) toggle.checked = false;
  });

  // Ukurasa wa kuunganisha router: unauliza kila sekunde 5, na router ikionekana unajifungua upya.
  var wait = document.querySelector("[data-router-wait]");
  if (wait && window.fetch) {
    var check = function () {
      if (document.hidden) return;
      fetch(wait.dataset.routerWait, { headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (data && data.seen) { wait.classList.add("is-connected"); setTimeout(function () { location.reload(); }, 900); }
        })
        .catch(function () {});
    };
    setInterval(check, 5000);
  }

  // Salio: kitufe cha jicho kinaficha na kuonyesha kiasi, kama app za pesa. Chaguo linakumbukwa kwenye kifaa hiki.
  var balanceToggle = document.querySelector("[data-balance-toggle]");
  if (balanceToggle) {
    var amounts = document.querySelectorAll("[data-balance]");
    var setHidden = function (hidden) {
      amounts.forEach(function (el) {
        if (!el.dataset.amount) el.dataset.amount = el.textContent;
        el.textContent = hidden ? "Tsh ••••••" : el.dataset.amount;
      });
      balanceToggle.setAttribute("aria-pressed", hidden ? "true" : "false");
      balanceToggle.setAttribute("aria-label", hidden ? balanceToggle.dataset.labelShow : balanceToggle.dataset.labelHide);
      balanceToggle.classList.toggle("is-hidden", hidden);
    };
    var stored = false;
    try { stored = window.localStorage.getItem("jl-balance-hidden") === "1"; } catch (e) {}
    setHidden(stored);
    balanceToggle.addEventListener("click", function () {
      var hidden = balanceToggle.getAttribute("aria-pressed") !== "true";
      setHidden(hidden);
      try { window.localStorage.setItem("jl-balance-hidden", hidden ? "1" : "0"); } catch (e) {}
    });
  }
})();

/* Kutoa pesa: vitufe vya kiasi cha haraka, na kitufe kinachoonyesha kiasi. */
(function () {
  var form = document.querySelector("[data-withdraw]");
  if (!form) return;
  var input = form.querySelector("input[name=amount]");
  var button = form.querySelector("[data-withdraw-button] span");
  var label = form.querySelector("[data-withdraw-button]").dataset.label;
  var original = button.textContent;
  var chips = form.querySelectorAll("[data-amount]");
  function sync() {
    var value = parseInt(input.value, 10);
    button.textContent = value > 0 ? label.replace("%(amount)s", value.toLocaleString("en-US")) : original;
    chips.forEach(function (chip) { chip.classList.toggle("is-picked", chip.dataset.amount === String(value)); });
  }
  chips.forEach(function (chip) {
    chip.addEventListener("click", function () { input.value = chip.dataset.amount; sync(); input.focus(); });
  });
  input.addEventListener("input", sync);
  sync();
})();

/* Vocha: vitufe vya idadi, na kitufe kinachoonyesha idadi. */
(function () {
  var form = document.querySelector("[data-voucher-form]");
  if (!form) return;
  var input = form.querySelector("input[name=count]");
  var button = form.querySelector("[data-voucher-button] span");
  var label = form.querySelector("[data-voucher-button]").dataset.label;
  var chips = form.querySelectorAll("[data-count]");
  function sync() {
    var value = parseInt(input.value, 10);
    if (value > 0) button.textContent = label.replace("%(n)s", value);
    chips.forEach(function (chip) { chip.classList.toggle("is-picked", chip.dataset.count === String(value)); });
  }
  chips.forEach(function (chip) {
    chip.addEventListener("click", function () { input.value = chip.dataset.count; sync(); });
  });
  input.addEventListener("input", sync);
  sync();
})();
