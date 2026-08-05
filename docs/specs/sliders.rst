:icon: material/wrench-outline

.. _spec-sliders:

sliders
=======

.. raw:: html

    <p class="spec-lede">V-groove sliders and rails — smooth low-friction linear guides for 3-D-printed frames, with configurable slop and wall thickness.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">slider(l=30, base=10, wall=4, slop=0.2)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="V-groove slider and rail schematic" xmlns="http://www.w3.org/2000/svg"><rect width="460" height="240" fill="var(--ground)"/><path d="M60,140 L160,70 M60,160 L160,90 M60,100 L160,30 M130,60 L280,60 L280,140 Z" fill="none" stroke="var(--ink-dim)" stroke-width="2" stroke-linecap="round"/></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>The V-groove profile is cut by the same polygon BOSL2 uses. <b>slop</b> controls the clearance between slider and rail; the rail is 90° V-grooves in a rectangular bar.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">slider</button> <button class="spec-tag" type="button">rail</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">100</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">8,307.2</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">30×18×20</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; Sliders.<span class="k">slider</span>(l=30, base=10, wall=4, slop=0.2)</div>
        </div>

        <div class="spec-tests">5 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "slider", "label": "slider", "uri": "_stl/sliders-slider.stl", "code": "Sliders.<span class=\"k\">slider</span>(l=30, base=10, wall=4, slop=0.2)", "part": "slider(l=30, base=10, wall=4, slop=0.2)", "tris": 100, "vol": "8,307.2", "bbox": "30\u00d718\u00d720", "wt": true}, {"id": "rail", "label": "rail", "uri": "_stl/sliders-rail.stl", "code": "Sliders.<span class=\"k\">rail</span>(l=100, w=10, h=10)", "part": "rail(l=100, w=10, h=10)", "tris": 52, "vol": "6,861.2", "bbox": "10\u00d7100\u00d710", "wt": true}]</script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
