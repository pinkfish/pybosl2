:icon: material/wrench-outline

.. _spec-screw_drive:

screw drive
===========

.. raw:: html

    <p class="spec-lede">Driver-recess masks for Phillips, hex, Torx, and Robertson — subtract from a screw head to make the drive recess, with exact dimensional tables from ISO/ANSI standards.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">phillips_mask(size="#2", l=10)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Screw drive recess schematic" xmlns="http://www.w3.org/2000/svg"><rect width="460" height="240" fill="var(--ground)"/><path d="M100,100 L120,40 L140,40 L160,100 M130,40 L130,200 M80,160 L180,160 M60,140 L200,140 M70,120 L190,120" fill="none" stroke="var(--ink-dim)" stroke-width="2" stroke-linecap="round"/></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>Every ``*_mask`` is built bottom-on-the-XY-plane. The dimensional helpers — <b>torx_info</b>, <b>phillips_depth</b>, etc. — return the same numbers as BOSL2.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">Phillips #2</button> <button class="spec-tag" type="button">hex 3 mm</button> <button class="spec-tag" type="button">Torx T30</button> <button class="spec-tag" type="button">Robertson #2</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">176</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">29.3</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">6×6×4</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; ScrewDrive.<span class="k">phillips_mask</span>(size="#2", l=10)</div>
        </div>

        <div class="spec-tests">19 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "phillips", "label": "Phillips #2", "uri": "_stl/screw_drive-phillips.stl", "code": "ScrewDrive.<span class=\"k\">phillips_mask</span>(size=\"#2\", l=10)", "part": "phillips_mask(size=\"#2\", l=10)", "tris": 176, "vol": "29.3", "bbox": "6\u00d76\u00d74", "wt": true}, {"id": "hex", "label": "hex 3 mm", "uri": "_stl/screw_drive-hex.stl", "code": "ScrewDrive.<span class=\"k\">hex_mask</span>(size=3, l=10)", "part": "hex_mask(size=3, l=10)", "tris": 20, "vol": "80.9", "bbox": "4\u00d73\u00d710", "wt": true}, {"id": "torx", "label": "Torx T30", "uri": "_stl/screw_drive-torx.stl", "code": "ScrewDrive.<span class=\"k\">torx_mask</span>(size=30, l=10)", "part": "torx_mask(size=30, l=10)", "tris": 188, "vol": "176.3", "bbox": "6\u00d75\u00d710", "wt": true}, {"id": "robertson", "label": "Robertson #2", "uri": "_stl/screw_drive-robertson.stl", "code": "ScrewDrive.<span class=\"k\">robertson_mask</span>(size=\"#2\", l=10)", "part": "robertson_mask(size=\"#2\", l=10)", "tris": 74, "vol": "93.4", "bbox": "4\u00d74\u00d710", "wt": true}]</script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
