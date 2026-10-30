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
