/**
 * Sidebar layout: sticky header + collapsible groups.
 */
(function () {
  function init() {
    var sidebar = document.querySelector("div.sphinxsidebar");
    if (!sidebar) return;

    var wrapper = sidebar.querySelector("div.sphinxsidebarwrapper");
    if (!wrapper) return;

    // ---- inject sticky header ----
    var header = document.createElement("div");
    header.className = "sidebar-sticky";
    header.innerHTML =
      '<div class="sidebar-brand">' +
        '<a class="sidebar-logo" href="index.html">pybosl2</a>' +
        '<div class="sidebar-icons">' +
          '<a href="genindex.html" title="API Index" class="sidebar-icon-link">' +
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
              '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>' +
            '</svg>' +
          '</a>' +
          '<a href="specs/index.html" title="Spec Sheets" class="sidebar-icon-link">' +
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
              '<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>' +
            '</svg>' +
          '</a>' +
        '</div>' +
      '</div>';
    wrapper.insertBefore(header, wrapper.firstChild);

    // ---- move search box into the sticky header ----
    var searchForm = sidebar.querySelector("form.search");
    if (searchForm && header && !header.contains(searchForm)) {
      header.appendChild(searchForm);
    }

    // ---- hide the old logo (Alabaster puts h1.logo) ----
    var oldLogo = sidebar.querySelector("h1.logo");
    if (oldLogo) oldLogo.style.display = "none";

    // ---- collapsible toctree groups ----
    var navList = sidebar.querySelector("div.sphinxsidebarwrapper ul");
    if (navList) {
      var items = navList.querySelectorAll("li");
      items.forEach(function (li) {
        var nested = li.querySelector("ul");
        if (!nested) return;
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
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
