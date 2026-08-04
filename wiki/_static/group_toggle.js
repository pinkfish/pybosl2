/**
 * Collapsible sidebar toctree groups.
 *
 * Look for sidebar <li> entries that contain nested <ul> children
 * (the shapes2d / shapes3d group pages with their own toctrees) and
 * add a toggle to collapse / expand them.
 */
(function () {
  function init() {
    var sidebar = document.querySelector("div.sphinxsidebar ul");
    if (!sidebar) return;

    var items = sidebar.querySelectorAll("li");
    items.forEach(function (li) {
      var nested = li.querySelector("ul");
      if (!nested) return;

      // Add a toggle button before the link text
      var link = li.querySelector("a.reference.internal");
      if (!link) return;

      var toggle = document.createElement("span");
      toggle.className = "ps-group-toggle";
      toggle.textContent = "\u25bc";
      toggle.style.cssText =
        "cursor:pointer;display:inline-block;width:14px;font-size:10px;" +
        "margin-right:2px;vertical-align:middle;user-select:none;";

      link.parentNode.insertBefore(toggle, link);

      var collapsed = false;
      toggle.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        collapsed = !collapsed;
        nested.style.display = collapsed ? "none" : "";
        toggle.textContent = collapsed ? "\u25b6" : "\u25bc";
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
