/* 01_pan_zoom.js — transform-only pan/zoom engine (mouse + touch + toolbar). */
(function (global) {
  "use strict";

  function PanZoom(viewport, stage) {
    this.vp = viewport;
    this.stage = stage;
    this.x = 0;
    this.y = 0;
    this.k = 1;
    this._pointers = new Map();
    this._pinch = 0;
    this._bind();
    this.apply();
  }

  PanZoom.prototype.apply = function () {
    this.stage.style.transform = "translate(" + this.x + "px," + this.y + "px) scale(" + this.k + ")";
  };

  PanZoom.prototype.showZoom = function () {
    // Visible zoom feedback so users can tell gestures are registering.
    var chip = this.vp.querySelector(".zoom-chip");
    if (!chip) {
      chip = document.createElement("div");
      chip.className = "zoom-chip";
      this.vp.appendChild(chip);
    }
    chip.textContent = Math.round(this.k * 100) + "%";
    chip.classList.add("show");
    var self = this;
    if (this._zoomT) window.clearTimeout(this._zoomT);
    this._zoomT = window.setTimeout(function () { chip.classList.remove("show"); }, 900);
  };

  PanZoom.prototype.zoomAt = function (cx, cy, factor) {
    var k2 = Math.min(4, Math.max(0.2, this.k * factor));
    var s = k2 / this.k;
    this.x = cx - (cx - this.x) * s;
    this.y = cy - (cy - this.y) * s;
    this.k = k2;
    this.apply();
    this.showZoom();
  };

  PanZoom.prototype.zoomBy = function (factor) {
    var r = this.vp.getBoundingClientRect();
    this.zoomAt(r.width / 2, r.height / 2, factor);
  };

  PanZoom.prototype.reset = function () {
    this.x = 0;
    this.y = 0;
    this.k = 1;
    this.apply();
  };

  PanZoom.prototype.fit = function () {
    // ponytail: draw.io-style — legibility first. Fits only when the diagram is
    // smaller than the viewport; otherwise open at 100% top-left and pan.
    var r = this.vp.getBoundingClientRect();
    var svg = this.stage.querySelector("svg");
    var sw = (svg && svg.getBoundingClientRect().width / this.k) || this.stage.scrollWidth || 1;
    var sh = (svg && svg.getBoundingClientRect().height / this.k) || this.stage.scrollHeight || 1;
    var pad = 48;
    var kfit = Math.min((r.width - pad) / sw, (r.height - pad) / sh);
    if (kfit >= 1) {
      this.k = Math.min(kfit, 2);
      this.x = Math.max(12, (r.width - sw * this.k) / 2);
      this.y = Math.max(12, (r.height - sh * this.k) / 2);
    } else {
      this.k = 1;
      this.x = 24;
      this.y = 24;
    }
    this.apply();
  };

  PanZoom.prototype.recenter = function () {
    // Recompute the SVG box and pull a drifted diagram back into view.
    var r = this.vp.getBoundingClientRect();
    var svg = this.stage.querySelector("svg");
    if (!svg || !r.width || !r.height) return;
    var box = svg.getBoundingClientRect();
    var cx = box.left + box.width / 2, cy = box.top + box.height / 2;
    var vx = r.left + r.width / 2, vy = r.top + r.height / 2;
    var far = Math.abs(cx - vx) > r.width || Math.abs(cy - vy) > r.height;
    if (far || box.width === 0) this.fit();
    else { this.x += vx - cx; this.y += vy - cy; this.apply(); }
  };

  PanZoom.prototype._bind = function () {
    var self = this;
    var lx = 0, ly = 0, drag = false;
    var resizeTimer = 0;
    window.addEventListener("resize", function () {
      // ponytail: debounced — zoom/resize fires continuously, layout is transform-only
      if (resizeTimer) window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(function () { self.recenter(); }, 180);
    });

    this.vp.addEventListener("wheel", function (e) {
      e.preventDefault();
      var r = self.vp.getBoundingClientRect();
      self.zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.12 : 0.89);
    }, { passive: false });

    this.vp.addEventListener("pointerdown", function (e) {
      self._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (self._pointers.size === 1) { drag = true; lx = e.clientX; ly = e.clientY; }
      if (self._pointers.size === 2) {
        var p = Array.from(self._pointers.values());
        self._pinch = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
        drag = false;
      }
      self.vp.setPointerCapture(e.pointerId);
    });

    this.vp.addEventListener("pointermove", function (e) {
      if (!self._pointers.has(e.pointerId)) return;
      self._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (self._pointers.size === 2) {
        var p = Array.from(self._pointers.values());
        var d = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
        if (self._pinch > 0) {
          var r = self.vp.getBoundingClientRect();
          self.zoomAt((p[0].x + p[1].x) / 2 - r.left, (p[0].y + p[1].y) / 2 - r.top, d / self._pinch);
        }
        self._pinch = d;
        return;
      }
      if (drag) {
        var dx = e.clientX - lx, dy = e.clientY - ly;
        // ponytail: two-finger pan arrives here as pointer pairs; single-pointer drag is the pan path
        self.x += dx;
        self.y += dy;
        lx = e.clientX;
        ly = e.clientY;
        self.apply();
      }
    });

    function up(e) {
      self._pointers.delete(e.pointerId);
      if (self._pointers.size < 2) self._pinch = 0;
      // ponytail: pinch lifting to one finger must hand off to pan, not die
      if (self._pointers.size === 1) {
        var rest = Array.from(self._pointers.values())[0];
        drag = true; lx = rest.x; ly = rest.y;
      } else if (self._pointers.size === 0) {
        drag = false;
      }
      self.showZoom();
    }
    this.vp.addEventListener("pointerup", up);
    this.vp.addEventListener("pointercancel", up);
    // ponytail: iOS Safari fires gesture events and page-zooms unless stopped here
    ["gesturestart", "gesturechange", "gestureend"].forEach(function (t) {
      self.vp.addEventListener(t, function (e) { e.preventDefault(); }, { passive: false });
    });
    this.vp.addEventListener("touchmove", function (e) {
      if (e.touches && e.touches.length > 1) e.preventDefault();
    }, { passive: false });
    this.vp.addEventListener("dblclick", function () { self.fit(); self.showZoom(); });
  };

  PanZoom.prototype.exportSVG = function () {
    var svg = this.stage.querySelector("svg");
    if (!svg) return null;
    return new XMLSerializer().serializeToString(svg);
  };

  global.PanZoom = PanZoom;
})(window);
