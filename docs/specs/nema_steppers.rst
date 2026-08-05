:icon: material/wrench-outline

.. _spec-nema_steppers:

nema steppers
=============

.. raw:: html

    <p class="spec-lede">Models of NEMA-standard stepper motors — body, plinth, shaft and mounting holes — plus the bolt-pattern mask to difference out of a mounting plate.</p>

.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">nema_stepper_motor(17)</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster"><svg viewBox="0 0 460 240" role="img" aria-label="Mounting-face view of a NEMA stepper motor: square body, four corner bolt holes, central shaft." xmlns="http://www.w3.org/2000/svg"><rect x="138" y="24" width="184" height="184" rx="14" fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.8"/><rect x="168" y="54" width="124" height="124" fill="none" stroke="var(--accent)" stroke-width="1" stroke-dasharray="5 5" opacity="0.7"/><line x1="168" y1="224" x2="292" y2="224" stroke="var(--ink-faint)" stroke-width="1"/><text x="230" y="238" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">bolt spacing 31 mm · NEMA 17</text><circle cx="230" cy="116" r="34" fill="var(--panel)" stroke="var(--ink-dim)" stroke-width="1.6"/><circle cx="230" cy="116" r="14" fill="color-mix(in srgb,var(--accent) 22%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.6"/><circle cx="168" cy="54" r="7" fill="var(--ground)" stroke="var(--accent)" stroke-width="1.5"/><circle cx="168" cy="178" r="7" fill="var(--ground)" stroke="var(--accent)" stroke-width="1.5"/><circle cx="292" cy="54" r="7" fill="var(--ground)" stroke="var(--accent)" stroke-width="1.5"/><circle cx="292" cy="178" r="7" fill="var(--ground)" stroke="var(--accent)" stroke-width="1.5"/></svg></div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill">watertight</span>
        </div>
        <p>NEMA 17 is the 3-D-printer classic: a 42.3 mm body on a 31 mm bolt circle with a 5 mm shaft. Eight sizes (NEMA 6 → 42) are tabulated as a <span class="mono">NemaSpec</span>.</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags"><button class="spec-tag" type="button">NEMA 17</button> <button class="spec-tag" type="button">NEMA 23</button> <button class="spec-tag" type="button">NEMA 8</button> <button class="spec-tag" type="button">mount mask</button></div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">290</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">43,858.4</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">42×42×44</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; NemaSteppers.<span class="k">nema_stepper_motor</span>(17)</div>
        </div>

        <div class="spec-tests">13 tests</div>
      </div>
    </div>

.. raw:: html

    <script id="spec-data" type="application/json">[{"id": "17", "label": "NEMA 17", "uri": "_stl/nema_steppers-17.stl", "code": "NemaSteppers.<span class=\"k\">nema_stepper_motor</span>(17)", "part": "nema_stepper_motor(17)", "tris": 290, "vol": "43,858.4", "bbox": "42\u00d742\u00d744", "wt": true}, {"id": "23", "label": "NEMA 23", "uri": "_stl/nema_steppers-23.stl", "code": "NemaSteppers.<span class=\"k\">nema_stepper_motor</span>(23)", "part": "nema_stepper_motor(23)", "tris": 388, "vol": "79,815.8", "bbox": "57\u00d757\u00d744", "wt": true}, {"id": "8", "label": "NEMA 8", "uri": "_stl/nema_steppers-8.stl", "code": "NemaSteppers.<span class=\"k\">nema_stepper_motor</span>(8)", "part": "nema_stepper_motor(8)", "tris": 262, "vol": "10,312.0", "bbox": "20\u00d720\u00d744", "wt": true}, {"id": "mask", "label": "mount mask", "uri": "_stl/nema_steppers-mask.stl", "code": "NemaSteppers.<span class=\"k\">nema_mount_mask</span>(17)", "part": "nema_mount_mask(17)", "tris": 506, "vol": "2,843.8", "bbox": "34\u00d739\u00d75", "wt": true}]</script>
    <script>
    function copySpecCode(btn) {var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){btn.title='Copy to clipboard';btn.classList.remove('copied');},1500);});}
    </script>
