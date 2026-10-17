// Mwongozo unaocheza kama "stories": hatua zinajiendesha, zinaweza kusimamishwa,
// na mtumiaji anagusa kulia/kushoto kwenda mbele/nyuma. Bila JavaScript,
// hatua zote zinaonekana kama orodha ya kawaida.
(function () {
  var player = document.getElementById("player");
  if (!player) return;

  var scenes = Array.prototype.slice.call(player.querySelectorAll(".scene"));
  var barsBox = player.querySelector(".player-bars");
  var playBtn = player.querySelector(".ctrl-play");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var bars = scenes.map(function () {
    var bar = document.createElement("span");
    bar.className = "bar";
    bar.appendChild(document.createElement("i"));
    barsBox.appendChild(bar);
    return bar.firstChild;
  });

  var index = 0;
  var elapsed = 0;
  var playing = false;
  var finished = false;
  var lastTime = null;

  player.classList.add("is-player");

  function duration(i) {
    return parseInt(scenes[i].dataset.duration, 10) || 7000;
  }

  function paintBars() {
    bars.forEach(function (fill, i) {
      var ratio = i < index ? 1 : i > index ? 0 : Math.min(1, elapsed / duration(i));
      fill.style.transform = "scaleX(" + ratio + ")";
    });
  }

  function show(i) {
    index = Math.max(0, Math.min(scenes.length - 1, i));
    elapsed = 0;
    finished = false;
    scenes.forEach(function (scene, n) {
      var active = n === index;
      scene.classList.remove("is-active");
      scene.setAttribute("aria-hidden", active ? "false" : "true");
      if (active) {
        void scene.offsetWidth; // anzisha upya michoro (animations) ya hatua hii
        scene.classList.add("is-active");
      }
    });
    paintBars();
  }

  function setPlaying(value) {
    playing = value;
    player.classList.toggle("is-paused", !playing);
    playBtn.textContent = playing ? "❚❚" : finished ? "↺" : "▶";
    playBtn.setAttribute("aria-label", playing ? "Simamisha" : finished ? "Anza upya" : "Cheza");
    lastTime = null;
  }

  function next() {
    if (index < scenes.length - 1) {
      show(index + 1);
    } else {
      elapsed = duration(index);
      finished = true;
      paintBars();
      setPlaying(false);
    }
  }

  function tick(now) {
    if (playing) {
      if (lastTime !== null) elapsed += now - lastTime;
      lastTime = now;
      if (elapsed >= duration(index)) next();
      paintBars();
    }
    window.requestAnimationFrame(tick);
  }

  function toggle() {
    if (finished) {
      show(0);
      setPlaying(true);
    } else {
      setPlaying(!playing);
    }
  }

  player.addEventListener("click", function (event) {
    var target = event.target.closest("[data-action], .tap");
    if (!target) return;
    if (target.classList.contains("tap-next") || target.dataset.action === "next") next();
    else if (target.classList.contains("tap-prev") || target.dataset.action === "prev") show(index - 1);
    else if (target.dataset.action === "toggle") toggle();
  });

  player.tabIndex = 0;
  player.addEventListener("keydown", function (event) {
    if (event.key === "ArrowRight") next();
    else if (event.key === "ArrowLeft") show(index - 1);
    else if (event.key === " ") { event.preventDefault(); toggle(); }
  });

  // Ianze yenyewe mtumiaji akiufikia mwongozo kwenye skrini, mara moja tu.
  if (!reduceMotion && "IntersectionObserver" in window) {
    var started = false;
    new IntersectionObserver(function (entries, observer) {
      if (!started && entries[0].isIntersecting) {
        started = true;
        setPlaying(true);
        observer.disconnect();
      }
    }, { threshold: 0.6 }).observe(player);
  }

  show(0);
  setPlaying(false);
  window.requestAnimationFrame(tick);
})();
