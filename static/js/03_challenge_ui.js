/* 03_challenge_ui.js — Challenge Me: fetch a CPG-mined task, render it, copy starter. */
(function (global) {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function load(query) {
    var out = document.getElementById("challengeOut");
    if (!out) return;
    out.innerHTML = "<div class='skeleton' style='height:180px;margin-top:14px'></div>";
    fetch("/api/challenge?" + query)
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { out.innerHTML = "<p class='hint'>" + esc(res.j.error || "No challenge available.") + "</p>"; return; }
        var c = res.j.challenge;
        var hints = (c.hints || []).map(function (h) { return "<li>" + esc(h) + "</li>"; }).join("");
        out.innerHTML = "<div class='card challenge' style='margin-top:14px'>"
          + "<b>" + esc(c.title) + "</b>"
          + "<p>" + esc(c.description) + "</p>"
          + "<p class='hint'>🎯 " + esc(c.target_file) + " · <code>" + esc(c.symbol) + "</code></p>"
          + "<pre id='challengeCode'>" + esc(c.starter_code) + "</pre>"
          + "<div class='row'><button class='btn btn-ghost' id='copyChallenge' type='button'>Copy failing test</button>"
          + "<button class='btn btn-ghost' id='nextChallenge' type='button'>Next challenge</button></div>"
          + (hints ? "<ul class='hint'>" + hints + "</ul>" : "")
          + "</div>";
        var copy = document.getElementById("copyChallenge");
        if (copy) copy.addEventListener("click", function () {
          if (navigator.clipboard) navigator.clipboard.writeText(c.failing_test || c.starter_code);
          copy.textContent = "Copied ✓";
        });
        var next = document.getElementById("nextChallenge");
        if (next) next.addEventListener("click", function () {
          load(query.replace(/&n=\d+/, "") + "&n=" + (Math.floor(Math.random() * 8) + 1));
        });
      })
      .catch(function () { out.innerHTML = "<p class='hint'>Could not load a challenge.</p>"; });
  }

  global.ChallengeUI = { load: load };
})(window);
