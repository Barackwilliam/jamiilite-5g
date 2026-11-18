// JamiiLite 5G: ukurasa wa mwanzo.
//
// 1. Tukio la mtaa wa usiku (canvas): watu wanapita na simu, wanaingia kwenye
//    WiFi ya kibanda, wanalipa, na pesa inaruka kwenda simu ya mmiliki.
// 2. Simulator ya mteja: mgeni anagusa simu na kupitia hatua halisi za mteja.
// 3. Safari ya packet: gusa kifaa uone packet ikisafiri na kilichomo ndani.
// 4. Tabs, ulinganisho na kikokotoo cha mapato.
// Sehemu nzito zinaanza tu zinapoonekana, ili ukurasa ufunguke haraka.
(function () {
  "use strict";

  var I18N = {};
  try { I18N = JSON.parse(document.getElementById("landing-i18n").textContent) || {}; } catch (e) { /* Kiswahili */ }
  var _ = function (s) { return typeof I18N[s] === "string" ? I18N[s] : s; };
  var ngettext = function (one, many, n) {
    var pair = I18N[one];
    if (Array.isArray(pair)) return n === 1 ? pair[0] : pair[1];
    return n === 1 ? one : many;
  };
  var fmt = function (s, v) { return s.replace(/%\((\w+)\)s/g, function (m, k) { return v[k]; }); };
  var money = function (n) { return Math.round(n).toLocaleString("en-US"); };
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var rand = function (a, b) { return a + Math.random() * (b - a); };
  var pick = function (list) { return list[Math.floor(Math.random() * list.length)]; };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  // Sehemu zilizo chini ya skrini zinaanza kivinjari kikiwa huru, si wakati ukurasa unafunguka.
  var whenIdle = function (fn) {
    if ("requestIdleCallback" in window) window.requestIdleCallback(fn, { timeout: 2500 });
    else setTimeout(fn, 400);
  };

  var PACKAGES = [[_("Saa 1"), 500], [_("Siku 1"), 1000], [_("Saa 1"), 500], [_("Wiki"), 5000]];

  // Hesabu inayopanda taratibu (mfano salio).
  function countUp(el, from, to, ms) {
    if (!el) return;
    if (reduceMotion) { el.textContent = money(to); return; }
    var start = performance.now();
    (function step(now) {
      var p = Math.min(1, (now - start) / ms);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = money(from + (to - from) * eased);
      if (p < 1) requestAnimationFrame(step);
    })(start);
  }

  function bump(el) {
    if (!el) return;
    el.classList.remove("is-bump");
    void el.offsetWidth;
    el.classList.add("is-bump");
  }

  function feedItem(list, icon, text, amount, max) {
    if (!list) return;
    var li = document.createElement("li");
    var i = document.createElement("i");
    i.textContent = icon;
    var span = document.createElement("span");
    span.textContent = text;
    li.appendChild(i);
    li.appendChild(span);
    if (amount) {
      var b = document.createElement("b");
      b.textContent = "+Tsh " + money(amount);
      li.appendChild(b);
    }
    list.insertBefore(li, list.firstChild);
    while (list.children.length > (max || 4)) list.removeChild(list.lastChild);
  }

  // ======================================================================
  // 2. Simulator ya mteja
  // ======================================================================
  function Sim(root) {
    this.root = root;
    this.phone = root.querySelector("[data-sim-phone]");
    this.finger = root.querySelector("[data-sim-finger]");
    this.ownerBalance = root.querySelector("[data-sim-owner-balance]");
    this.ownerFeed = root.querySelector("[data-sim-owner-feed]");
    this.ownerOnline = root.querySelector("[data-sim-owner-online]");
    this.ownerToday = root.querySelector("[data-sim-owner-today]");
    this.balance = 146000;
    this.online = 6;
    this.today = 21;
    this.auto = !reduceMotion;
    this.order = ["wifi", "portal", "stk", "online", "expired"];
    var self = this;

    root.addEventListener("click", function (e) {
      var el = e.target.closest("[data-sim-action], [data-sim-pkg], [data-sim-key]");
      if (!el) return;
      if (el.dataset.simAction) self.action(el.dataset.simAction, el);
      else if (el.dataset.simPkg) self.pickPackage(el);
      else if (el.dataset.simKey) self.key(el);
    });
    // Mtu akigusa mwenyewe, tunasimamisha onyesho la kiotomatiki.
    this.phone.addEventListener("pointerdown", function (e) { if (e.isTrusted) self.takeOver(); });

    this.reset();
    feedItem(this.ownerFeed, "💰", _("Siku 1") + " · 0754…221", 1000, 5);
    feedItem(this.ownerFeed, "📶", _("Mteja ameingia · JamiiTek WiFi"), 0, 5);
    this.fits = root.querySelectorAll(".sim-fit");
    this.scale = 1;
    this.fit();
    window.addEventListener("resize", function () { self.fit(); });
    // Onyesho la kiotomatiki linaanza simu ikionekana, na linasubiri ikifichwa.
    if ("IntersectionObserver" in window && this.auto) {
      new IntersectionObserver(function (entries) {
        self.inView = entries[0].isIntersecting;
        if (self.inView) { self.fit(); self.startTour(); }
      }, { threshold: 0.35 }).observe(root);
    }
  }

  // Simu zinapunguzwa ukubwa zitoshee skrini, bila kubadilisha mpangilio wa ndani.
  Sim.prototype.fit = function () {
    var stage = this.root.querySelector("[data-sim-stage]");
    if (!stage || !stage.clientWidth) return;
    var narrow = window.innerWidth < 760;
    var gap = narrow ? 0 : 64;
    var phones = narrow ? 1 : this.fits.length;
    var room = (stage.clientWidth - gap) / phones;
    var tall = Math.max(320, window.innerHeight - 150);
    var self = this;
    this.fits.forEach(function (box) {
      var phone = box.firstElementChild;
      var w = phone.offsetWidth, h = phone.offsetHeight;
      var k = Math.min(1, room / w, tall / h);
      box.style.setProperty("--sim-scale", k.toFixed(3));
      box.style.width = Math.floor(w * k) + "px";
      box.style.height = Math.floor(h * k) + "px";
      if (phone === self.phone) self.scale = k;
    });
  };

  Sim.prototype.startTour = function () {
    if (this.touring || !this.auto) return;
    var self = this;
    this.touring = true;
    setTimeout(function () { self.tour().then(function () { self.touring = false; }); }, 700);
  };

  Sim.prototype.$ = function (sel) { return this.root.querySelector(sel); };

  Sim.prototype.show = function (name) {
    this.state = name;
    this.root.querySelectorAll("[data-screen]").forEach(function (s) { s.classList.toggle("is-active", s.dataset.screen === name); });
    var index = { wifi: 0, portal: 1, stk: 2, paid: 3, online: 3, expired: 4 }[name];
    this.root.querySelectorAll("[data-step]").forEach(function (li, i) {
      li.classList.toggle("is-done", i < index);
      li.classList.toggle("is-current", i === index);
    });
    this.$("[data-sim-wifi]").classList.toggle("is-on", name !== "wifi");
  };

  // Kila "Anza upya" inaongeza run: kazi zilizopangwa kabla (setTimeout) zinaona hazihusiki tena.
  Sim.prototype.later = function (fn, ms) {
    var self = this, run = this.run;
    setTimeout(function () { if (self.run === run) fn(); }, ms);
  };

  Sim.prototype.reset = function () {
    this.run = (this.run || 0) + 1;
    clearInterval(this.clock);
    this.$("[data-sim-joining]").hidden = true;
    this.$("[data-sim-toast]").hidden = true;
    this.pkgEl = this.$("[data-sim-pkg]");
    this.root.querySelectorAll("[data-sim-pkg]").forEach(function (p, i) { p.classList.toggle("is-picked", i === 0); });
    this.show("wifi");
  };

  Sim.prototype.takeOver = function () {
    if (!this.auto) return;
    this.auto = false;
    this.root.classList.add("is-manual");
    this.finger.classList.remove("is-on");
  };

  Sim.prototype.pickPackage = function (el) {
    this.root.querySelectorAll("[data-sim-pkg]").forEach(function (p) { p.classList.toggle("is-picked", p === el); });
    this.pkgEl = el;
  };

  Sim.prototype.action = function (name, el) {
    var self = this;
    if (name === "locked") {
      el.classList.remove("is-shake"); void el.offsetWidth; el.classList.add("is-shake");
      var toast = this.$("[data-sim-toast]"); toast.hidden = false;
      clearTimeout(this.toastTimer); this.toastTimer = setTimeout(function () { toast.hidden = true; }, 1600);
    } else if (name === "join" && this.state === "wifi") {
      this.$("[data-sim-joining]").hidden = false;
      this.later(function () { self.$("[data-sim-joining]").hidden = true; self.show("portal"); }, 1100);
    } else if (name === "pay" && this.state === "portal") {
      this.price = parseInt(this.pkgEl.dataset.simPkg, 10);
      this.minutes = parseInt(this.pkgEl.dataset.simMins, 10);
      this.pkgName = this.pkgEl.dataset.simName;
      this.$("[data-sim-stk-text]").textContent = fmt(_("Lipa Tsh %(amount)s kwa JAMIITEK WIFI? Weka PIN yako."), { amount: money(this.price) });
      this.pin = 0;
      this.root.querySelectorAll("[data-sim-pin] i").forEach(function (d) { d.classList.remove("is-on"); });
      this.show("stk");
    } else if (name === "skip" && this.state === "online") {
      this.speed = 40;
    } else if (name === "again" && this.state === "expired") {
      this.show("portal");
    } else if (name === "restart") {
      this.reset();
      if (!this.auto && !reduceMotion) { this.auto = true; this.root.classList.remove("is-manual"); this.startTour(); }
    }
  };

  Sim.prototype.key = function (el) {
    if (this.state !== "stk" || this.pin >= 4) return;
    el.classList.add("is-press"); setTimeout(function () { el.classList.remove("is-press"); }, 150);
    this.root.querySelectorAll("[data-sim-pin] i")[this.pin].classList.add("is-on");
    this.pin += 1;
    if (this.pin === 4) {
      var self = this;
      this.later(function () { self.paid(); }, 500);
    }
  };

  Sim.prototype.paid = function () {
    var self = this;
    this.show("paid");
    var before = this.balance;
    this.balance += this.price;
    this.today += 1;
    countUp(this.ownerBalance, before, this.balance, 800);
    bump(this.ownerBalance);
    this.ownerToday.textContent = this.today;
    feedItem(this.ownerFeed, "💰", this.pkgName + " · 0712…678", this.price, 5);
    this.later(function () {
      self.online += 1;
      self.ownerOnline.textContent = self.online;
      feedItem(self.ownerFeed, "📶", _("Mteja ameingia · JamiiTek WiFi"), 0, 5);
      self.goOnline();
    }, 1800);
  };

  Sim.prototype.goOnline = function () {
    var self = this;
    this.show("online");
    this.speed = 1;
    // Muda wote wa kifurushi unaonyeshwa ndani ya sekunde ~40.
    var total = this.minutes * 60, left = total, perTick = total / 160;
    var down = 0, up = 0;
    var ring = this.$("[data-sim-ring]"), label = this.$("[data-sim-left]");
    var downEl = this.$("[data-sim-down]"), upEl = this.$("[data-sim-up]");
    clearInterval(this.clock);
    this.clock = setInterval(function () {
      left -= perTick * self.speed;
      down += rand(0.4, 2.6) * self.speed; up += rand(0.05, 0.3) * self.speed;
      if (left <= 0) {
        left = 0;
        clearInterval(self.clock);
        self.online -= 1;
        self.ownerOnline.textContent = self.online;
        feedItem(self.ownerFeed, "⏰", _("Muda umeisha · mteja ametoka"), 0, 5);
        self.show("expired");
      }
      var h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), sec = Math.floor(left % 60);
      label.textContent = (h ? h + ":" : "") + String(m).padStart(2, "0") + ":" + String(sec).padStart(2, "0");
      ring.style.strokeDashoffset = (326.7 * (1 - left / total)).toFixed(1);
      ring.style.stroke = left / total < 0.2 ? "#f0786a" : "";
      downEl.textContent = down.toFixed(1); upEl.textContent = up.toFixed(1);
    }, 250);
  };

  // Onyesho la kiotomatiki: "kidole" kinagusa hatua zote mpaka mtu achukue usukani.
  Sim.prototype.tap = async function (selector, pause) {
    if (!this.auto) throw new Error("manual");
    var el = typeof selector === "string" ? this.$(selector) : selector;
    var box = this.phone.getBoundingClientRect(), r = el.getBoundingClientRect(), k = this.scale || 1;
    this.finger.classList.add("is-on");
    this.finger.style.left = (r.left - box.left + r.width / 2) / k + "px";
    this.finger.style.top = (r.top - box.top + r.height / 2) / k + "px";
    await sleep(750);
    if (!this.auto) throw new Error("manual");
    this.finger.classList.remove("is-tap"); void this.finger.offsetWidth; this.finger.classList.add("is-tap");
    el.click();
    await sleep(pause || 600);
  };

  Sim.prototype.waitFor = async function (state) {
    while (this.state !== state) {
      if (!this.auto) throw new Error("manual");
      await sleep(200);
    }
  };

  Sim.prototype.whileHidden = async function () {
    while (this.inView === false || document.hidden) await sleep(400);
  };

  Sim.prototype.tour = async function () {
    var self = this;
    try {
      while (this.auto) {
        await this.whileHidden();
        this.reset();
        await sleep(900);
        await this.tap('[data-sim-action="locked"]', 900);
        await this.tap('[data-sim-action="join"]', 1600);
        await this.waitFor("portal");
        await this.tap(this.root.querySelectorAll("[data-sim-pkg]")[1], 500);
        await this.tap(this.root.querySelectorAll("[data-sim-pkg]")[0], 500);
        await this.tap('[data-sim-action="pay"]', 700);
        var keys = ["4", "7", "2", "9"];
        for (var i = 0; i < keys.length; i++) await this.tap('[data-sim-key="' + keys[i] + '"]', 150);
        await this.waitFor("online");
        this.finger.classList.remove("is-on");
        await sleep(6500);
        await this.tap('[data-sim-action="skip"]', 400);
        this.finger.classList.remove("is-on");
        await this.waitFor("expired");
        await sleep(3500);
      }
    } catch (err) {
      self.finger.classList.remove("is-on");
    }
  };

  whenIdle(function () { document.querySelectorAll("[data-sim]").forEach(function (el) { new Sim(el); }); });

  // ======================================================================
  // 3. Bila / Na JamiiLite
  // ======================================================================
  document.querySelectorAll("[data-compare]").forEach(function (root) {
    var tabs = root.querySelectorAll("[data-compare-tab]");
    var touched = false;
    function set(which) {
      root.classList.toggle("is-after", which === "after");
      tabs.forEach(function (t) { t.setAttribute("aria-pressed", String(t.dataset.compareTab === which)); });
      root.querySelectorAll("[data-compare-panel]").forEach(function (p) { p.hidden = p.dataset.comparePanel !== which; });
    }
    tabs.forEach(function (t) { t.addEventListener("click", function () { touched = true; set(t.dataset.compareTab); }); });
    if (!reduceMotion && "IntersectionObserver" in window) {
      new IntersectionObserver(function (entries, obs) {
        if (!entries[0].isIntersecting) return;
        obs.disconnect();
        setTimeout(function () { if (!touched) set("after"); }, 2200);
      }, { threshold: 0.6 }).observe(root);
    }
  });

  // ======================================================================
  // 4. Kikokotoo cha mapato
  // ======================================================================
  document.querySelectorAll("[data-calc]").forEach(function (root) {
    var fee = parseInt(root.dataset.fee, 10) || 10000;
    var inputs = {};
    root.querySelectorAll("[data-calc-in]").forEach(function (i) { inputs[i.dataset.calcIn] = i; });
    var out = function (k) { return root.querySelector('[data-calc-out="' + k + '"]'); };
    var res = function (k) { return root.querySelector('[data-calc-result="' + k + '"]'); };
    var shown = { gross: 0, net: 0 };
    var maxGross = 200 * 3000 * 31;
    function update() {
      var customers = +inputs.customers.value, price = +inputs.price.value, days = +inputs.days.value;
      Object.keys(inputs).forEach(function (k) {
        var i = inputs[k];
        i.style.setProperty("--fill", ((i.value - i.min) / (i.max - i.min) * 100) + "%");
      });
      out("customers").textContent = customers;
      out("price").textContent = money(price);
      out("days").textContent = days;
      var gross = customers * price * days, net = Math.max(0, gross - fee);
      countUp(res("gross"), shown.gross, gross, 450);
      countUp(res("net"), shown.net, net, 450);
      shown.gross = gross; shown.net = net;
      var payback = Math.max(1, Math.ceil(fee / (customers * price)));
      res("payback").textContent = fmt(ngettext("siku %(n)s", "siku %(n)s", payback), { n: payback });
      root.querySelector("[data-calc-bar]").style.width = Math.max(4, Math.sqrt(gross / maxGross) * 100) + "%";
    }
    Object.keys(inputs).forEach(function (k) { inputs[k].addEventListener("input", update); });
    update();
  });

  // ======================================================================
  // 5. Safari ya packet
  // ======================================================================
  function Journey(root) {
    this.root = root;
    this.map = root.querySelector("[data-jr-map]");
    this.packet = root.querySelector("[data-jr-packet]");
    this.tag = root.querySelector("[data-jr-tag]");
    this.bar = root.querySelector("[data-jr-bar]");
    this.count = root.querySelector("[data-jr-count]");
    this.playBtn = root.querySelector('[data-jr="play"]');
    this.steps = Array.prototype.slice.call(root.querySelectorAll("[data-jr-steps] > li"));
    this.nodes = {};
    var self = this;
    root.querySelectorAll("[data-node]").forEach(function (n) { self.nodes[n.dataset.node] = n; });
    this.index = 0;
    this.playing = !reduceMotion;
    this.inView = false;

    root.addEventListener("click", function (e) {
      var node = e.target.closest("[data-node]");
      var btn = e.target.closest("[data-jr]");
      if (node) {
        self.pause();
        self.go(self.nextTo(node.dataset.node));
      } else if (btn) {
        var what = btn.dataset.jr;
        if (what === "play") { self.playing ? self.pause() : self.play(); return; }
        self.pause();
        self.go((self.index + (what === "next" ? 1 : -1) + self.steps.length) % self.steps.length);
      }
    });
    window.addEventListener("resize", function () { self.place(false); });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        self.inView = entries[0].isIntersecting;
        if (self.inView) { self.place(false); self.schedule(); }
      }, { threshold: 0.3 }).observe(root);
    }
    this.go(0);
    this.renderPlay();
  }

  // Hatua ya kwanza (kuanzia inayofuata) ambayo packet yake inafika kwenye kifaa hiki.
  Journey.prototype.nextTo = function (name) {
    for (var k = 1; k <= this.steps.length; k++) {
      var i = (this.index + k) % this.steps.length;
      if (this.steps[i].dataset.to === name) return i;
    }
    for (var j = 0; j < this.steps.length; j++) if (this.steps[j].dataset.from === name) return j;
    return this.index;
  };

  // Katikati ya ikoni ya kifaa, ukilinganisha na ramani.
  Journey.prototype.center = function (name) {
    var box = this.map.getBoundingClientRect();
    var r = this.nodes[name].querySelector(".jr-ico").getBoundingClientRect();
    return { x: r.left - box.left + r.width / 2, y: r.top - box.top + r.height / 2 };
  };

  Journey.prototype.place = function (animate) {
    var step = this.steps[this.index];
    if (!step || !this.map.offsetWidth) return;
    var a = this.center(step.dataset.from), b = this.center(step.dataset.to);
    var p = this.packet;
    clearTimeout(this.arrive);
    if (animate && !reduceMotion) {
      p.classList.remove("is-moving", "is-arrived");
      p.style.transform = "translate(" + a.x + "px," + a.y + "px)";
      void p.offsetWidth;
      p.classList.add("is-moving");
      // Ikifika, nukta inafifia ili ikoni ya kifaa ionekane; lebo inabaki.
      this.arrive = setTimeout(function () { p.classList.add("is-arrived"); }, 1200);
    } else {
      p.classList.add("is-arrived");
    }
    p.style.transform = "translate(" + b.x + "px," + b.y + "px)";
  };

  Journey.prototype.go = function (i) {
    var self = this;
    this.index = i;
    var step = this.steps[i];
    this.steps.forEach(function (li, k) { li.classList.toggle("is-active", k === i); });
    Object.keys(this.nodes).forEach(function (name) {
      self.nodes[name].classList.toggle("is-from", name === step.dataset.from);
      self.nodes[name].classList.toggle("is-to", name === step.dataset.to);
    });
    this.root.style.setProperty("--jr-color", step.dataset.color);
    this.tag.textContent = step.dataset.tag;
    this.bar.style.width = ((i + 1) / this.steps.length * 100) + "%";
    this.count.textContent = (i + 1) + " / " + this.steps.length;
    this.place(true);
    this.schedule();
  };

  Journey.prototype.schedule = function () {
    var self = this;
    clearTimeout(this.timer);
    if (!this.playing) return;
    this.timer = setTimeout(function () {
      if (self.inView && !document.hidden) self.go((self.index + 1) % self.steps.length);
      else self.schedule();
    }, 3200);
  };

  Journey.prototype.renderPlay = function () {
    this.playBtn.textContent = this.playing ? "❚❚" : "▶";
    this.playBtn.setAttribute("aria-label", this.playing ? _("Simamisha") : _("Cheza"));
    this.root.classList.toggle("is-playing", this.playing);
  };
  Journey.prototype.play = function () { this.playing = true; this.renderPlay(); this.go((this.index + 1) % this.steps.length); };
  Journey.prototype.pause = function () { this.playing = false; clearTimeout(this.timer); this.renderPlay(); };

  whenIdle(function () { document.querySelectorAll("[data-journey]").forEach(function (el) { new Journey(el); }); });

  // ======================================================================
  // 6. Tabs: sehemu zinafunguka unapogusa
  // ======================================================================
  document.querySelectorAll("[data-tabs]").forEach(function (root) {
    var tabs = Array.prototype.slice.call(root.querySelectorAll("[data-tab]"));
    function select(name, focus) {
      tabs.forEach(function (t) {
        var on = t.dataset.tab === name;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        if (on && focus) t.focus();
        if (on && t.scrollIntoView && t.parentNode.scrollWidth > t.parentNode.clientWidth) {
          t.parentNode.scrollTo({ left: t.offsetLeft - 16, behavior: reduceMotion ? "auto" : "smooth" });
        }
      });
      root.querySelectorAll("[data-panel]").forEach(function (p) { p.hidden = p.dataset.panel !== name; });
      // Sehemu iliyofunguka inapima upya ukubwa wake (simu, njia za packet).
      window.dispatchEvent(new Event("resize"));
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { select(t.dataset.tab); });
      t.addEventListener("keydown", function (e) {
        var to = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
        if (to === undefined) return;
        e.preventDefault();
        select(tabs[(to + tabs.length) % tabs.length].dataset.tab, true);
      });
    });
    document.querySelectorAll("[data-open-tab]").forEach(function (link) {
      link.addEventListener("click", function () { select(link.dataset.openTab); });
    });
  });

  // ======================================================================
  // 7. Ukurasa unaozungumza: neno la kichwa, sehemu zinazojitokeza, matukio
  // ======================================================================
  document.querySelectorAll("[data-rotate]").forEach(function (box) {
    var words = Array.prototype.slice.call(box.children);
    if (words.length < 2 || reduceMotion) return;
    var i = 0;
    setInterval(function () {
      if (document.hidden) return;
      var out = words[i];
      i = (i + 1) % words.length;
      out.classList.remove("is-on"); out.classList.add("is-out");
      words[i].classList.remove("is-out"); words[i].classList.add("is-on");
      setTimeout(function () { out.classList.remove("is-out"); }, 600);
    }, 2600);
  });

  var reveal = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-in"); ro.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    reveal.forEach(function (el) { ro.observe(el); });
  } else {
    reveal.forEach(function (el) { el.classList.add("is-in"); });
  }

  // Matukio ya JamiiTek WiFi (mfano wa duka) yanatokea pembeni mtu akishashuka chini ya hero.
  var toast = document.querySelector("[data-toast]");
  if (toast && !reduceMotion) {
    var EVENTS = [
      ["💰", "JamiiTek WiFi · +Tsh 500", _("Saa 1") + " · " + _("sasa hivi")],
      ["📶", _("Mteja ameingia · JamiiTek WiFi"), _("sasa hivi")],
      ["💰", "JamiiTek WiFi · +Tsh 1,000", _("Siku 1") + " · " + _("sasa hivi")],
      ["⏰", _("Muda umeisha · mteja ametoka"), _("Router imemkata yenyewe")],
      ["💰", "JamiiTek WiFi · +Tsh 5,000", _("Wiki") + " · " + _("sasa hivi")],
    ];
    var hero = document.querySelector(".lp-hero");
    var n = 0, timer = null, stopped = false;
    var icon = toast.querySelector("i"), title = toast.querySelector("b"), sub = toast.querySelector("small");
    var show = function () {
      if (stopped || document.hidden) return;
      var e = EVENTS[n++ % EVENTS.length];
      icon.textContent = e[0]; title.textContent = e[1]; sub.textContent = e[2];
      toast.classList.add("is-on");
      setTimeout(function () { toast.classList.remove("is-on"); }, 4200);
    };
    toast.querySelector("[data-toast-close]").addEventListener("click", function () {
      stopped = true; clearInterval(timer); toast.classList.remove("is-on");
    });
    if (hero && "IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        var past = !entries[0].isIntersecting;
        clearInterval(timer); timer = null;
        if (past && !stopped) { setTimeout(show, 1200); timer = setInterval(show, 9000); }
        else toast.classList.remove("is-on");
      }).observe(hero);
    }
  }
})();
