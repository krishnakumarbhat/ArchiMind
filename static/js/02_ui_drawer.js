/* 02_ui_drawer.js — responsive drawer toggles, backdrop, Escape handling. */
(function (global) {
  "use strict";

  function closeAll() {
    document.body.classList.remove("nav-open", "inspector-open");
    var bd = document.getElementById("backdrop");
    if (bd) bd.classList.remove("show");
  }

  function syncBackdrop() {
    var bd = document.getElementById("backdrop");
    if (!bd) return;
    var open = document.body.classList.contains("nav-open") || document.body.classList.contains("inspector-open");
    bd.classList.toggle("show", open);
  }

  function toggle(cls) {
    var other = cls === "nav-open" ? "inspector-open" : "nav-open";
    document.body.classList.remove(other);
    document.body.classList.toggle(cls);
    syncBackdrop();
  }

  function init() {
    var navBtn = document.getElementById("navToggle");
    var inspBtn = document.getElementById("inspectorToggle");
    var bd = document.getElementById("backdrop");
    if (navBtn) navBtn.addEventListener("click", function () { toggle("nav-open"); });
    if (inspBtn) inspBtn.addEventListener("click", function () { toggle("inspector-open"); });
    if (bd) bd.addEventListener("click", closeAll);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeAll();
    });
    // ponytail: drawers are mobile-only; drop classes when resizing up to desktop
    var mq = window.matchMedia("(min-width: 1024px)");
    function onChange(e) { if (e.matches) closeAll(); }
    if (mq.addEventListener) mq.addEventListener("change", onChange);
  }

  global.Drawer = { init: init, closeAll: closeAll };
})(window);
