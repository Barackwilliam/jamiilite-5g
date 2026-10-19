// JamiiLite 5G: ramani ya mtandao "Live".
//
// Inachora simu za wateja, routers, JamiiLite (RADIUS) na mtoa huduma wa
// malipo, kisha inasafirisha "packets" kwenye njia zao kila tukio halisi
// linapotokea (vocha kuingia, matumizi, malipo, ripoti za routers).
// Hali ya "mfano" inatengeneza matukio ya kuigiza na inaandikwa wazi hivyo.
(function () {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var POLL_MS = 3000;
  var SPEED = 0.55; // px kwa ms, ndani ya viewBox
  var MAX_LOG = 50;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Kila aina ya tukio: njia ya packet, rangi (darasa la CSS), na jibu linalorudi.
  var KINDS = {
    auth_accept: { hops: ["phone", "router", "cloud"], cls: "pk-request", reply: "pk-accept", tag: "good" },
    auth_reject: { hops: ["phone", "router", "cloud"], cls: "pk-request", reply: "pk-reject", replyShape: "ring", tag: "bad" },
    acct_start: { hops: ["router", "cloud"], cls: "pk-acct", small: true, tag: "info" },
    acct_update: { hops: ["router", "cloud"], cls: "pk-acct", small: true, tag: "info" },
    acct_stop: { hops: ["router", "cloud"], cls: "pk-acct", small: true, tag: "muted" },
    payment_started: { hops: ["phone", "router", "cloud", "gateway"], cls: "pk-pay", shape: "diamond", tag: "warn" },
    payment_paid: { hops: ["gateway", "cloud", "router"], cls: "pk-pay", shape: "diamond", coin: true, tag: "good" },
    payment_failed: { hops: ["gateway", "cloud"], cls: "pk-reject", shape: "ring", tag: "bad" },
    command: { hops: ["cloud", "router"], cls: "pk-request", tag: "info" },
    checkin: { hops: ["router", "cloud"], cls: "pk-checkin", tiny: true, reply: "pk-checkin" },
  };

  var DEMO_ROUTERS = ["Duka la Kati", "Kibanda cha Stendi", "Saluni ya Mama Asha"];
  var DEMO_PACKAGES = [["Saa 1", 500], ["Siku 1", 1000], ["Wiki", 5000]];

  function el(name, attrs, parent) {
    var node = document.createElementNS(NS, name);
    for (var key in attrs) node.setAttribute(key, attrs[key]);
    if (parent) parent.appendChild(node);
    return node;
  }

  function text(parent, x, y, value, cls, anchor) {
    var t = el("text", { x: x, y: y, class: cls || "", "text-anchor": anchor || "middle" }, parent);
    t.textContent = value;
    return t;
  }

  function clip(value, max) {
    return value.length > max ? value.slice(0, max - 1) + "…" : value;
  }

  function tsh(n) {
    return "Tsh " + Math.round(n).toLocaleString("en-US");
  }

  function clock(ms) {
    var d = new Date(ms);
    return [d.getHours(), d.getMinutes(), d.getSeconds()].map(function (v) { return String(v).padStart(2, "0"); }).join(":");
  }

  function Live(root) {
    this.root = root;
    this.svg = root.querySelector("[data-live-map]");
    this.log = root.querySelector("[data-live-log]");
    this.endpoint = root.dataset.endpoint || "";
    this.demo = root.dataset.demo === "1" || !this.endpoint;
    this.demoOnly = !this.endpoint;
    this.routers = [];
    this.gateway = "Malipo";
    this.stats = { today_amount: 0, accepts: 0, rejects: 0, clients: 0 };
    this.recent = []; // muda wa matukio ya dakika iliyopita, kwa "packets/dakika"
    this.packets = [];
    this.seen = {};
    this.cursor = null;
    this.failures = 0;
    this.layoutKey = "";
    this.running = false;
    this.tick = this.tick.bind(this);

    var self = this;
    var toggle = root.querySelector("[data-demo-toggle]");
    if (toggle) {
      toggle.addEventListener("click", function () { self.setDemo(!self.demo); });
      if (this.demoOnly) toggle.hidden = true;
    }
    window.addEventListener("resize", function () {
      clearTimeout(self.resizeTimer);
      self.resizeTimer = setTimeout(function () { self.layout(true); }, 150);
    });
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && !self.demo) self.poll();
    });
    this.setDemo(this.demo);
  }

  Live.prototype.setDemo = function (on) {
    this.demo = on;
    clearTimeout(this.pollTimer);
    clearTimeout(this.demoTimer);
    this.root.classList.toggle("is-demo", on);
    var banner = this.root.querySelector("[data-demo-banner]");
    if (banner) banner.hidden = !on;
    var toggle = this.root.querySelector("[data-demo-toggle]");
    if (toggle) toggle.textContent = on ? "Rudi kwenye data halisi" : "Onyesha mfano";
    this.clearLog();
    if (on) {
      this.startDemo();
    } else {
      this.cursor = null;
      this.poll();
    }
  };

  Live.prototype.status = function (state, label) {
    var badge = document.querySelector("[data-live-status]");
    if (!badge) return;
    badge.dataset.state = state;
    badge.querySelector("[data-live-label]").textContent = label;
  };

  // --- Data halisi ----------------------------------------------------------

  Live.prototype.poll = function () {
    var self = this;
    clearTimeout(this.pollTimer);
    if (this.demo) return;
    if (document.hidden) return; // tutaendelea ukurasa ukionekana tena
    var url = this.endpoint + (this.cursor === null ? "" : "?since=" + this.cursor);
    fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (response) {
        if (response.redirected || response.status === 403 || response.status === 401) throw new Error("login");
        if (!response.ok) throw new Error("http " + response.status);
        return response.json();
      })
      .then(function (data) {
        if (self.demo) return;
        self.failures = 0;
        self.status("live", "LIVE");
        self.apply(data);
      })
      .catch(function (err) {
        self.failures += 1;
        self.status("down", err.message === "login" ? "Ingia tena" : "Imekatika, inajaribu tena…");
      })
      .then(function () {
        if (!self.demo) self.pollTimer = setTimeout(function () { self.poll(); }, self.failures ? Math.min(30000, POLL_MS * (1 + self.failures)) : POLL_MS);
      });
  };

  Live.prototype.apply = function (data) {
    var self = this;
    this.gateway = data.gateway || this.gateway;
    this.showOwner = !!data.show_owner;
    this.routerTotal = data.router_total;
    var previous = {};
    this.routers.forEach(function (r) { previous[r.id] = r; });
    this.routers = data.routers;
    this.layout(false);

    // Router imeripoti tena tangu tulipoangalia: packet ndogo ya check-in.
    data.routers.forEach(function (r) {
      var old = previous[r.id];
      if (old && r.seen && old.seen && r.seen !== old.seen) self.send("checkin", r.id);
    });

    Object.assign(this.stats, data.stats);
    this.renderStats();

    if (data.backfill) {
      data.events.forEach(function (e) { self.addLog(e, false); });
    } else {
      var gap = data.events.length ? Math.min(600, POLL_MS / data.events.length) : 0;
      data.events.forEach(function (e, i) {
        setTimeout(function () { self.play(e); }, i * gap);
      });
    }
    this.cursor = data.cursor;
  };

  Live.prototype.play = function (e) {
    if (this.seen[e.id]) return;
    this.seen[e.id] = true;
    this.recent.push(Date.now());
    this.addLog(e, true);
    this.send(e.kind, e.router, e);
    this.renderStats();
  };

  // --- Hali ya mfano ----------------------------------------------------------

  Live.prototype.startDemo = function () {
    var self = this;
    var names = this.routers.length ? this.routers.map(function (r) { return r.name; }) : DEMO_ROUTERS;
    this.routers = names.slice(0, 4).map(function (name, i) {
      return { id: "demo" + i, name: name, owner: "Mfano", online: true, clients: 2 + ((i * 3) % 5), seen: Date.now() };
    });
    this.gateway = "M-Pesa (mfano)";
    this.stats = { today_amount: 18500, today_count: 21, accepts: 34, rejects: 2, clients: 0 };
    this.status("demo", "MFANO");
    this.layout(true);
    this.demoSeq = 1;
    var loop = function () {
      if (!self.demo) return;
      self.demoEvent();
      self.demoTimer = setTimeout(loop, 700 + Math.random() * 1600);
    };
    loop();
  };

  Live.prototype.demoEvent = function () {
    var self = this;
    var router = this.routers[Math.floor(Math.random() * this.routers.length)];
    var device = "…" + Math.random().toString(16).slice(2, 4).toUpperCase() + ":" + Math.random().toString(16).slice(2, 4).toUpperCase();
    var pkg = DEMO_PACKAGES[Math.floor(Math.random() * DEMO_PACKAGES.length)];
    var roll = Math.random();
    var make = function (kind, label, detail, amount) {
      return { id: "d" + self.demoSeq++, kind: kind, label: label, router: router.id, router_name: router.name,
               device: device, detail: detail, amount: amount || null, at: Date.now(), demo: true };
    };
    if (roll < 0.22) {
      // Mteja ananunua: ombi la malipo, analipa, kisha anaingia mwenyewe.
      this.play(make("payment_started", "Ombi la malipo", pkg[0] + " · 0712…" + Math.floor(100 + Math.random() * 899), pkg[1]));
      setTimeout(function () {
        if (!self.demo) return;
        self.stats.today_amount += pkg[1];
        self.stats.today_count += 1;
        self.play(make("payment_paid", "Amelipa", pkg[0], pkg[1]));
        setTimeout(function () {
          if (!self.demo) return;
          router.clients += 1;
          self.stats.accepts += 1;
          self.play(make("auth_accept", "Ameingia", pkg[0] + " · vocha " + Math.random().toString(36).slice(2, 6).toUpperCase() + "…"));
          self.layout(false);
        }, 1800);
      }, 2600);
    } else if (roll < 0.62) {
      var down = (Math.random() * 180).toFixed(1);
      this.play(make("acct_update", "Matumizi", "↓ " + down + " MB · ↑ " + (down / 9).toFixed(1) + " MB"));
    } else if (roll < 0.8) {
      this.stats.accepts += 1;
      this.play(make("auth_accept", "Ameingia", pkg[0] + " · vocha " + Math.random().toString(36).slice(2, 6).toUpperCase() + "…"));
    } else if (roll < 0.88) {
      this.stats.rejects += 1;
      this.play(make("auth_reject", "Amekataliwa", ["Vocha si sahihi", "Muda wa vocha umeisha"][Math.floor(Math.random() * 2)]));
    } else if (roll < 0.95) {
      router.clients = Math.max(0, router.clients - 1);
      this.play(make("acct_stop", "Ametoka", "↓ " + (Math.random() * 400).toFixed(1) + " MB"));
      this.layout(false);
    } else {
      router.seen = Date.now();
      this.send("checkin", router.id);
    }
  };

  // --- Ramani -----------------------------------------------------------------

  Live.prototype.layout = function (force) {
    var vertical = this.svg.getBoundingClientRect().width < 620;
    var max = vertical ? 4 : 7;
    var shown = this.routers.slice(0, max);
    var key = (vertical ? "v" : "h") + shown.map(function (r) { return r.id; }).join(",");
    if (force || key !== this.layoutKey) {
      this.layoutKey = key;
      this.build(shown, vertical);
    }
    this.updateNodes(shown);
  };

  Live.prototype.build = function (routers, vertical) {
    var svg = this.svg;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    this.packets.forEach(function (p) { p.node.remove(); });
    this.packets = [];
    this.nodes = {};
    this.links = {};

    var n = Math.max(routers.length, 1);
    var W, H, pos = {};
    if (vertical) {
      W = 360; H = 450;
      routers.forEach(function (r, i) {
        var x = (W * (i + 1)) / (n + 1);
        pos["phone:" + r.id] = { x: x, y: 44 };
        pos["router:" + r.id] = { x: x, y: 160 };
      });
      pos.cloud = { x: W / 2, y: 300 };
      pos.gateway = { x: W / 2, y: 405 };
    } else {
      W = 760; H = Math.max(300, 60 + n * 84);
      routers.forEach(function (r, i) {
        var y = (H * (i + 1)) / (n + 1);
        pos["phone:" + r.id] = { x: 58, y: y };
        pos["router:" + r.id] = { x: 245, y: y };
      });
      pos.cloud = { x: 500, y: H / 2 };
      pos.gateway = { x: 680, y: H / 2 };
    }
    this.vertical = vertical;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);

    var linkLayer = el("g", { class: "lv-links" }, svg);
    var nodeLayer = el("g", { class: "lv-nodes" }, svg);
    this.packetLayer = el("g", { class: "lv-packets" }, svg);
    var self = this;

    function link(a, b, d, cls) {
      var path = el("path", { d: d, class: "lv-link " + (cls || "") }, linkLayer);
      self.links[a + ">" + b] = path;
      return path;
    }

    var c = pos.cloud, g = pos.gateway;
    routers.forEach(function (r) {
      var p = pos["phone:" + r.id], q = pos["router:" + r.id];
      if (vertical) {
        link("phone:" + r.id, "router:" + r.id, "M" + p.x + "," + (p.y + 24) + " L" + q.x + "," + (q.y - 30), "lv-wifi");
        link("router:" + r.id, "cloud", "M" + q.x + "," + (q.y + 28) + " C" + q.x + "," + (q.y + 80) + " " + c.x + "," + (c.y - 90) + " " + c.x + "," + (c.y - 32));
      } else {
        link("phone:" + r.id, "router:" + r.id, "M" + (p.x + 44) + "," + p.y + " L" + (q.x - 72) + "," + q.y, "lv-wifi");
        link("router:" + r.id, "cloud", "M" + (q.x + 72) + "," + q.y + " C" + (q.x + 140) + "," + q.y + " " + (c.x - 150) + "," + c.y + " " + (c.x - 80) + "," + c.y);
      }
      self.nodes["phone:" + r.id] = self.phoneNode(nodeLayer, p, r);
      self.nodes["router:" + r.id] = self.routerNode(nodeLayer, q, r, vertical);
    });
    if (vertical) {
      link("cloud", "gateway", "M" + c.x + "," + (c.y + 32) + " L" + g.x + "," + (g.y - 28));
    } else {
      link("cloud", "gateway", "M" + (c.x + 80) + "," + c.y + " L" + (g.x - 72) + "," + g.y);
    }

    var cloud = el("g", { class: "lv-node lv-cloud", transform: "translate(" + c.x + "," + c.y + ")" }, nodeLayer);
    el("circle", { r: 40, class: "lv-halo" }, cloud);
    el("rect", { x: -80, y: -32, width: 160, height: 64, rx: 16, class: "lv-box" }, cloud);
    text(cloud, 0, -4, "JamiiLite", "lv-title");
    text(cloud, 0, 16, "RADIUS · Mfumo", "lv-sub");
    this.nodes.cloud = cloud;

    var gw = el("g", { class: "lv-node lv-gateway", transform: "translate(" + g.x + "," + g.y + ")" }, nodeLayer);
    el("rect", { x: -72, y: -28, width: 144, height: 56, rx: 12, class: "lv-box" }, gw);
    this.gatewayLabel = text(gw, 0, -3, clip(this.gateway, 20), "lv-title");
    text(gw, 0, 16, "M-Pesa · Tigo · Airtel", "lv-sub");
    this.nodes.gateway = gw;

    if (!routers.length) {
      text(svg, W / 2, H / 2 - 70, "Ongeza router ili uone mtandao wako hapa", "lv-empty");
    }
    var hidden = (this.routerTotal || this.routers.length) - routers.length;
    if (hidden > 0) text(svg, vertical ? W / 2 : 245, H - 10, "+ routers " + hidden + " zaidi", "lv-sub");
  };

  Live.prototype.phoneNode = function (layer, p, r) {
    var g = el("g", { class: "lv-node lv-phones", transform: "translate(" + p.x + "," + p.y + ")" }, layer);
    g._phones = el("g", {}, g);
    g._count = text(g, 0, 36, "", "lv-sub");
    return g;
  };

  Live.prototype.routerNode = function (layer, q, r, vertical) {
    var w = vertical ? 92 : 144, h = vertical ? 56 : 52;
    var g = el("g", { class: "lv-node lv-router", transform: "translate(" + q.x + "," + q.y + ")" }, layer);
    el("rect", { x: -w / 2, y: -h / 2, width: w, height: h, rx: 12, class: "lv-box" }, g);
    g._dot = el("circle", { cx: -w / 2 + 14, cy: vertical ? -h / 2 + 14 : 0, r: 5, class: "lv-dot" }, g);
    if (vertical) {
      text(g, 6, -4, clip(r.name, 10), "lv-title");
      g._sub = text(g, 0, 16, "", "lv-sub");
    } else {
      text(g, -w / 2 + 28, -3, clip(r.name, 15), "lv-title", "start");
      g._sub = text(g, -w / 2 + 28, 15, "", "lv-sub", "start");
    }
    return g;
  };

  Live.prototype.updateNodes = function (routers) {
    var self = this;
    if (this.gatewayLabel) this.gatewayLabel.textContent = clip(this.gateway, 20);
    routers.forEach(function (r) {
      var node = self.nodes["router:" + r.id], phones = self.nodes["phone:" + r.id];
      if (!node) return;
      node.classList.toggle("is-offline", !r.online);
      var owner = self.showOwner && !self.vertical ? " · " + clip(r.owner, 10) : "";
      node._sub.textContent = (r.online ? "Online" : "Offline") + owner;
      var link = self.links["router:" + r.id + ">cloud"];
      if (link) link.classList.toggle("is-down", !r.online);

      // Simu ndogo moja kwa kila mteja (hadi 5), kisha idadi kamili chini yake.
      var group = phones._phones;
      while (group.firstChild) group.removeChild(group.firstChild);
      var count = Math.min(r.clients, 5);
      var spread = 13;
      for (var i = 0; i < Math.max(count, 1); i++) {
        var x = (i - (Math.max(count, 1) - 1) / 2) * spread;
        el("rect", { x: x - 5, y: -12, width: 10, height: 18, rx: 2.5, class: "lv-phone" + (count ? "" : " is-empty") }, group);
      }
      phones._count.textContent = r.clients === 1 ? "mteja 1" : "wateja " + r.clients;
    });
  };

  // --- Packets ------------------------------------------------------------------

  Live.prototype.route = function (hops, routerId) {
    var names = hops.map(function (h) { return h === "phone" || h === "router" ? h + ":" + routerId : h; });
    var legs = [];
    for (var i = 0; i < names.length - 1; i++) {
      var forward = this.links[names[i] + ">" + names[i + 1]];
      var backward = this.links[names[i + 1] + ">" + names[i]];
      if (!forward && !backward) return null; // router haionekani kwenye ramani
      legs.push({ path: forward || backward, reverse: !forward, to: names[i + 1] });
    }
    return legs;
  };

  Live.prototype.send = function (kind, routerId, event) {
    var spec = KINDS[kind];
    if (!spec || reduceMotion || !this.packetLayer) return;
    var legs = this.route(spec.hops, routerId);
    if (!legs) return;
    var self = this;
    this.launch(legs, spec, function () {
      if (spec.reply) {
        var back = self.route(spec.hops.slice().reverse(), routerId);
        if (back) self.launch(back, { cls: spec.reply, shape: spec.replyShape, tiny: spec.tiny, small: spec.small });
      }
      if (spec.coin && event && event.amount) self.float(routerId, "+" + tsh(event.amount));
    });
  };

  Live.prototype.launch = function (legs, spec, done) {
    var r = spec.tiny ? 3 : spec.small ? 4 : spec.coin ? 7 : 5.5;
    var g = el("g", { class: "lv-packet " + spec.cls }, this.packetLayer);
    el("circle", { r: r * 2.4, class: "lv-glow" }, g);
    // Umbo ni kiashiria cha pili, ili rangi isiwe njia pekee ya kutofautisha.
    if (spec.shape === "diamond") {
      el("rect", { x: -r, y: -r, width: r * 2, height: r * 2, rx: 1.5, transform: "rotate(45)", class: "lv-core" }, g);
    } else if (spec.shape === "ring") {
      el("circle", { r: r, class: "lv-core lv-ring" }, g);
    } else {
      el("circle", { r: r, class: "lv-core" }, g);
    }
    var first = legs[0];
    var len = first.path.getTotalLength();
    var start = first.path.getPointAtLength(first.reverse ? len : 0);
    g.setAttribute("transform", "translate(" + start.x.toFixed(1) + "," + start.y.toFixed(1) + ")");
    this.packets.push({ node: g, legs: legs, leg: 0, t: 0, len: len, done: done });
    if (!this.running) {
      this.running = true;
      this.last = performance.now();
      requestAnimationFrame(this.tick);
    }
  };

  Live.prototype.tick = function (now) {
    var dt = Math.min(64, now - this.last);
    this.last = now;
    var self = this;
    this.packets = this.packets.filter(function (p) {
      p.t += dt * SPEED;
      var leg = p.legs[p.leg];
      if (p.t >= p.len) {
        self.flash(leg.to);
        p.leg += 1;
        if (p.leg >= p.legs.length) {
          p.node.remove();
          if (p.done) p.done();
          return false;
        }
        p.t = 0;
        leg = p.legs[p.leg];
        p.len = leg.path.getTotalLength();
      }
      var at = leg.path.getPointAtLength(leg.reverse ? p.len - p.t : p.t);
      p.node.setAttribute("transform", "translate(" + at.x.toFixed(1) + "," + at.y.toFixed(1) + ")");
      return true;
    });
    if (this.packets.length) {
      requestAnimationFrame(this.tick);
    } else {
      this.running = false;
    }
  };

  Live.prototype.flash = function (name) {
    var node = this.nodes[name];
    if (!node) return;
    node.classList.remove("is-hit");
    void node.getBBox(); // anzisha upya animation ya CSS
    node.classList.add("is-hit");
    clearTimeout(node._hit);
    node._hit = setTimeout(function () { node.classList.remove("is-hit"); }, 450);
  };

  Live.prototype.float = function (routerId, label) {
    var node = this.nodes["router:" + routerId];
    if (!node) return;
    var box = node.getBBox();
    var m = node.transform.baseVal.consolidate().matrix;
    // Pembeni mwa router (mlalo) au juu yake (wima), isifunike router nyingine.
    var t = this.vertical
      ? text(this.packetLayer, m.e, m.f + box.y - 10, label, "lv-float")
      : text(this.packetLayer, m.e + box.x + box.width + 8, m.f - 10, label, "lv-float", "start");
    setTimeout(function () { t.remove(); }, 1800);
  };

  // --- Takwimu na log -------------------------------------------------------

  Live.prototype.renderStats = function () {
    var cutoff = Date.now() - 60000;
    this.recent = this.recent.filter(function (t) { return t >= cutoff; });
    var clients = this.routers.reduce(function (sum, r) { return sum + (r.online ? r.clients : 0); }, 0);
    var values = {
      today_amount: tsh(this.stats.today_amount || 0),
      clients: String(this.demo ? clients : this.stats.clients || clients),
      accepts: String(this.stats.accepts || 0),
      rejects: String(this.stats.rejects || 0),
      per_minute: String(this.recent.length),
    };
    for (var key in values) {
      var node = this.root.querySelector('[data-stat="' + key + '"]');
      if (node && node.textContent !== values[key]) {
        node.textContent = values[key];
        node.classList.remove("is-bump");
        void node.offsetWidth;
        node.classList.add("is-bump");
      }
    }
  };

  Live.prototype.clearLog = function () {
    while (this.log.firstChild) this.log.removeChild(this.log.firstChild);
    this.seen = {};
  };

  Live.prototype.addLog = function (e, fresh) {
    var spec = KINDS[e.kind] || {};
    var li = document.createElement("li");
    li.className = "lv-entry" + (fresh ? " is-new" : "");
    var time = document.createElement("time");
    time.textContent = clock(e.at);
    var tag = document.createElement("span");
    tag.className = "lv-tag lv-tag-" + (spec.tag || "muted");
    tag.textContent = e.label;
    var body = document.createElement("span");
    body.className = "lv-body";
    var where = document.createElement("strong");
    where.textContent = e.router_name;
    body.appendChild(where);
    var bits = [e.device, e.detail].filter(Boolean).join(" · ");
    if (bits) body.appendChild(document.createTextNode(" · " + bits));
    li.appendChild(time);
    li.appendChild(tag);
    li.appendChild(body);
    if (e.amount && (e.kind === "payment_paid" || e.kind === "payment_started")) {
      var amount = document.createElement("span");
      amount.className = "lv-amount" + (e.kind === "payment_paid" ? " is-in" : "");
      amount.textContent = (e.kind === "payment_paid" ? "+" : "") + tsh(e.amount);
      li.appendChild(amount);
    }
    this.log.insertBefore(li, this.log.firstChild);
    while (this.log.children.length > MAX_LOG) this.log.removeChild(this.log.lastChild);
    var empty = this.root.querySelector("[data-log-empty]");
    if (empty) empty.hidden = true;
  };

  document.querySelectorAll("[data-live]").forEach(function (root) { new Live(root); });
})();
