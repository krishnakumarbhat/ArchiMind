/* 02_studio_tabs.js — tabs + off-canvas drawers (assistant, TOC) with backdrop/Escape. */
(function (global) {
  "use strict";
  var DRAWERS = ["chat-open", "toc-open"];

  function sync() {
    var bd = document.getElementById("backdrop");
    var open = DRAWERS.some(function (c) { return document.body.classList.contains(c); });
    if (bd) bd.classList.toggle("show", open);
  }
  function closeDrawers() {
    DRAWERS.forEach(function (c) { document.body.classList.remove(c); });
    sync();
  }
  function open(cls) {
    closeDrawers();
    document.body.classList.add(cls);
    sync();
  }
  function show(tab) {
    document.querySelectorAll(".tabs button").forEach(function (x) {
      x.classList.toggle("active", x.dataset.stab === tab);
    });
    document.querySelectorAll(".tabpage").forEach(function (p) {
      p.classList.toggle("active", p.dataset.page === tab);
    });
    closeDrawers();
    document.dispatchEvent(new CustomEvent("studio:tab", { detail: tab }));
  }
  function init() {
    document.querySelectorAll(".tabs button").forEach(function (b) {
      b.addEventListener("click", function () { show(b.dataset.stab); });
    });
    var fab = document.getElementById("chatFab");
    if (fab) fab.addEventListener("click", function () { open("chat-open"); });
    var close = document.getElementById("chatClose");
    if (close) close.addEventListener("click", closeDrawers);
    var toc = document.getElementById("tocBtn");
    if (toc) toc.addEventListener("click", function () { open("toc-open"); });
    var bd = document.getElementById("backdrop");
    if (bd) bd.addEventListener("click", closeDrawers);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrawers(); });
    var mq = window.matchMedia("(min-width: 1024px)");
    if (mq.addEventListener) mq.addEventListener("change", function (e) { if (e.matches) closeDrawers(); });
  }
  global.StudioTabs = { init: init, show: show, open: open, closeDrawers: closeDrawers };
})(window);
