:icon: material/wrench-outline

.. _spec-ball_bearings:

ball bearings
=============

.. raw:: html

    <p class="spec-lede">Standard cartridge models from a trade-size name — shielded (ZZ) or open, with the balls modelled rolling in the race.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">ball_bearing("608")</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Schematic of an open ball bearing with 9 balls in the race." xmlns="http://www.w3.org/2000/svg"><circle cx="230" cy="118" r="96" fill="none" stroke="var(--ink-dim)" stroke-width="1.8"/><circle cx="230" cy="118" r="88" fill="none" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="230" cy="118" r="40" fill="var(--ground)" stroke="var(--ink-dim)" stroke-width="1.8"/><circle cx="230" cy="118" r="48" fill="none" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="230" cy="118" r="66" fill="none" stroke="var(--accent)" stroke-width="1" stroke-dasharray="5 5"/><circle cx="296.0" cy="118.0" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="280.6" cy="160.4" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="241.5" cy="183.0" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="197.0" cy="175.2" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="168.0" cy="140.6" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="168.0" cy="95.4" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="197.0" cy="60.8" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="241.5" cy="53.0" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><circle cx="280.6" cy="75.6" r="11.8" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/><text x="230" y="234" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">9 balls · pitch &Oslash;</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>The open 608 skate bearing: inner and outer races, a toroidal ball groove, and 9 balls spaced around it — one watertight assembly. 136 trade sizes are tabulated.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">608</button> <button class="spec-tag" type="button">6902ZZ</button> <button class="spec-tag" type="button">R8</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">2,328</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">1,640.6</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">22×22×7</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; BallBearings.ball_bearing("608")</div>
        </div>

        <div class="spec-tests">10 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "608", "label": "608", "uri": "_stl/ball_bearings-608.stl", "code": "BallBearings.ball_bearing(\"608\")", "part": "ball_bearing(\"608\")", "tris": 2328, "vol": "1,640.6", "bbox": "22\u00d722\u00d77", "wt": true}, {"id": "6902zz", "label": "6902ZZ", "uri": "_stl/ball_bearings-6902zz.stl", "code": "BallBearings.ball_bearing(\"6902ZZ\")", "part": "ball_bearing(\"6902ZZ\")", "tris": 696, "vol": "2,862.2", "bbox": "28\u00d728\u00d77", "wt": true}, {"id": "r8", "label": "R8", "uri": "_stl/ball_bearings-r8.stl", "code": "BallBearings.ball_bearing(\"R8\")", "part": "ball_bearing(\"R8\")", "tris": 2978, "vol": "2,400.7", "bbox": "29\u00d728\u00d76", "wt": false}]</script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
