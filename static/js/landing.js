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
  // 1. Tukio la mtaa wa usiku
  // ======================================================================
  function Scene(root) {
    this.root = root;
    this.canvas = root.querySelector("canvas");
    this.ctx = this.canvas.getContext("2d");
    this.balanceEl = root.querySelector("[data-owner-balance]");
    this.feed = root.querySelector("[data-owner-feed]");
    this.onlineEl = root.querySelector("[data-scene-online]");
    this.salesEl = root.querySelector("[data-scene-sales]");
    this.balance = 128500;
    this.sales = 2; // mauzo mawili ya mapema yaliyo kwenye simu ya mmiliki
    this.walkers = [];
    this.packets = [];
    this.rings = [];
    this.bubbles = [];
    this.visible = true;
    this.last = 0;
    this.nextWalker = 0;
    this.nextRing = 0;
    this.balanceEl.textContent = money(this.balance);
    if (this.salesEl) this.salesEl.textContent = this.sales;
    this.resize();
    var self = this;
    window.addEventListener("resize", function () { self.resize(); });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (e) { self.visible = e[0].isIntersecting; if (self.visible) self.start(); }).observe(root);
    }
    document.addEventListener("visibilitychange", function () { if (!document.hidden) self.start(); });
    // Mtaa usianze mtupu: watu wachache tayari wapo, na mauzo mawili ya mapema.
    for (var i = 0; i < 5; i++) this.spawn(rand(0.05, 0.95));
    feedItem(this.feed, "💰", _("Siku 1") + " · 0754…221", 1000, 4);
    feedItem(this.feed, "💰", _("Saa 1") + " · 0688…904", 500, 4);
    if (reduceMotion) {
      this.draw(0);
    } else {
      this.start();
    }
  }

  Scene.prototype.resize = function () {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.W = w; this.H = h;
    this.s = Math.max(0.6, Math.min(1.3, w / 560));
    this.ground = h * 0.7;
    this.router = { x: w * 0.3, y: this.ground - 104 * this.s };
    this.cloud = { x: w * 0.8, y: h * 0.17 };
    this.range = w * 0.36;
    this.buildSkyline();
    this.stars = [];
    for (var i = 0; i < 80; i++) this.stars.push({ x: rand(0, w), y: rand(0, h * 0.5), r: rand(0.4, 1.4), p: rand(0, 6.28), sp: rand(0.6, 2) });
  };

  Scene.prototype.buildSkyline = function () {
    var x = -10, list = [];
    while (x < this.W + 20) {
      var bw = rand(38, 86) * this.s, bh = rand(0.16, 0.4) * this.H;
      var windows = [];
      for (var wy = 10; wy < bh - 14; wy += 14 * this.s) {
        for (var wx = 7; wx < bw - 8; wx += 12 * this.s) {
          if (Math.random() < 0.42) windows.push({ x: wx, y: wy, on: Math.random() < 0.7, f: Math.random() < 0.08 });
        }
      }
      list.push({ x: x, w: bw, h: bh, windows: windows, tone: rand(0, 1) });
      x += bw + rand(2, 10);
    }
    this.skyline = list;
  };

  Scene.prototype.start = function () {
    if (this.running || reduceMotion) return;
    this.running = true;
    var self = this;
    this.last = performance.now();
    requestAnimationFrame(function loop(now) {
      if (!self.visible || document.hidden) { self.running = false; return; }
      var dt = Math.max(0, Math.min(50, now - self.last)) / 1000;
      self.last = now;
      self.update(dt, now / 1000);
      self.draw(now / 1000);
      requestAnimationFrame(loop);
    });
  };

  Scene.prototype.spawn = function (at) {
    var fromLeft = Math.random() < 0.5;
    var depth = rand(0, 1);
    this.walkers.push({
      x: at !== undefined ? at * this.W : (fromLeft ? -20 : this.W + 20),
      dir: fromLeft ? 1 : -1,
      depth: depth,
      y: this.ground + 14 + depth * (this.H - this.ground - 34),
      speed: rand(26, 44) * this.s,
      interested: Math.random() < 0.72,
      state: "walk",
      timer: 0,
      phase: rand(0, 6),
      hue: pick(["#7DD8F0", "#c0a8ff", "#ffc98f", "#FFC456", "#ff9fb4"]),
    });
  };

  Scene.prototype.packet = function (from, to, color, size, done) {
    var mid = { x: (from.x + to.x) / 2, y: Math.min(from.y, to.y) - 40 * this.s };
    this.packets.push({ a: from, b: to, c: mid, t: 0, sp: rand(0.9, 1.3), color: color, size: size, done: done });
  };

  Scene.prototype.ownerTarget = function () {
    var box = this.canvas.getBoundingClientRect();
    var r = this.balanceEl.getBoundingClientRect();
    return { x: Math.min(this.W - 8, r.left + r.width / 2 - box.left), y: Math.min(this.H - 8, r.top + r.height / 2 - box.top) };
  };

  Scene.prototype.pay = function (w) {
    var self = this;
    var pkg = pick(PACKAGES);
    var phone = { x: w.x, y: w.y - 30 * this.s };
    // simu -> router -> JamiiLite: ombi la kuingia na malipo
    this.packet(phone, this.router, "#22B8E0", 4, function () {
      self.packet(self.router, self.cloud, "#22B8E0", 4, function () {
        // jibu: amekubaliwa, na pesa inaenda kwa mmiliki
        self.packet(self.cloud, self.router, "#3ccf7e", 4, function () {
          self.packet(self.router, phone, "#3ccf7e", 4, function () { w.state = "online"; w.timer = rand(6, 10); });
        });
        self.packet(self.cloud, self.ownerTarget(), "#f0b54a", 7, function () {
          var before = self.balance;
          self.balance += pkg[1];
          self.sales += 1;
          countUp(self.balanceEl, before, self.balance, 700);
          bump(self.balanceEl);
          if (self.salesEl) self.salesEl.textContent = self.sales;
          feedItem(self.feed, "💰", pkg[0] + " · 07" + Math.floor(rand(10, 99)) + "…" + Math.floor(rand(100, 999)), pkg[1], 4);
        });
      });
    });
  };

  Scene.prototype.update = function (dt, t) {
    var self = this;
    if (t > this.nextWalker && this.walkers.length < 10) { this.spawn(); this.nextWalker = t + rand(0.9, 2.2); }
    if (t > this.nextRing) { this.rings.push({ r: 8, a: 0.55 }); this.nextRing = t + 1.1; }
    this.rings.forEach(function (ring) { ring.r += dt * self.range * 0.55; ring.a = 0.55 * (1 - ring.r / self.range); });
    this.rings = this.rings.filter(function (ring) { return ring.a > 0; });

    this.walkers.forEach(function (w) {
      w.phase += dt * 6;
      var near = Math.abs(w.x - self.router.x) < self.range * 0.8;
      if (w.state === "walk") {
        w.x += w.dir * w.speed * dt;
        if (w.interested && near && Math.random() < dt * 1.4) { w.state = "join"; w.timer = 0.7; }
      } else if (w.state === "join") {
        w.timer -= dt;
        if (w.timer <= 0) { w.state = "paying"; self.pay(w); }
      } else if (w.state === "online") {
        w.x += w.dir * w.speed * 0.25 * dt;
        w.timer -= dt;
        if (Math.random() < dt * 2.2) self.bubbles.push({ x: w.x + rand(-6, 6), y: w.y - 40 * self.s, a: 1, t: pick(["↓", "↓", "▶", "✉"]) });
        if (w.timer <= 0) {
          w.state = "done"; w.interested = false;
          self.bubbles.push({ x: w.x, y: w.y - 46 * self.s, a: 1, t: "⏰" });
          feedItem(self.feed, "⏰", _("Muda umeisha · mteja ametoka"), 0, 4);
        }
      } else {
        w.x += w.dir * w.speed * dt;
      }
    });
    this.walkers = this.walkers.filter(function (w) { return w.x > -40 && w.x < self.W + 40; });
    if (this.onlineEl) this.onlineEl.textContent = this.walkers.filter(function (w) { return w.state === "online"; }).length;

    this.packets.forEach(function (p) { p.t += dt * p.sp; });
    var finished = this.packets.filter(function (p) { return p.t >= 1; });
    this.packets = this.packets.filter(function (p) { return p.t < 1; });
    finished.forEach(function (p) { if (p.done) p.done(); });

    this.bubbles.forEach(function (b) { b.y -= dt * 22; b.a -= dt * 0.7; });
    this.bubbles = this.bubbles.filter(function (b) { return b.a > 0; });
  };

  Scene.prototype.draw = function (t) {
    var c = this.ctx, W = this.W, H = this.H, s = this.s, self = this;
    c.clearRect(0, 0, W, H);

    // nyota na mwezi
    this.stars.forEach(function (st) {
      c.globalAlpha = 0.35 + 0.45 * Math.sin(t * st.sp + st.p) * 0.5 + 0.25;
      c.fillStyle = "#D6E0F0";
      c.beginPath(); c.arc(st.x, st.y, st.r, 0, 6.28); c.fill();
    });
    c.globalAlpha = 1;
    var moon = c.createRadialGradient(W * 0.14, H * 0.13, 0, W * 0.14, H * 0.13, 60 * s);
    moon.addColorStop(0, "rgba(255,240,210,0.9)"); moon.addColorStop(0.25, "rgba(255,240,210,0.25)"); moon.addColorStop(1, "rgba(255,240,210,0)");
    c.fillStyle = moon; c.beginPath(); c.arc(W * 0.14, H * 0.13, 60 * s, 0, 6.28); c.fill();
    c.fillStyle = "#fff6e0"; c.beginPath(); c.arc(W * 0.14, H * 0.13, 13 * s, 0, 6.28); c.fill();

    // majengo ya nyuma na madirisha
    this.skyline.forEach(function (b) {
      var top = self.ground - b.h;
      c.fillStyle = b.tone > 0.5 ? "#0d1a3d" : "#0b1634";
      c.fillRect(b.x, top, b.w, b.h);
      b.windows.forEach(function (wd) {
        var on = wd.on && !(wd.f && Math.sin(t * 7 + wd.x) > 0.6);
        if (!on) return;
        c.fillStyle = "rgba(255, 205, 120, 0.55)";
        c.fillRect(b.x + wd.x, top + wd.y, 5 * s, 7 * s);
      });
    });

    // ardhi na barabara
    var g = c.createLinearGradient(0, this.ground, 0, H);
    g.addColorStop(0, "#111d3f"); g.addColorStop(1, "#0B1A36");
    c.fillStyle = g; c.fillRect(0, this.ground, W, H - this.ground);
    c.strokeStyle = "rgba(255,255,255,0.08)"; c.setLineDash([14 * s, 12 * s]); c.lineWidth = 2;
    c.beginPath(); c.moveTo(0, H - 14); c.lineTo(W, H - 14); c.stroke(); c.setLineDash([]);

    // njia ya internet: router -> JamiiLite
    var r = this.router, cl = this.cloud;
    c.strokeStyle = "rgba(34,184,224,0.25)"; c.lineWidth = 1.5; c.setLineDash([4, 6]);
    c.beginPath(); c.moveTo(r.x, r.y); c.quadraticCurveTo((r.x + cl.x) / 2, Math.min(r.y, cl.y) - 30 * s, cl.x, cl.y); c.stroke();
    c.setLineDash([]);
    for (var k = 0; k < 4; k++) {
      var tt = ((t * 0.35 + k / 4) % 1);
      var px = (1 - tt) * (1 - tt) * r.x + 2 * (1 - tt) * tt * ((r.x + cl.x) / 2) + tt * tt * cl.x;
      var py = (1 - tt) * (1 - tt) * r.y + 2 * (1 - tt) * tt * (Math.min(r.y, cl.y) - 30 * s) + tt * tt * cl.y;
      c.fillStyle = "rgba(125,216,240,0.6)"; c.beginPath(); c.arc(px, py, 1.8, 0, 6.28); c.fill();
    }

    // JamiiLite (wingu)
    var halo = c.createRadialGradient(cl.x, cl.y, 0, cl.x, cl.y, 70 * s);
    halo.addColorStop(0, "rgba(34,184,224,0.55)"); halo.addColorStop(1, "rgba(34,184,224,0)");
    c.fillStyle = halo; c.beginPath(); c.arc(cl.x, cl.y, 70 * s, 0, 6.28); c.fill();
    c.fillStyle = "#123563"; c.strokeStyle = "rgba(125,216,240,0.8)"; c.lineWidth = 1.5;
    roundRect(c, cl.x - 52 * s, cl.y - 18 * s, 104 * s, 36 * s, 12 * s); c.fill(); c.stroke();
    c.fillStyle = "#fff"; c.font = "800 " + Math.round(12 * s) + "px system-ui, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
    c.fillText("JamiiLite", cl.x, cl.y + 1);

    // mawimbi ya WiFi
    this.rings.forEach(function (ring) {
      c.strokeStyle = "rgba(34,184,224," + ring.a.toFixed(3) + ")"; c.lineWidth = 2;
      c.beginPath(); c.arc(r.x, r.y, ring.r, 0, 6.28); c.stroke();
    });

    // kibanda cha mmiliki
    var kx = r.x - 70 * s, ky = this.ground - 96 * s, kw = 140 * s, kh = 96 * s;
    c.fillStyle = "#1a2a55"; c.fillRect(kx, ky + 22 * s, kw, kh - 22 * s);
    for (var i = 0; i < 7; i++) {
      c.fillStyle = i % 2 ? "#f2f2f2" : "#d6453a";
      c.beginPath(); c.moveTo(kx - 8 * s + i * (kw + 16 * s) / 7, ky + 8 * s); c.lineTo(kx - 8 * s + (i + 1) * (kw + 16 * s) / 7, ky + 8 * s);
      c.lineTo(kx - 8 * s + (i + 1) * (kw + 16 * s) / 7, ky + 26 * s); c.lineTo(kx - 8 * s + i * (kw + 16 * s) / 7, ky + 26 * s); c.fill();
    }
    var shopLight = c.createLinearGradient(0, ky + 30 * s, 0, ky + kh);
    shopLight.addColorStop(0, "rgba(255,214,140,0.9)"); shopLight.addColorStop(1, "rgba(255,170,90,0.5)");
    c.fillStyle = shopLight; c.fillRect(kx + 12 * s, ky + 36 * s, kw - 24 * s, kh - 48 * s);
    c.fillStyle = "rgba(255,200,120,0.12)"; c.beginPath(); c.ellipse(r.x, this.ground + 8 * s, 110 * s, 16 * s, 0, 0, 6.28); c.fill();
    c.fillStyle = "#0B1F40"; c.font = "800 " + Math.round(10 * s) + "px system-ui, sans-serif";
    c.fillText("NEEMA WiFi", r.x, ky + 50 * s);

    // router juu ya kibanda
    c.fillStyle = "#e9eef8"; roundRect(c, r.x - 18 * s, r.y - 6 * s, 36 * s, 12 * s, 4 * s); c.fill();
    c.strokeStyle = "#e9eef8"; c.lineWidth = 2;
    c.beginPath(); c.moveTo(r.x - 12 * s, r.y - 6 * s); c.lineTo(r.x - 16 * s, r.y - 22 * s); c.moveTo(r.x + 12 * s, r.y - 6 * s); c.lineTo(r.x + 16 * s, r.y - 22 * s); c.stroke();
    var blink = Math.sin(t * 9) > 0 ? "#3ccf7e" : "#1d6b45";
    c.fillStyle = blink; c.beginPath(); c.arc(r.x + 10 * s, r.y, 2.4 * s, 0, 6.28); c.fill();

    // watu, kuanzia walio mbali
    this.walkers.slice().sort(function (a, b) { return a.depth - b.depth; }).forEach(function (w) { self.drawWalker(w); });

    // packets
    this.packets.forEach(function (p) {
      var u = p.t, x = (1 - u) * (1 - u) * p.a.x + 2 * (1 - u) * u * p.c.x + u * u * p.b.x;
      var y = (1 - u) * (1 - u) * p.a.y + 2 * (1 - u) * u * p.c.y + u * u * p.b.y;
      var glow = c.createRadialGradient(x, y, 0, x, y, p.size * 3.2);
      glow.addColorStop(0, p.color); glow.addColorStop(1, "rgba(0,0,0,0)");
      c.fillStyle = glow; c.beginPath(); c.arc(x, y, p.size * 3.2, 0, 6.28); c.fill();
      c.fillStyle = p.color; c.beginPath(); c.arc(x, y, p.size, 0, 6.28); c.fill();
      if (p.size > 5) { c.fillStyle = "#3b2600"; c.font = "900 " + Math.round(7 * s) + "px system-ui"; c.fillText("Tsh", x, y + 0.5); }
    });

    // vipovu vya data
    c.font = "700 " + Math.round(11 * s) + "px system-ui, sans-serif";
    this.bubbles.forEach(function (b) { c.globalAlpha = Math.max(0, b.a); c.fillStyle = "#FFC456"; c.fillText(b.t, b.x, b.y); });
    c.globalAlpha = 1;
  };

  Scene.prototype.drawWalker = function (w) {
    var c = this.ctx, s = this.s * (1 + w.depth * 0.45);
    var step = (w.state === "walk" || w.state === "done") ? Math.sin(w.phase) : 0;
    var x = w.x, y = w.y;
    c.fillStyle = "rgba(0,0,0,0.35)"; c.beginPath(); c.ellipse(x, y + 2, 10 * s, 3 * s, 0, 0, 6.28); c.fill();
    c.strokeStyle = "#1c2b55"; c.lineWidth = 4 * s; c.lineCap = "round";
    c.beginPath(); c.moveTo(x, y - 14 * s); c.lineTo(x - 5 * s * step, y); c.moveTo(x, y - 14 * s); c.lineTo(x + 5 * s * step, y); c.stroke();
    c.fillStyle = "#24386e"; roundRect(c, x - 7 * s, y - 34 * s, 14 * s, 22 * s, 6 * s); c.fill();
    c.fillStyle = "#2c427d"; c.beginPath(); c.arc(x, y - 40 * s, 6 * s, 0, 6.28); c.fill();
    var connected = w.state === "online";
    var px = x + w.dir * 8 * s, py = y - 30 * s;
    var col = connected ? "#3ccf7e" : (w.state === "join" || w.state === "paying") ? "#f0b54a" : w.hue;
    var glow = c.createRadialGradient(px, py, 0, px, py, 16 * s);
    glow.addColorStop(0, col); glow.addColorStop(1, "rgba(0,0,0,0)");
    c.globalAlpha = 0.55; c.fillStyle = glow; c.beginPath(); c.arc(px, py, 16 * s, 0, 6.28); c.fill(); c.globalAlpha = 1;
    c.fillStyle = col; roundRect(c, px - 3 * s, py - 5 * s, 6 * s, 10 * s, 1.5 * s); c.fill();
    if (connected) {
      c.fillStyle = "#3ccf7e"; c.font = "900 " + Math.round(10 * s) + "px system-ui"; c.fillText("✓", x, y - 54 * s);
    }
  };

  function roundRect(c, x, y, w, h, r) {
    c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
  }

  document.querySelectorAll("[data-scene]").forEach(function (el) { new Scene(el); });

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
    feedItem(this.ownerFeed, "📶", _("Mteja ameingia · Neema WiFi"), 0, 5);
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
      this.$("[data-sim-stk-text]").textContent = fmt(_("Lipa Tsh %(amount)s kwa NEEMA WIFI? Weka PIN yako ya M-Pesa."), { amount: money(this.price) });
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
      feedItem(self.ownerFeed, "📶", _("Mteja ameingia · Neema WiFi"), 0, 5);
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

  document.querySelectorAll("[data-sim]").forEach(function (el) { new Sim(el); });

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

  document.querySelectorAll("[data-journey]").forEach(function (el) { new Journey(el); });

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

  // Matukio ya Neema WiFi (mfano wa duka) yanatokea pembeni mtu akishashuka chini ya hero.
  var toast = document.querySelector("[data-toast]");
  if (toast && !reduceMotion) {
    var EVENTS = [
      ["💰", "Neema WiFi · +Tsh 500", _("Saa 1") + " · " + _("sasa hivi")],
      ["📶", _("Mteja ameingia · Neema WiFi"), _("sasa hivi")],
      ["💰", "Neema WiFi · +Tsh 1,000", _("Siku 1") + " · " + _("sasa hivi")],
      ["⏰", _("Muda umeisha · mteja ametoka"), _("Router imemkata yenyewe")],
      ["💰", "Neema WiFi · +Tsh 5,000", _("Wiki") + " · " + _("sasa hivi")],
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
