/* 00_app.js — client router: golden demos, analysis polling, blast-radius, chat. */
(function (global) {
  "use strict";

  var state = { golden: [], current: null, pollTimer: null, pz: null, diagrams: {}, tab: "hld" };

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function toast(msg, bad) {
    var el = $("notice");
    if (!el) return;
    el.textContent = msg;
    el.className = "status-card" + (bad ? " is-bad" : "");
    el.style.display = "block";
  }

  function mermaidCode(graph) {
    if (!graph) return "";
    if (typeof graph === "string") return graph;
    var g = graph.graph || graph;
    return (g && g.mermaid_code) || "";
  }

  function renderDiagram() {
    var host = $("mermaidHost");
    if (!host) return;
    var code = state.diagrams[state.tab] || "";
    host.innerHTML = "";
    if (!code) {
      host.innerHTML = '<div class="canvas-empty">No diagram for this view yet.</div>';
      return;
    }
    if (!global.mermaid) {
      host.innerHTML = '<div class="canvas-error">Diagram renderer still loading…</div>';
      return;
    }
    var id = "mmd-" + Date.now();
    try {
      global.mermaid.render(id, code).then(function (out) {
        host.innerHTML = out.svg;
        if (state.pz) state.pz.fit();
      }).catch(function (err) {
        host.innerHTML = '<div class="canvas-error">Diagram failed to render: ' + esc(err && err.message) + "</div>";
      });
    } catch (err) {
      host.innerHTML = '<div class="canvas-error">Diagram failed to render.</div>';
    }
  }

  function setDiagrams(hld, lld, flow) {
    state.diagrams = { hld: mermaidCode(hld), lld: mermaidCode(lld), flow: mermaidCode(flow) };
    document.querySelectorAll(".diagram-tabs button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.tab === state.tab);
    });
    renderDiagram();
  }

  function renderInspector(doc) {
    var insp = $("inspectorBody");
    if (!insp) return;
    var stats = doc.stats || {};
    var html = "";
    html += "<h2>" + esc(doc.name || doc.repo_name || "Repository") + "</h2>";
    if (doc.description) html += "<p>" + esc(doc.description) + "</p>";
    if (doc.chat_summary) html += '<div class="status-card">' + esc(doc.chat_summary) + "</div>";
    var keys = [["files", "Files"], ["py_files", "Python"], ["classes", "Classes"], ["functions", "Functions"], ["edges", "Edges"]];
    html += '<div class="stat-grid">';
    keys.forEach(function (kv) {
      if (stats[kv[0]] != null) html += '<div class="stat"><b>' + esc(stats[kv[0]]) + "</b><span>" + kv[1] + "</span></div>";
    });
    html += "</div>";
    var inv = doc.invariants || [];
    if (inv.length) {
      html += "<h2>Architecture invariants</h2>";
      inv.forEach(function (r) {
        html += '<div class="invariant"><span class="' + (r.passed ? "ok" : "fail") + '">' + (r.passed ? "✓" : "✗") + "</span><span>" + esc(r.id) + "</span></div>";
      });
    }
    if (doc.chat_response) {
      html += "<h2>Handbook</h2><div class='doc-body'><pre>" + esc(String(doc.chat_response).slice(0, 4000)) + "</pre></div>";
    }
    html += "<h2>Blast radius</h2>"
      + '<div class="analyze-form"><input id="blastSymbol" type="text" placeholder="Symbol, e.g. UserRepo.fetch">'
      + '<button class="btn btn-ghost" id="blastBtn" type="button">Trace impact</button></div>'
      + '<div id="blastOut"></div>';
    insp.innerHTML = html;
    var btn = $("blastBtn");
    if (btn) btn.addEventListener("click", runBlast);
  }

  function runBlast() {
    var sym = ($("blastSymbol") || {}).value || "";
    sym = sym.trim();
    if (!sym) { toast("Enter a symbol to trace.", true); return; }
    var q = "symbol=" + encodeURIComponent(sym);
    if (state.current && state.current.golden) q += "&golden=" + encodeURIComponent(state.current.golden);
    if (state.current && state.current.analysis_id) q += "&analysis_id=" + encodeURIComponent(state.current.analysis_id);
    fetch("/api/blast-radius?" + q)
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        var out = $("blastOut");
        if (!out) return;
        if (!res.ok) { out.innerHTML = '<div class="status-card">' + esc(res.j.error || "Trace failed.") + "</div>"; return; }
        var list = (res.j.impacted || []).map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("");
        out.innerHTML = "<p>" + esc(res.j.edges) + " downstream symbols · " + esc(res.j.ms) + " ms</p>"
          + (list ? '<ul class="impact-list">' + list + "</ul>" : "<p>No downstream impact.</p>");
      })
      .catch(function () { toast("Trace request failed.", true); });
  }

  function showGolden(g) {
    state.current = { golden: g.id };
    document.querySelectorAll(".pill").forEach(function (p) {
      p.classList.toggle("active", p.dataset.golden === g.id);
    });
    setDiagrams(g.hld_mermaid, g.lld_mermaid, g.flow_mermaid);
    renderInspector(g);
    if (window.Drawer) window.Drawer.closeAll();
  }

  function loadGolden() {
    fetch("/api/golden")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.golden = data.golden || [];
        var bar = $("pillbar");
        if (!bar) return;
        state.golden.forEach(function (g) {
          var b = document.createElement("button");
          b.className = "pill";
          b.dataset.golden = g.id;
          b.textContent = g.name || g.id;
          b.addEventListener("click", function () { showGolden(g); });
          bar.appendChild(b);
        });
        var first = state.golden.filter(function (g) { return g.cached; })[0] || state.golden[0];
        if (first && first.cached) showGolden(first);
      })
      .catch(function () { toast("Golden demos unavailable.", true); });
  }

  function setStatus(msg, progress) {
    var card = $("statusCard");
    if (!card) return;
    card.style.display = "block";
    $("statusMsg").textContent = msg;
    $("statusBar").style.width = Math.max(0, Math.min(100, progress)) + "%";
  }

  function pollStatus(analysisId, repoName) {
    clearInterval(state.pollTimer);
    state.pollTimer = setInterval(function () {
      fetch("/api/status?analysis_id=" + encodeURIComponent(analysisId))
        .then(function (r) { return r.json(); })
        .then(function (s) {
          setStatus((s.stage || s.status) + " — " + (s.message || ""), s.progress || 0);
          if (s.status === "completed" && s.result) {
            clearInterval(state.pollTimer);
            setStatus("Analysis complete.", 100);
            var res = s.result;
            state.current = { analysis_id: analysisId };
            setDiagrams(res.hld_graph, res.lld_graph, res.flow_graph);
            renderInspector({
              name: repoName, chat_summary: res.chat_summary,
              chat_response: res.chat_response, invariants: res.invariants || []
            });
            var link = $("resultsLink");
            if (link) { link.href = "/doc?analysis_id=" + encodeURIComponent(analysisId); link.style.display = ""; }
          } else if (s.status === "error") {
            clearInterval(state.pollTimer);
            toast("Analysis failed: " + (s.error || s.message || "unknown"), true);
          }
        })
        .catch(function () { /* ponytail: keep polling through transient blips */ });
    }, 3000);
  }

  function submitAnalysis(e) {
    e.preventDefault();
    var input = $("repoUrl");
    var url = (input.value || "").trim();
    if (!url) { toast("Enter a public GitHub repository URL.", true); return; }
    var btn = $("analyzeBtn");
    if (btn) btn.disabled = true;
    setStatus("Starting analysis…", 2);
    fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: url })
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, code: r.status, j: j }; }); })
      .then(function (res) {
        if (btn) btn.disabled = false;
        if (!res.ok) { toast(res.j.error || res.j.message || "Could not start analysis.", true); return; }
        var name = url.split("/").slice(-2).join("/");
        pollStatus(res.j.analysis_id, name);
      })
      .catch(function () {
        if (btn) btn.disabled = false;
        toast("Could not reach the server.", true);
      });
  }

  function init() {
    if (global.mermaid) global.mermaid.initialize({ startOnLoad: false, theme: "dark" });
    var vp = $("viewport"), stage = $("stage");
    if (vp && stage && global.PanZoom) state.pz = new global.PanZoom(vp, stage);
    if (window.Drawer) window.Drawer.init();
    loadGolden();
    var form = $("analyzeForm");
    if (form) form.addEventListener("submit", submitAnalysis);
    document.querySelectorAll(".diagram-tabs button").forEach(function (b) {
      b.addEventListener("click", function () {
        state.tab = b.dataset.tab;
        document.querySelectorAll(".diagram-tabs button").forEach(function (x) {
          x.classList.toggle("active", x === b);
        });
        renderDiagram();
      });
    });
    var tb = $("canvasToolbar");
    if (tb && state.pz !== null) {
      tb.addEventListener("click", function (e) {
        var act = e.target && e.target.dataset && e.target.dataset.act;
        if (!act || !state.pz) return;
        if (act === "zin") state.pz.zoomBy(1.25);
        else if (act === "zout") state.pz.zoomBy(0.8);
        else if (act === "reset") state.pz.reset();
        else if (act === "fit") state.pz.fit();
        else if (act === "full") { var w = $("canvasWrap"); if (w && w.requestFullscreen) w.requestFullscreen(); }
        else if (act === "svg") {
          var svg = state.pz.exportSVG();
          if (!svg) return;
          var blob = new Blob([svg], { type: "image/svg+xml" });
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "archimind-diagram.svg";
          a.click();
          setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
        }
      });
    }
  }

  global.ArchiMind = { init: init };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
