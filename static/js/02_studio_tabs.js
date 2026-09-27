/* 02_studio_tabs.js — tab switching + drawer/backdrop/Escape (transform-only CSS). */
(function (global) {
  "use strict";

  function closeDrawers() {
    document.body.classList.remove("nav-open");
    var bd = document.getElementById("backdrop");
    if (bd) bd.classList.remove("show");
  }

  function init() {
    document.querySelectorAll(".tabs button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll(".tabs button").forEach(function (x) {
          x.classList.toggle("active", x === b);
        });
        document.querySelectorAll(".tabpage").forEach(function (p) {
          p.classList.toggle("active", p.dataset.page === b.dataset.stab);
        });
        closeDrawers();
      });
    });
    var nav = document.getElementById("studioNavToggle");
    if (nav) {
      nav.addEventListener("click", function () {
        document.body.classList.toggle("nav-open");
        var bd = document.getElementById("backdrop");
        if (bd) bd.classList.toggle("show", document.body.classList.contains("nav-open"));
      });
    }
    var bd = document.getElementById("backdrop");
    if (bd) bd.addEventListener("click", closeDrawers);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDrawers();
    });
    var mq = window.matchMedia("(min-width: 1024px)");
    function onChange(e) { if (e.matches) closeDrawers(); }
    if (mq.addEventListener) mq.addEventListener("change", onChange);
  }

  global.StudioTabs = { init: init, closeDrawers: closeDrawers };
})(window);
