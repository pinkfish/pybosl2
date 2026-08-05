:icon: material/wrench-outline

.. _spec-bottlecaps:

bottlecaps
==========

.. raw:: html

    <p class="spec-lede">Standard soda-bottle necks and caps — PCO 1810 and 1881 thread finishes — a threaded neck to graft onto a bottle body and its matching cap.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">pco1810_neck(fa=6)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Bottle neck and cap schematic" xmlns="http://www.w3.org/2000/svg"><rect width="460" height="240" fill="var(--ground)"/><path d="M120,50 L120,190 M140,50 L140,190 M160,50 L160,190 M100,80 L180,80 M100,160 L180,160 M115,80 Q115,30 140,20 Q165,30 165,80" fill="none" stroke="var(--ink-dim)" stroke-width="2" stroke-linecap="round"/></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>The neck profile (inner bore, support ring, tamper-ring channel and sealing lip) is a turtle path revolved with <b>rotate_extrude</b>. Threads are <b>thread_helix</b> ridges with the two thread breaks cut by prismoids.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">PCO 1810 neck</button> <button class="spec-tag" type="button">PCO 1810 cap</button> <button class="spec-tag" type="button">PCO 1881 neck</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">4,130</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">4,358.5</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">33×33×26</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; BottleCaps.pco1810_neck(fa=6)</div>
        </div>

        <div class="spec-tests">7 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "pco1810-neck", "label": "PCO 1810 neck", "uri": "_stl/bottlecaps-pco1810-neck.stl", "code": "BottleCaps.pco1810_neck(fa=6)", "part": "pco1810_neck(fa=6)", "tris": 4130, "vol": "4,358.5", "bbox": "33\u00d733\u00d726", "wt": true}, {"id": "pco1810-cap", "label": "PCO 1810 cap", "uri": "_stl/bottlecaps-pco1810-cap.stl", "code": "BottleCaps.pco1810_cap(fa=6)", "part": "pco1810_cap(fa=6)", "tris": 932, "vol": "3,952.8", "bbox": "33\u00d733\u00d716", "wt": true}, {"id": "pco1881-neck", "label": "PCO 1881 neck", "uri": "_stl/bottlecaps-pco1881-neck.stl", "code": "BottleCaps.pco1881_neck(fa=6)", "part": "pco1881_neck(fa=6)", "tris": 3806, "vol": "3,258.7", "bbox": "33\u00d733\u00d722", "wt": true}]</script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
