/**
 * Live-filter search for the genindex page.
 *
 * Adds a search input above the alphabetical index that filters
 * entries in real-time as the user types.  Matching letters and
 * entries stay visible; non-matching ones are hidden.
 */
(function () {
  if (document.querySelector(".genindex-jumpbox") === null) return;

  function init() {
    var body = document.querySelector(".body") || document.querySelector(".document");
    if (!body) return;

    var genindex = body.querySelector("[id='the-index']") || body.querySelector(".genindextable");
    if (!genindex) {
      genindex = body.querySelectorAll("table")[0];
    }
    if (!genindex) return;

    // ---- build search box ----
    var searchBox = document.createElement("div");
    searchBox.style.cssText = "margin: 0 0 18px 0;";

    var input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Filter index...";
    input.style.cssText =
      "width:100%;max-width:400px;padding:6px 10px;" +
      "border:1px solid #ccc;border-radius:6px;font-size:14px;";
    searchBox.appendChild(input);

    genindex.parentNode.insertBefore(searchBox, genindex);

    // ---- collect entries ----
    var entries = [];
    var rows = genindex.querySelectorAll("tr");
    rows.forEach(function (row) {
      var links = row.querySelectorAll("a");
      if (links.length === 0) return;
      var text = Array.from(links)
        .map(function (a) { return a.textContent; })
        .join(" ");
      entries.push({ row: row, text: text.toLowerCase() });
    });

    // ---- live filter ----
    var timer;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        var q = input.value.toLowerCase().trim();
        var hasMatch = false;

        entries.forEach(function (e) {
          if (!q || e.text.indexOf(q) !== -1) {
            e.row.style.display = "";
            hasMatch = true;
          } else {
            e.row.style.display = "none";
          }
        });

        // Hide letter-header rows that have no visible children after filtering
        var allRows = genindex.querySelectorAll("tr");
        allRows.forEach(function (r) {
          var code = r.querySelector("code");
          if (!code) return;
          var next = r.nextElementSibling;
          var visible = false;
          while (next && !next.querySelector("code")) {
            if (next.style.display !== "none") { visible = true; break; }
            next = next.nextElementSibling;
          }
          r.style.display = (!q || visible) ? "" : "none";
        });
      }, 80);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
