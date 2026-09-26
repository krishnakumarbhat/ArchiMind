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

  PanZoom.prototype.zoomAt = function (cx, cy, factor) {
    var k2 = Math.min(4, Math.max(0.2, this.k * factor));
    var s = k2 / this.k;
    this.x = cx - (cx - this.x) * s;
    this.y = cy - (cy - this.y) * s;
    this.k = k2;
    this.apply();
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
    var r = this.vp.getBoundingClientRect();
    var sw = this.stage.scrollWidth || 1;
    var sh = this.stage.scrollHeight || 1;
    this.k = Math.min(2, Math.max(0.2, Math.min((r.width - 48) / sw, (r.height - 48) / sh)));
    this.x = 24;
    this.y = 24;
    this.apply();
  };

  PanZoom.prototype._bind = function () {
    var self = this;
    var lx = 0, ly = 0, drag = false;

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
      if (self._pointers.size === 0) drag = false;
    }
    this.vp.addEventListener("pointerup", up);
    this.vp.addEventListener("pointercancel", up);
    this.vp.addEventListener("dblclick", function () { self.fit(); });
  };

  PanZoom.prototype.exportSVG = function () {
    var svg = this.stage.querySelector("svg");
    if (!svg) return null;
    return new XMLSerializer().serializeToString(svg);
  };

  global.PanZoom = PanZoom;
})(window);
