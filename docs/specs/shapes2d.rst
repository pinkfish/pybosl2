:icon: material/wrench-outline

.. _spec-shapes2d:

shapes2d
========

.. raw:: html

    <p class="spec-lede">BOSL2 2-D primitives: circle, square, rect, trapezoid, star, ring, pie slice, squircle, keyhole, and more — anchored Path2D shapes that feed directly into extrusions.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">circle(radius=15).linear_extrude(height=2)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="2-D primitives schematic" xmlns="http://www.w3.org/2000/svg"><rect width="460" height="240" fill="var(--ground)"/><path d="M70,70 L210,70 L210,190 L70,190 Z M110,40 L170,40 L170,220 L110,220 Z M70,130 L210,130 M140,70 L140,190" fill="none" stroke="var(--ink-dim)" stroke-width="2" stroke-linecap="round"/></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>Every shape returns a <b>Path2D</b> that chains into 2-D operations: ``.offset()``, ``.round_corners()``, ``.polygon()``, ``.linear_extrude()``. Anchors and rounding work consistently.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">circle</button> <button class="spec-tag" type="button">square</button> <button class="spec-tag" type="button">rectangle</button> <button class="spec-tag" type="button">trapezoid</button> <button class="spec-tag" type="button">star</button> <button class="spec-tag" type="button">ring</button> <button class="spec-tag" type="button">pie slice</button> <button class="spec-tag" type="button">squircle</button> <button class="spec-tag" type="button">keyhole</button> <button class="spec-tag" type="button">rounded square</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">116</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">1,403.4</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">30×30×2</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; pybosl2.<span class="k">circle</span>(radius=15).linear_extrude(height=2)</div>
        </div>

        <div class="spec-tests">149 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "circle", "label": "circle", "uri": "_stl/shapes2d-circle.stl", "code": "pybosl2.<span class=\"k\">circle</span>(radius=15).linear_extrude(height=2)", "part": "circle(radius=15).linear_extrude(height=2)", "tris": 116, "vol": "1,403.4", "bbox": "30\u00d730\u00d72", "wt": true}, {"id": "square", "label": "square", "uri": "_stl/shapes2d-square.stl", "code": "pybosl2.<span class=\"k\">square</span>(size=30).linear_extrude(height=2)", "part": "square(size=30).linear_extrude(height=2)", "tris": 12, "vol": "1,800.0", "bbox": "30\u00d730\u00d72", "wt": true}, {"id": "rect", "label": "rectangle", "uri": "_stl/shapes2d-rect.stl", "code": "pybosl2.<span class=\"k\">rect</span>(size=[30, 20], rounding=5).linear_extrude(height=2)", "part": "rect(size=[30, 20], rounding=5).linear_extrude(height=2)", "tris": 76, "vol": "1,153.1", "bbox": "30\u00d720\u00d72", "wt": true}, {"id": "trapezoid", "label": "trapezoid", "uri": "_stl/shapes2d-trapezoid.stl", "code": "pybosl2.<span class=\"k\">trapezoid</span>(height=30, width1=40, width2=20).linear_extrude(height=2)", "part": "trapezoid(height=30, width1=40, width2=20).linear_extrude(height=2)", "tris": 12, "vol": "1,800.0", "bbox": "40\u00d730\u00d72", "wt": true}, {"id": "star", "label": "star", "uri": "_stl/shapes2d-star.stl", "code": "pybosl2.<span class=\"k\">star</span>(tips=5, radius=25, inner_radius=10).linear_extrude(height=2)", "part": "star(tips=5, radius=25, inner_radius=10).linear_extrude(height=2)", "tris": 36, "vol": "1,469.5", "bbox": "45\u00d748\u00d72", "wt": true}, {"id": "ring", "label": "ring", "uri": "_stl/shapes2d-ring.stl", "code": "pybosl2.<span class=\"k\">ring</span>(radius=18, ring_width=6).linear_extrude(height=2)", "part": "ring(radius=18, ring_width=6).linear_extrude(height=2)", "tris": 240, "vol": "1,571.8", "bbox": "48\u00d748\u00d72", "wt": true}, {"id": "pie-slice", "label": "pie slice", "uri": "_stl/shapes2d-pie-slice.stl", "code": "pybosl2.<span class=\"k\">pie_slice</span>(radius=20, angle=120, height=5)", "part": "pie_slice(radius=20, angle=120, height=5)", "tris": 64, "vol": "2,078.9", "bbox": "30\u00d720\u00d75", "wt": true}, {"id": "squircle", "label": "squircle", "uri": "_stl/shapes2d-squircle.stl", "code": "pybosl2.<span class=\"k\">squircle</span>(30, squareness=0.6).linear_extrude(height=2)", "part": "squircle(30, squareness=0.6).linear_extrude(height=2)", "tris": 124, "vol": "1,128.7", "bbox": "30\u00d730\u00d72", "wt": false}, {"id": "keyhole", "label": "keyhole", "uri": "_stl/shapes2d-keyhole.stl", "code": "pybosl2.<span class=\"k\">keyhole</span>(length=25, radius1=4, radius2=9).linear_extrude(height=2)", "part": "keyhole(length=25, radius1=4, radius2=9).linear_extrude(height=2)", "tris": 136, "vol": "810.6", "bbox": "18\u00d738\u00d72", "wt": true}, {"id": "rounded-square", "label": "rounded square", "uri": "_stl/shapes2d-rounded-square.stl", "code": "pybosl2.<span class=\"k\">rect</span>(size=[30, 30], rounding=8).linear_extrude(height=2)", "part": "rect(size=[30, 30], rounding=8).linear_extrude(height=2)", "tris": 124, "vol": "1,686.8", "bbox": "30\u00d730\u00d72", "wt": true}]</script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
