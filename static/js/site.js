// Tovuti ya hadhara: kichwa kinachobadilika ukishuka, na mwanga unaofuata kipanya kwenye kadi.
(function () {
  "use strict";
  var bar = document.querySelector(".topbar");
  if (bar) {
    var onScroll = function () { bar.classList.toggle("is-scrolled", window.scrollY > 8); };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  if (!window.matchMedia("(hover: hover)").matches) return;
  document.addEventListener("pointermove", function (event) {
    var card = event.target.closest && event.target.closest("[data-spot]");
    if (!card) return;
    var box = card.getBoundingClientRect();
    card.style.setProperty("--mx", event.clientX - box.left + "px");
    card.style.setProperty("--my", event.clientY - box.top + "px");
  }, { passive: true });
})();

// Menyu ya pembeni: inafunguka kushoto, inafungwa kwa Esc, kwa kugusa nje, au kwa ×.
(function () {
  "use strict";
  var side = document.getElementById("menyu");
  var opener = document.querySelector("[data-side-open]");
  var backdrop = document.querySelector(".side-backdrop");
  if (!side || !opener || !backdrop) return;
  var open = function () {
    side.classList.add("is-open");
    backdrop.hidden = false;
    document.body.classList.add("side-locked");
    opener.setAttribute("aria-expanded", "true");
    var first = side.querySelector(".side-nav a");
    (first || side).focus();
  };
  var close = function () {
    side.classList.remove("is-open");
    backdrop.hidden = true;
    document.body.classList.remove("side-locked");
    opener.setAttribute("aria-expanded", "false");
    opener.focus();
  };
  opener.addEventListener("click", function (e) { e.preventDefault(); open(); });
  document.querySelectorAll("[data-side-close]").forEach(function (el) {
    el.addEventListener("click", function (e) { e.preventDefault(); close(); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && side.classList.contains("is-open")) close();
  });
  // Kiungo cha ukurasa uleule (mfano #bei) kinafunga menyu kisha kinashuka hapo.
  side.querySelectorAll(".side-nav a").forEach(function (a) {
    a.addEventListener("click", function () { if (side.classList.contains("is-open")) close(); });
  });
})();
