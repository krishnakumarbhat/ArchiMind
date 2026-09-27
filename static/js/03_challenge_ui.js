/* 03_challenge_ui.js — Challenge Me panel: fetch schema, render, reveal. */
(function (global) {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function load(query) {
    var out = document.getElementById("challengeOut");
    if (out) out.innerHTML = "<p class='hint'>Forging a challenge from untested seams…</p>";
    fetch("/api/challenge?" + query)
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!out) return;
        if (!res.ok) { out.innerHTML = "<p class='hint'>" + esc(res.j.error || "No challenge available.") + "</p>"; return; }
        var c = res.j.challenge;
        var hints = (c.hints || []).map(function (h) { return "<li>" + esc(h) + "</li>"; }).join("");
        out.innerHTML = "<div class='challenge'><h3>" + esc(c.title) + "</h3>"
          + "<p>" + esc(c.description) + "</p>"
          + "<p class='hint'>Target: " + esc(c.target_file) + " · " + esc(c.symbol) + "</p>"
          + "<pre>" + esc(c.starter_code) + "</pre>"
          + (hints ? "<ul>" + hints + "</ul>" : "")
          + "</div>";
      })
      .catch(function () {
        if (out) out.innerHTML = "<p class='hint'>Could not load a challenge.</p>";
      });
  }

  global.ChallengeUI = { load: load };
})(window);
