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
        if (span) span.textContent = "Imenakiliwa";
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
})();
