:icon: material/wrench-outline

.. _spec-walls:

walls
=====

.. raw:: html

    <p class="spec-lede">FDM-optimised walls that use less plastic and print without support: a cross-braced sparse wall, a corrugated wall, thick-edged thinning walls and triangles, and struts.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">sparse_wall(height=50, length=100, thick=4)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Plan of a sparse cross-braced wall: a solid frame filled with diagonal X-braces." xmlns="http://www.w3.org/2000/svg"><rect x="34" y="24" width="392" height="168" fill="var(--panel-2)"/><rect x="47" y="37" width="366" height="142" fill="var(--ground)"/><line x1="47.0" y1="37" x2="108.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="108.0" y1="37" x2="47.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="108.0" y1="37" x2="169.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="169.0" y1="37" x2="108.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="169.0" y1="37" x2="230.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="230.0" y1="37" x2="169.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="230.0" y1="37" x2="291.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="291.0" y1="37" x2="230.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="291.0" y1="37" x2="352.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="352.0" y1="37" x2="291.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="352.0" y1="37" x2="413.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><line x1="413.0" y1="37" x2="352.0" y2="179" stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"/><rect x="34" y="24" width="392" height="168" fill="none" stroke="var(--ink-dim)" stroke-width="1.8"/><rect x="47" y="37" width="366" height="142" fill="none" stroke="var(--ink-dim)" stroke-width="1.3"/><text x="230" y="218" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">sparse wall · X-braced · support-free</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>The diagonal braces are held under <b>maxang</b> from vertical so every overhang prints clean; the thinning wall is BOSL2's exact 24-point polyhedron, transcribed and closed watertight.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">sparse</button> <button class="spec-tag" type="button">corrugated</button> <button class="spec-tag" type="button">thinning wall</button> <button class="spec-tag" type="button">thinning triangle</button> <button class="spec-tag" type="button">narrowing strut</button> <button class="spec-tag" type="button">sparse cuboid</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">280</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">12,007.0</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">4×101×50</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; Walls.<span class="k">sparse_wall</span>(height=50, length=100, thick=4)</div>
        </div>
        <div class="spec-proof"><div class="spec-proof-big">40%</div><div class="spec-proof-txt"><b>The sparse lattice fills its 4×100×50 envelope with 12,007 mm&sup3;</b> — 40% less plastic than the 20,000 mm&sup3; solid wall, and it needs no support.</div></div>
        <div class="spec-tests">12 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "sparse", "label": "sparse", "uri": "_stl/walls-sparse.stl", "code": "Walls.<span class=\"k\">sparse_wall</span>(height=50, length=100, thick=4)", "part": "sparse_wall(height=50, length=100, thick=4)", "tris": 280, "vol": "12,007.0", "bbox": "4\u00d7101\u00d750", "wt": true}, {"id": "corrugated", "label": "corrugated", "uri": "_stl/walls-corrugated.stl", "code": "Walls.<span class=\"k\">corrugated_wall</span>(height=50, length=100, thick=5)", "part": "corrugated_wall(height=50, length=100, thick=5)", "tris": 476, "vol": "14,200.0", "bbox": "5\u00d7100\u00d750", "wt": true}, {"id": "thinning-wall", "label": "thinning wall", "uri": "_stl/walls-thinning-wall.stl", "code": "Walls.<span class=\"k\">thinning_wall</span>(height=50, length=80, thick=4)", "part": "thinning_wall(height=50, length=80, thick=4)", "tris": 44, "vol": "9,422.6", "bbox": "4\u00d780\u00d750", "wt": true}, {"id": "thinning-triangle", "label": "thinning triangle", "uri": "_stl/walls-thinning-triangle.stl", "code": "Walls.<span class=\"k\">thinning_triangle</span>(height=50, length=80, thick=4, center=True)", "part": "thinning_triangle(height=50, length=80, thick=4, center=True)", "tris": 74, "vol": "7,032.8", "bbox": "4\u00d780\u00d750", "wt": true}, {"id": "strut", "label": "narrowing strut", "uri": "_stl/walls-strut.stl", "code": "Walls.<span class=\"k\">narrowing_strut</span>(w=10, length=80, wall=5, angle=30)", "part": "narrowing_strut(w=10, length=80, wall=5, angle=30)", "tris": 16, "vol": "7,464.1", "bbox": "10\u00d780\u00d714", "wt": true}, {"id": "sparse-cuboid", "label": "sparse cuboid", "uri": "_stl/walls-sparse-cuboid.stl", "code": "Walls.<span class=\"k\">sparse_cuboid</span>([20, 40, 30], strut=2)", "part": "sparse_cuboid([20, 40, 30], strut=2)", "tris": 160, "vol": "14,673.8", "bbox": "20\u00d740\u00d730", "wt": true}]</script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
