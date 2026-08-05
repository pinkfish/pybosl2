:icon: material/wrench-outline

.. _spec-joiners:

joiners
=======

.. raw:: html

    <p class="spec-lede">Shapes that connect two separately-printed parts: a tapered-or-straight dovetail joint — male tenon or female socket — and a press-and-click snap pin.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">dovetail("male", width=15, height=8, slide=30)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Section of a dovetail joint: a flared male tenon seated in a female socket." xmlns="http://www.w3.org/2000/svg"><path d="M 46,52 H 414 V 210 H 46 Z M 136,60 L 324,60 L 295,174 L 165,174 Z" fill="url(#h)" fill-rule="evenodd" stroke="var(--ink-dim)" stroke-width="1.5"/><defs><pattern id="h" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse"><line x1="0" y1="0" x2="0" y2="7" stroke="var(--line)" stroke-width="1.4"/></pattern></defs><path d="M 171,168 L 289,168 L 318,66 L 142,66 Z" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink)" stroke-width="1.6"/><line x1="289" y1="168" x2="318" y2="66" stroke="var(--accent)" stroke-width="1.4"/><text x="230" y="198" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">male tenon · female socket · slope 1:6</text></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>The dovetail flares to <span class="mono">w + 2·h/slope</span> at the top so it resists pulling apart; a taper lets a long joint slide home and wedge tight. The female is the same shape grown by <b>slop</b> for a press fit.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">male dovetail</button> <button class="spec-tag" type="button">female socket</button> <button class="spec-tag" type="button">tapered</button> <button class="spec-tag" type="button">snap pin</button> <button class="spec-tag" type="button">pin socket</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">12</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">3,920.0</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">18×30×8</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; Joiners.<span class="k">dovetail</span>("male", width=15, height=8, slide=30)</div>
        </div>

        <div class="spec-tests">8 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "male", "label": "male dovetail", "uri": "_stl/joiners-male.stl", "code": "Joiners.<span class=\"k\">dovetail</span>(\"male\", width=15, height=8, slide=30)", "part": "dovetail(\"male\", width=15, height=8, slide=30)", "tris": 12, "vol": "3,920.0", "bbox": "18\u00d730\u00d78", "wt": true}, {"id": "female", "label": "female socket", "uri": "_stl/joiners-female.stl", "code": "Joiners.<span class=\"k\">dovetail</span>(\"female\", width=15, height=8, slide=30)", "part": "dovetail(\"female\", width=15, height=8, slide=30)", "tris": 12, "vol": "3,920.0", "bbox": "18\u00d730\u00d78", "wt": true}, {"id": "taper", "label": "tapered", "uri": "_stl/joiners-taper.stl", "code": "Joiners.<span class=\"k\">dovetail</span>(\"male\", width=15, height=8, slide=30, taper=4)", "part": "dovetail(\"male\", width=15, height=8, slide=30, taper=4)", "tris": 20, "vol": "3,419.1", "bbox": "18\u00d730\u00d78", "wt": true}, {"id": "snap-pin", "label": "snap pin", "uri": "_stl/joiners-snap-pin.stl", "code": "Joiners.<span class=\"k\">snap_pin</span>()", "part": "snap_pin()", "tris": 228, "vol": "173.5", "bbox": "6\u00d76\u00d714", "wt": true}, {"id": "socket", "label": "pin socket", "uri": "_stl/joiners-socket.stl", "code": "Joiners.<span class=\"k\">snap_pin_socket</span>()", "part": "snap_pin_socket()", "tris": 112, "vol": "301.2", "bbox": "6\u00d77\u00d713", "wt": true}]</script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
