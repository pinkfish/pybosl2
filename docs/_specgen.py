# Copyright (c) 2026, pinkfish
#
# Licensed under the BSD 2-Clause License. See the LICENSE file in the project
# root for the full license text.
# SPDX-License-Identifier: BSD-2-Clause

# LibFile: docs/_specgen.py
#    Generates the visual "spec sheet" pages for the docs: a gallery landing page plus one page per
#    featured part module, each with a procedurally-drawn technical schematic and the REAL metrics of
#    a part rendered through the PythonSCAD app (triangles / volume / bbox / watertightness). Output
#    goes to docs/_extra/specs/, which conf.py's html_extra_path copies to wiki/specs/ on build.
#
#    Re-run after changing the render metrics:  python3 docs/_specgen.py
#
# FileGroup: bosl2

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "_extra" / "specs"
STL_DIR = OUT / "_stl"

# Rendering is optional: with the PythonSCAD app present we render each variant to an STL and measure
# it; without it, we reuse the STLs and metrics already cached on disk (_stl/metrics.json).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from tests.render_stl import find_pythonscad_binary, render_object, stl_metrics
except Exception:  # pragma: no cover - only when the render harness can't be imported
    find_pythonscad_binary = lambda: None  # noqa: E731
    render_object = stl_metrics = None

# --- the design system (machinist / CAM spec-sheet identity), shared by every page ---
CSS = """
:root{
  --ground:#14171a; --panel:#1c2024; --panel-2:#21262b; --line:#2c3238;
  --ink:#e6ebef; --ink-dim:#8b959d; --ink-faint:#5b656d;
  --accent:#38bdf0; --pass:#57d9a3; --warn:#e6b45e;
  --mono:ui-monospace,"SF Mono","SFMono-Regular",Menlo,Consolas,"Liberation Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme: light){
  :root{
    --ground:#eaeef1; --panel:#ffffff; --panel-2:#f4f7f9; --line:#d2dade;
    --ink:#171c21; --ink-dim:#586269; --ink-faint:#8b959c;
    --accent:#0d7ba6; --pass:#158a5e; --warn:#9c6612;
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0; background:var(--ground); color:var(--ink); font-family:var(--sans);
  font-size:16px; line-height:1.6; -webkit-font-smoothing:antialiased;
  background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);
  background-size:40px 40px; background-position:-1px -1px;}
.wrap{max-width:1080px; margin:0 auto; padding:0 24px}
.mono{font-family:var(--mono)}
a{color:var(--accent); text-decoration:none}
a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:3px}
header.bar{border-bottom:1px solid var(--line); position:sticky; top:0; z-index:5;
  background:color-mix(in srgb,var(--ground) 84%,transparent); backdrop-filter:blur(6px)}
.bar .wrap{display:flex; align-items:baseline; gap:14px; padding:13px 24px; flex-wrap:wrap}
.logo{font-family:var(--mono); font-weight:700; font-size:18px}
.logo b{color:var(--accent)}
.bar .sep{color:var(--ink-faint)}
.bar .meta{font-family:var(--mono); font-size:12px; color:var(--ink-dim)}
.bar nav{margin-left:auto; display:flex; gap:16px; font-family:var(--mono); font-size:12.5px}
.bar nav a{color:var(--ink-dim)} .bar nav a:hover{color:var(--accent)}
.dot{display:inline-block; width:8px;height:8px;border-radius:50%;background:var(--pass);margin-right:6px;
  box-shadow:0 0 0 3px color-mix(in srgb,var(--pass) 22%,transparent)}
.eyebrow{font-family:var(--mono); font-size:11.5px; letter-spacing:.18em; text-transform:uppercase; color:var(--accent)}
h1{font-family:var(--mono); font-weight:700; letter-spacing:-.01em; line-height:1.12;
  font-size:clamp(28px,5vw,46px); margin:.35em 0 .3em; text-wrap:balance}
h1 .dim{color:var(--ink-dim)}
.lede{font-size:clamp(16px,1.9vw,18px); color:var(--ink-dim); max-width:62ch; margin:0}
section{padding:52px 0}
.hero{padding:44px 0 36px}
.spec{margin-top:30px; border:1px solid var(--line); border-radius:12px; overflow:hidden; background:var(--panel);
  display:grid; grid-template-columns:1.02fr .98fr}
@media (max-width:760px){.spec{grid-template-columns:1fr}}
.spec .draw{border-right:1px solid var(--line); padding:22px; display:flex; flex-direction:column; gap:12px;
  background:radial-gradient(circle at 1px 1px,var(--line) 1px,transparent 0) 0 0/22px 22px,var(--panel-2)}
@media (max-width:760px){.spec .draw{border-right:0; border-bottom:1px solid var(--line)}}
.spec .caption{font-family:var(--mono); font-size:11.5px; color:var(--ink-dim); display:flex; justify-content:space-between; gap:10px}
.spec svg{width:100%; height:auto; display:block}
.spec .info{padding:22px 24px; display:flex; flex-direction:column; gap:15px}
.spec h2{font-family:var(--mono); font-size:19px; margin:0}
.spec p{margin:0; color:var(--ink-dim); font-size:14.5px}
.pill{display:inline-flex; align-items:center; gap:6px; font-family:var(--mono); font-size:11px; letter-spacing:.04em;
  padding:2px 9px; border-radius:999px; border:1px solid; text-transform:uppercase}
.pill.pass{color:var(--pass); border-color:color-mix(in srgb,var(--pass) 45%,var(--line))}
.pill.pass::before{content:""; width:7px;height:7px;border-radius:50%;background:var(--pass)}
table.metrics{width:100%; border-collapse:collapse; font-family:var(--mono); font-size:13px; font-variant-numeric:tabular-nums}
table.metrics th{text-align:left; font-weight:400; color:var(--ink-dim); padding:7px 0; font-size:10.5px;
  text-transform:uppercase; letter-spacing:.12em; border-bottom:1px solid var(--line)}
table.metrics td{padding:9px 10px 9px 0; border-bottom:1px solid var(--line)}
table.metrics td.num{text-align:right; padding-right:0}
table.metrics tr:last-child td{border-bottom:0}
.proof{border:1px dashed color-mix(in srgb,var(--pass) 45%,var(--line)); border-radius:10px; padding:13px 15px;
  background:color-mix(in srgb,var(--pass) 8%,var(--panel)); display:flex; gap:13px; align-items:center}
.proof .big{font-family:var(--mono); font-weight:700; font-size:24px; color:var(--pass); font-variant-numeric:tabular-nums; line-height:1}
.proof .txt{font-size:13px; color:var(--ink-dim)} .proof .txt b{color:var(--ink)}
.code{font-family:var(--mono); font-size:12.5px; background:var(--panel-2); border:1px solid var(--line);
  border-radius:8px; padding:11px 13px; overflow-x:auto; color:var(--ink)}
.code .k{color:var(--accent)}
.tags{display:flex; flex-wrap:wrap; gap:6px}
.tag{font-family:var(--mono); font-size:10.5px; color:var(--ink-dim); border:1px solid var(--line); border-radius:5px; padding:2px 7px}
.tag.hot{color:var(--accent); border-color:color-mix(in srgb,var(--accent) 40%,var(--line))}
/* interactive variant viewer + clickable variant tags */
.spec .viewer{position:relative; width:100%; min-height:300px; border-radius:8px; overflow:hidden;
  display:flex; align-items:center; justify-content:center; background:var(--panel)}
.spec .viewer canvas{display:block}
.spec .viewer .poster{width:100%; display:block}
.spec .viewer .hint{position:absolute; left:10px; bottom:9px; font-family:var(--mono); font-size:10px;
  color:var(--ink-faint); pointer-events:none}
.taglabel{font-family:var(--mono); font-size:10px; text-transform:uppercase; letter-spacing:.14em; color:var(--ink-faint)}
button.tag{cursor:pointer; font:inherit; font-family:var(--mono); font-size:10.5px; color:var(--ink-dim);
  background:transparent; border:1px solid var(--line); border-radius:5px; padding:3px 9px; transition:color .13s,background .13s,border-color .13s}
button.tag:hover{color:var(--accent); border-color:color-mix(in srgb,var(--accent) 45%,var(--line))}
button.tag[aria-selected="true"]{color:var(--ground); background:var(--accent); border-color:var(--accent)}
@media (prefers-color-scheme:light){button.tag[aria-selected="true"]{color:#fff}}
.stats{display:flex; gap:28px; flex-wrap:wrap; font-family:var(--mono)}
.stats>div{display:flex; flex-direction:column; gap:2px}
.stats .v{font-size:19px; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.05}
.stats .l{font-size:10px; text-transform:uppercase; letter-spacing:.1em; color:var(--ink-dim)}
.sec-head{display:flex; align-items:baseline; gap:14px; border-bottom:1px solid var(--line); padding-bottom:12px; margin-bottom:24px}
.sec-head h3{font-family:var(--mono); font-size:15px; margin:0}
.sec-head .count{margin-left:auto; font-family:var(--mono); font-size:12px; color:var(--ink-dim)}
.grid{display:grid; grid-template-columns:repeat(2,1fr); gap:14px}
@media (max-width:720px){.grid{grid-template-columns:1fr}}
.card{border:1px solid var(--line); border-radius:10px; background:var(--panel); padding:16px 18px; display:flex;
  flex-direction:column; gap:9px; transition:border-color .15s, transform .15s; color:inherit}
a.card:hover{border-color:color-mix(in srgb,var(--accent) 55%,var(--line)); transform:translateY(-2px); text-decoration:none}
.card .top{display:flex; align-items:baseline; gap:10px}
.card .name{font-family:var(--mono); font-weight:700; font-size:15px}
.card .name .py{color:var(--ink-faint); font-weight:400}
.card .tests{margin-left:auto; font-family:var(--mono); font-size:11px; color:var(--pass)}
.card .arrow{margin-left:auto; font-family:var(--mono); font-size:11px; color:var(--accent)}
.card .desc{font-size:13.5px; color:var(--ink-dim); margin:0}
footer{border-top:1px solid var(--line); padding:32px 0 56px; color:var(--ink-dim); font-size:13px}
footer .wrap{display:flex; gap:22px; flex-wrap:wrap; align-items:baseline}
footer .r{margin-left:auto}
::selection{background:color-mix(in srgb,var(--accent) 35%,transparent)}
@media (prefers-reduced-motion:reduce){*{transition:none!important; scroll-behavior:auto}}
"""


# --------------------------------------------------------------------------
# procedural technical schematics (SVG), one per shape family
# --------------------------------------------------------------------------


def _svg(body, w=460, h=240, label=""):
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" xmlns="http://www.w3.org/2000/svg">{body}</svg>'


def gear_svg(teeth=20):
    cx, cy, rp = 230, 118, 86
    rt, rr, rb = rp * 1.13, rp * 0.9, rp * 0.3
    pts = []
    for i in range(teeth):
        a0 = i / teeth * 2 * math.pi
        step = 2 * math.pi / teeth
        for frac, rad in [(0.02, rr), (0.16, rt), (0.34, rt), (0.48, rr)]:
            a = a0 + frac * step
            pts.append(f"{cx + rad * math.cos(a):.1f},{cy + rad * math.sin(a):.1f}")
    path = "M" + " L".join(pts) + " Z"
    body = (
        f'<path d="{path}" fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.6"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{rp:.0f}" fill="none" stroke="var(--accent)" '
        f'stroke-width="1" stroke-dasharray="6 5" opacity="0.8"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{rb:.0f}" fill="var(--ground)" stroke="var(--accent)" stroke-width="1.5"/>'
        f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="var(--accent)"/>'
        f'<text x="{cx}" y="{cy + rp + 22:.0f}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">pitch circle · z={teeth}</text>'
    )
    return _svg(
        body,
        label=f"Schematic of a {teeth}-tooth involute gear with pitch circle and bore.",
    )


def bearing_svg(nballs=9):
    cx, cy = 230, 118
    ro, rmid, ri = 96, 66, 40
    br = (ro - ri) / 2 * 0.42
    dots = ""
    for i in range(nballs):
        a = i / nballs * 2 * math.pi
        x, y = cx + rmid * math.cos(a), cy + rmid * math.sin(a)
        dots += (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{br:.1f}" '
            f'fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/>'
        )
    body = (
        f'<circle cx="{cx}" cy="{cy}" r="{ro}" fill="none" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{ro - 8}" fill="none" stroke="var(--ink-dim)" stroke-width="1.2"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{ri}" fill="var(--ground)" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{ri + 8}" fill="none" stroke="var(--ink-dim)" stroke-width="1.2"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{rmid}" fill="none" stroke="var(--accent)" stroke-width="1" stroke-dasharray="5 5"/>'
        f"{dots}"
        f'<text x="{cx}" y="{cy + ro + 20}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">{nballs} balls · pitch &Oslash;</text>'
    )
    return _svg(
        body,
        label=f"Schematic of an open ball bearing with {nballs} balls in the race.",
    )


def linear_bearing_svg():
    # longitudinal cutaway: cylindrical shell, axial bore + shaft, two rows of balls
    cx, cy, L = 230, 118, 300
    od, idd = 116, 62
    x0, x1 = cx - L / 2, cx + L / 2
    yo0, yo1 = cy - od / 2, cy + od / 2
    yi0, yi1 = cy - idd / 2, cy + idd / 2
    dots = ""
    br = (yi0 - yo0) / 2 * 0.55
    ycen_t = (yo0 + yi0) / 2
    ycen_b = (yo1 + yi1) / 2
    for i in range(7):
        x = x0 + (i + 0.5) * L / 7
        for yc in (ycen_t, ycen_b):
            dots += (
                f'<circle cx="{x:.1f}" cy="{yc:.1f}" r="{br:.1f}" '
                f'fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/>'
            )
    body = (
        f'<rect x="{x0}" y="{yo0}" width="{L}" height="{od}" rx="8" fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<rect x="{x0 - 14}" y="{yi0}" width="{L + 28}" height="{idd}" fill="var(--ground)" stroke="var(--ink-dim)" stroke-width="1.4"/>'
        f'<line x1="{x0 - 26}" y1="{cy}" x2="{x1 + 26}" y2="{cy}" stroke="var(--accent)" stroke-width="1.2" stroke-dasharray="10 4 2 4"/>'
        f"{dots}"
        f'<text x="{cx}" y="{yo1 + 22}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">shell &amp; ball tracks · runs on a rod</text>'
    )
    return _svg(body, label="Longitudinal cutaway of a linear ball bearing running on a rod.")


def truss_svg(cubes=3):
    # isometric stack of `cubes` unit cubes along one axis
    s = 46
    ex, ey = s * 0.86, s * 0.5  # iso unit vectors
    ox, oy = 120, 70
    out = ""
    for c in range(cubes):
        bx = ox + c * ex
        by = oy + c * ey
        # 3 visible faces of a cube in iso
        _top = f"{bx},{by} {bx + ex},{by + ey} {bx + ex - ex},{by + ey + s * 0.0} "  # placeholder

        # define 8 corners
        def P(dx, dy, dz):
            return (bx + dx * ex + dy * (-ex) + dz * 0, by + dx * ey + dy * ey - dz * s)

        A = (bx, by)
        B = (bx + ex, by + ey)
        _C = (bx, by + s)
        D = (bx + ex, by + ey + s)
        E = (bx - ex, by + ey)
        F = (bx - ex, by + ey + s)
        # top rhombus A B E and the front faces
        out += (
            f'<polygon points="{A[0]:.0f},{A[1]:.0f} {B[0]:.0f},{B[1]:.0f} {A[0]:.0f},{A[1] + 0:.0f}" fill="none"/>'
            f'<polygon points="{A[0]:.0f},{A[1]:.0f} {B[0]:.0f},{B[1]:.0f} {(B[0] - ex):.0f},{(B[1]):.0f} {E[0]:.0f},{E[1]:.0f}" '
            f'fill="color-mix(in srgb,var(--accent) 16%,var(--panel-2))" stroke="var(--ink-dim)" stroke-width="1.3"/>'
            f'<polygon points="{E[0]:.0f},{E[1]:.0f} {(B[0] - ex):.0f},{B[1]:.0f} {D[0] - ex:.0f},{D[1]:.0f} {F[0]:.0f},{F[1]:.0f}" '
            f'fill="var(--panel)" stroke="var(--ink-dim)" stroke-width="1.3"/>'
            f'<polygon points="{(B[0] - ex):.0f},{B[1]:.0f} {B[0]:.0f},{B[1]:.0f} {D[0]:.0f},{D[1]:.0f} {D[0] - ex:.0f},{D[1]:.0f}" '
            f'fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.3"/>'
        )
    body = out + (
        f'<text x="230" y="225" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">{cubes} segments · bracing shown open</text>'
    )
    return _svg(body, label=f"Isometric schematic of a {cubes}-segment cube truss.")


def dovetail_svg():
    # section view: a male dovetail tenon (wide top) seated in a female socket
    cx = 230
    bw, tw = 118, 176  # base / top widths (flare)
    yb, yt = 168, 66  # base / top y
    male = f"M {cx - bw / 2:.0f},{yb} L {cx + bw / 2:.0f},{yb} L {cx + tw / 2:.0f},{yt} L {cx - tw / 2:.0f},{yt} Z"
    body = (
        # female block with the socket removed, drawn as a surrounding outline
        f'<path d="M 46,{yt - 14} H 414 V 210 H 46 Z '
        f"M {cx - tw / 2 - 6:.0f},{yt - 6} L {cx + tw / 2 + 6:.0f},{yt - 6} "
        f'L {cx + bw / 2 + 6:.0f},{yb + 6} L {cx - bw / 2 - 6:.0f},{yb + 6} Z" '
        f'fill="url(#h)" fill-rule="evenodd" stroke="var(--ink-dim)" stroke-width="1.5"/>'
        f'<defs><pattern id="h" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
        f'<line x1="0" y1="0" x2="0" y2="7" stroke="var(--line)" stroke-width="1.4"/></pattern></defs>'
        # the male tenon
        f'<path d="{male}" fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" '
        f'stroke="var(--ink)" stroke-width="1.6"/>'
        # slope callout
        f'<line x1="{cx + bw / 2:.0f}" y1="{yb}" x2="{cx + tw / 2:.0f}" y2="{yt}" stroke="var(--accent)" stroke-width="1.4"/>'
        f'<text x="{cx}" y="{yb + 30:.0f}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">male tenon · female socket · slope 1:6</text>'
    )
    return _svg(
        body,
        label="Section of a dovetail joint: a flared male tenon seated in a female socket.",
    )


def nema_svg():
    # mounting-face view of a NEMA motor: rounded-square body, 4 bolt holes, central plinth + shaft
    cx, cy = 230, 116
    hb = 92  # body half-width
    bs = 62  # bolt half-spacing
    body = (
        f'<rect x="{cx - hb}" y="{cy - hb}" width="{2 * hb}" height="{2 * hb}" rx="14" '
        f'fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.8"/>'
    )
    holes = ""
    for sx in (-1, 1):
        for sy in (-1, 1):
            holes += (
                f'<circle cx="{cx + sx * bs}" cy="{cy + sy * bs}" r="7" fill="var(--ground)" '
                f'stroke="var(--accent)" stroke-width="1.5"/>'
            )
    # bolt-circle guide + spacing dimension
    dim = (
        f'<rect x="{cx - bs}" y="{cy - bs}" width="{2 * bs}" height="{2 * bs}" fill="none" '
        f'stroke="var(--accent)" stroke-width="1" stroke-dasharray="5 5" opacity="0.7"/>'
        f'<line x1="{cx - bs}" y1="{cy + hb + 16}" x2="{cx + bs}" y2="{cy + hb + 16}" stroke="var(--ink-faint)" stroke-width="1"/>'
        f'<text x="{cx}" y="{cy + hb + 30}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">bolt spacing 31 mm · NEMA 17</text>'
    )
    plinth = (
        f'<circle cx="{cx}" cy="{cy}" r="34" fill="var(--panel)" stroke="var(--ink-dim)" stroke-width="1.6"/>'
        f'<circle cx="{cx}" cy="{cy}" r="14" fill="color-mix(in srgb,var(--accent) 22%,var(--panel))" '
        f'stroke="var(--ink-dim)" stroke-width="1.6"/>'
    )
    return _svg(
        body + dim + plinth + holes,
        label="Mounting-face view of a NEMA stepper motor: square body, four corner bolt holes, central shaft.",
    )


def hose_svg():
    # section of a modular ball-and-socket hose segment: socket cup (bottom), waist, ball (top), bore
    cx = 230
    body = (
        # bore centreline
        f'<line x1="{cx}" y1="30" x2="{cx}" y2="222" stroke="var(--accent)" stroke-width="1.2" stroke-dasharray="10 4 2 4"/>'
        # ball end (top)
        f'<circle cx="{cx}" cy="74" r="46" fill="color-mix(in srgb,var(--accent) 20%,var(--panel-2))" '
        f'stroke="var(--ink-dim)" stroke-width="1.6"/>'
        # waist / body
        f'<path d="M {cx - 34},96 L {cx + 34},96 L {cx + 40},150 L {cx - 40},150 Z" '
        f'fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.6"/>'
        # socket cup (bottom) opening down — thick ring drawn as two arcs
        f'<path d="M {cx - 58},150 A 58 58 0 0 0 {cx + 58},150 L {cx + 58},204 '
        f'A 58 58 0 0 1 {cx + 44},164 A 44 44 0 0 1 {cx - 44},164 A 58 58 0 0 1 {cx - 58},204 Z" '
        f'fill="url(#h)" stroke="var(--ink-dim)" stroke-width="1.6"/>'
        f'<defs><pattern id="h" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">'
        f'<line x1="0" y1="0" x2="0" y2="7" stroke="var(--line)" stroke-width="1.4"/></pattern></defs>'
        # bore hole through it all
        f'<rect x="{cx - 15}" y="30" width="30" height="150" fill="var(--ground)" stroke="var(--ink-dim)" '
        f'stroke-width="1.2" opacity="0.9"/>'
        f'<text x="{cx}" y="222" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">ball · waist · socket · through bore</text>'
    )
    return _svg(
        body,
        label="Section of a modular hose segment: a ball end, a waist, and a socket end with a through bore.",
    )


def hinge_svg(segs=5):
    body = """
    <defs><pattern id="h" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
      <line x1="0" y1="0" x2="0" y2="7" stroke="var(--line)" stroke-width="1.4"/></pattern></defs>
    <rect x="30" y="20" width="400" height="78" rx="4" fill="url(#h)" stroke="var(--ink-dim)" stroke-width="1.5"/>
    <rect x="30" y="142" width="400" height="78" rx="4" fill="none" stroke="var(--ink-dim)" stroke-width="1.5"/>
    <line x1="14" y1="120" x2="446" y2="120" stroke="var(--accent)" stroke-width="1.2" stroke-dasharray="10 4 2 4"/>
    <g stroke="var(--ink)" stroke-width="1.5">
      <rect x="46" y="98" width="70" height="44" rx="10" fill="color-mix(in srgb,var(--accent) 26%,var(--panel))"/>
      <rect x="122" y="98" width="66" height="44" rx="10" fill="var(--panel-2)"/>
      <rect x="196" y="98" width="70" height="44" rx="10" fill="color-mix(in srgb,var(--accent) 26%,var(--panel))"/>
      <rect x="272" y="98" width="66" height="44" rx="10" fill="var(--panel-2)"/>
      <rect x="344" y="98" width="70" height="44" rx="10" fill="color-mix(in srgb,var(--accent) 26%,var(--panel))"/></g>
    <g fill="var(--ground)" stroke="var(--accent)" stroke-width="1.4">
      <circle cx="81" cy="120" r="7"/><circle cx="155" cy="120" r="7"/><circle cx="231" cy="120" r="7"/>
      <circle cx="305" cy="120" r="7"/><circle cx="379" cy="120" r="7"/></g>
    <text x="230" y="232" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">length = 40 mm · segs=5</text>
    """
    return _svg(body, label="Plan view of a five-knuckle butt hinge.")


def poly_svg():
    # a real icosahedron: rotate the phi-based vertices, project, and paint the faces
    # back-to-front, shading each by depth so the solid reads in 3-D.
    phi = (1 + 5**0.5) / 2
    V = [
        (-1, phi, 0),
        (1, phi, 0),
        (-1, -phi, 0),
        (1, -phi, 0),
        (0, -1, phi),
        (0, 1, phi),
        (0, -1, -phi),
        (0, 1, -phi),
        (phi, 0, -1),
        (phi, 0, 1),
        (-phi, 0, -1),
        (-phi, 0, 1),
    ]
    F = [
        [0, 11, 5],
        [0, 5, 1],
        [0, 1, 7],
        [0, 7, 10],
        [0, 10, 11],
        [1, 5, 9],
        [5, 11, 4],
        [11, 10, 2],
        [10, 7, 6],
        [7, 1, 8],
        [3, 9, 4],
        [3, 4, 2],
        [3, 2, 6],
        [3, 6, 8],
        [3, 8, 9],
        [4, 9, 5],
        [2, 4, 11],
        [6, 2, 10],
        [8, 6, 7],
        [9, 8, 1],
    ]
    m = max(sum(c * c for c in v) ** 0.5 for v in V)
    ax, ay = math.radians(-22), math.radians(31)
    R = []
    for x, y, z in V:
        x, y, z = x / m, y / m, z / m
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        R.append((x, y, z))
    cx, cy, s = 230, 112, 92
    P = [(cx + s * p[0], cy - s * p[1]) for p in R]
    body = ""
    for i in sorted(range(len(F)), key=lambda i: sum(R[v][2] for v in F[i])):  # far first
        f = F[i]
        depth = sum(R[v][2] for v in f) / 3  # -1 (back) .. 1 (front)
        pct = int(14 + (depth + 1) / 2 * 30)
        pts = " ".join(f"{P[v][0]:.1f},{P[v][1]:.1f}" for v in f)
        body += (
            f'<polygon points="{pts}" fill="color-mix(in srgb,var(--accent) {pct}%,var(--panel))" '
            f'stroke="var(--ink-dim)" stroke-width="1.2" stroke-linejoin="round"/>'
        )
    body += (
        f'<text x="{cx}" y="{cy + 116}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">icosahedron · 12 v · 30 e · 20 f</text>'
    )
    return _svg(body, label="Isometric projection of a regular icosahedron, faces depth-shaded.")


def wall_svg():
    # plan of a sparse cross-braced wall: a solid frame hollowed out and filled with X-braces
    x0, y0, x1, y1 = 34, 24, 426, 192
    fw = 13
    ix0, iy0, ix1, iy1 = x0 + fw, y0 + fw, x1 - fw, y1 - fw
    cols = 6
    cw = (ix1 - ix0) / cols
    strut = 'stroke="color-mix(in srgb,var(--accent) 42%,var(--panel))" stroke-width="7" stroke-linecap="round"'
    braces = ""
    for i in range(cols):
        a, b = ix0 + i * cw, ix0 + (i + 1) * cw
        braces += (
            f'<line x1="{a:.1f}" y1="{iy0}" x2="{b:.1f}" y2="{iy1}" {strut}/>'
            f'<line x1="{b:.1f}" y1="{iy0}" x2="{a:.1f}" y2="{iy1}" {strut}/>'
        )
    body = (
        f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="var(--panel-2)"/>'
        f'<rect x="{ix0}" y="{iy0}" width="{ix1 - ix0}" height="{iy1 - iy0}" fill="var(--ground)"/>'
        f"{braces}"
        f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<rect x="{ix0}" y="{iy0}" width="{ix1 - ix0}" height="{iy1 - iy0}" fill="none" stroke="var(--ink-dim)" stroke-width="1.3"/>'
        f'<text x="230" y="{y1 + 26}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">sparse wall · X-braced · support-free</text>'
    )
    return _svg(
        body,
        label="Plan of a sparse cross-braced wall: a solid frame filled with diagonal X-braces.",
    )


def wire_svg(wires=13):
    # cross-section of a hex-packed wire bundle, coloured from the real 17-wire table
    palette = [
        [0.2, 0.2, 0.2],
        [1.0, 0.2, 0.2],
        [0.0, 0.8, 0.0],
        [1.0, 1.0, 0.2],
        [0.3, 0.3, 1.0],
        [1.0, 1.0, 1.0],
        [0.7, 0.5, 0.0],
        [0.5, 0.5, 0.5],
        [0.2, 0.9, 0.9],
        [0.8, 0.0, 0.8],
        [0.0, 0.6, 0.6],
        [1.0, 0.7, 0.7],
        [1.0, 0.5, 1.0],
        [0.5, 0.6, 0.0],
        [1.0, 0.7, 0.0],
        [0.7, 1.0, 0.5],
        [0.6, 0.6, 1.0],
    ]

    def ring(lev):
        if lev == 0:
            return [(0.0, 0.0)]
        cs = [(lev * math.cos(math.radians(60 * k)), lev * math.sin(math.radians(60 * k))) for k in range(6)]
        pts = []
        for k in range(6):
            x0, y0 = cs[k]
            x1, y1 = cs[(k + 1) % 6]
            for s in range(lev):
                t = s / lev
                pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        pts.reverse()
        return pts

    offs, lev = [], 0
    while len(offs) < wires:
        offs += ring(lev)
        lev += 1
    offs = offs[:wires]
    cx, cy, scale = 230, 116, 30
    dots = ""
    for i, (ox, oy) in enumerate(offs):
        r, g, b = palette[i % len(palette)]
        col = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
        dots += (
            f'<circle cx="{cx + ox * scale:.1f}" cy="{cy - oy * scale:.1f}" r="{scale * 0.47:.1f}" '
            f'fill="{col}" stroke="var(--ink-dim)" stroke-width="1.1"/>'
        )
    body = (
        dots + f'<text x="{cx}" y="{cy + 108}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">{wires} wires · hex-packed · 17-colour table</text>'
    )
    return _svg(
        body,
        label=f"Cross-section of a {wires}-wire bundle, hex-packed and colour-coded.",
    )


def hook_svg():
    # side elevation of a ring hook: a base flaring along the true tangent into the ring
    bx, hole_z, ro, ri = 30, 30, 25, 17
    cp = (0.0, hole_z)
    d = math.hypot(bx / 2, hole_z)
    u = ((bx / 2 - cp[0]) / d, (0 - cp[1]) / d)
    ang = math.acos(ro / d)
    tans = []
    for s in (1, -1):
        c, si = math.cos(s * ang), math.sin(s * ang)
        rot = (c * u[0] - si * u[1], si * u[0] + c * u[1])
        tans.append((cp[0] + ro * rot[0], cp[1] + ro * rot[1]))
    tx, tz = max(tans, key=lambda t: t[1])
    scale, cx, basey = 2.4, 230, 206

    def X(x):
        return cx + x * scale

    def Y(z):
        return basey - z * scale

    paddle = f"{X(-bx / 2):.1f},{Y(0):.1f} {X(bx / 2):.1f},{Y(0):.1f} {X(tx):.1f},{Y(tz):.1f} {X(-tx):.1f},{Y(tz):.1f}"
    body = (
        f'<circle cx="{X(0):.1f}" cy="{Y(hole_z):.1f}" r="{ro * scale:.1f}" fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<polygon points="{paddle}" fill="var(--panel-2)" stroke="none"/>'
        f'<polyline points="{X(-tx):.1f},{Y(tz):.1f} {X(-bx / 2):.1f},{Y(0):.1f} {X(bx / 2):.1f},{Y(0):.1f} {X(tx):.1f},{Y(tz):.1f}" '
        f'fill="none" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<circle cx="{X(0):.1f}" cy="{Y(hole_z):.1f}" r="{ri * scale:.1f}" fill="var(--ground)" stroke="var(--accent)" stroke-width="1.6"/>'
        # tangent construction + points
        f'<line x1="{X(bx / 2):.1f}" y1="{Y(0):.1f}" x2="{X(tx):.1f}" y2="{Y(tz):.1f}" stroke="var(--accent)" stroke-width="1" stroke-dasharray="4 4" opacity="0.8"/>'
        f'<line x1="{X(-bx / 2):.1f}" y1="{Y(0):.1f}" x2="{X(-tx):.1f}" y2="{Y(tz):.1f}" stroke="var(--accent)" stroke-width="1" stroke-dasharray="4 4" opacity="0.8"/>'
        f'<circle cx="{X(tx):.1f}" cy="{Y(tz):.1f}" r="2.6" fill="var(--accent)"/>'
        f'<circle cx="{X(-tx):.1f}" cy="{Y(tz):.1f}" r="2.6" fill="var(--accent)"/>'
        # hole_z dimension
        f'<line x1="{X(-bx / 2) - 14:.1f}" y1="{Y(0):.1f}" x2="{X(-bx / 2) - 14:.1f}" y2="{Y(hole_z):.1f}" stroke="var(--ink-dim)" stroke-width="1"/>'
        f'<text x="{X(-bx / 2) - 20:.1f}" y="{Y(hole_z / 2) + 3:.1f}" text-anchor="end" fill="var(--ink-dim)" font-family="var(--mono)" font-size="10">hole_z</text>'
        f'<circle cx="{X(0):.1f}" cy="{Y(hole_z):.1f}" r="2.2" fill="var(--accent)"/>'
        f'<text x="{X(0):.1f}" y="{basey + 18:.1f}" text-anchor="middle" fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">base flares along the ring tangent</text>'
    )
    return _svg(
        body,
        label="Side elevation of a ring hook: a base flaring along the tangent into a holed ring.",
    )


# --------------------------------------------------------------------------
# module registry: real render metrics + copy
# --------------------------------------------------------------------------

MODULES = {
    "gears": dict(
        title="gears",
        tests=52,
        svg=gear_svg(20),
        subtitle=(
            "Involute spur gears whose teeth are <em>rack-carved with a real undercut</em>, "
            "the way the current BOSL2 does it — plus helical, herringbone, rack, ring, bevel and worm."
        ),
        part="spur_gear(mod=5, teeth=20, thickness=8, helical=20)",
        code='Gears.<span class="k">spur_gear</span>(mod=5, teeth=20, thickness=8, helical=20, shaft_diam=6)',
        metrics=[
            ("helical spur · z=20", 5640, "69,617.1", "116×116×8"),
            ("undercut spur · z=8", 2300, "11,984.0", "55×55×8"),
        ],
        note=(
            "A 20-tooth helical gear meshes at <b>gear_dist()</b>; the 8-tooth gear picks up "
            '<b>profile_shift="auto"</b> so its flanks don\'t undercut. Both close watertight.'
        ),
        proof=None,
        tags=[
            "undercut",
            "profile_shift",
            "helical",
            "herringbone",
            "rack",
            "ring",
            "bevel",
            "worm",
            "gear_dist()",
        ],
    ),
    "hinges": dict(
        title="hinges",
        tests=6,
        svg=hinge_svg(5),
        subtitle=(
            "A print-in-place living-hinge mask, an interlocking knuckle hinge with a pin bore, "
            "and snap lock / socket connectors."
        ),
        part="knuckle_hinge_pair(fold=…)",
        code='Hinges.<span class="k">knuckle_hinge_pair</span>(fold=60)',
        metrics=[
            ("flat · 0°", 1576, "5,929.1", "40×46×6"),
            ("folded · 60°", 1748, "5,927.9", "40×36×24"),
        ],
        note=(
            "Two leaves meshed around one pin, exported as a single mesh. Folding re-triangulates "
            "the surface but moves mass rigidly."
        ),
        proof=(
            "0.02%",
            "<b>&Delta;volume across the fold = 1.2 mm&sup3;.</b> A rigid rotation, not a "
            "distortion — the pin bore and knuckle mesh stay closed.",
        ),
        tags=["renders watertight", "living hinge", "knuckle", "snap-lock"],
    ),
    "cubetruss": dict(
        title="cubetruss",
        tests=26,
        svg=truss_svg(3),
        subtitle=(
            "Modular cube-truss segments, the trusses tiled from them (with end clips), "
            "L/T corners, diagonal supports, and the printed clip family."
        ),
        part="cubetruss(extents=3)",
        code='CubeTruss.<span class="k">cubetruss</span>(extents=3)',
        metrics=[("3-segment truss", 1456, "15,456.6", "30×84×30")],
        note=(
            "Each 30 mm cube is lightened with octagonal tunnels through all three axes and braced; "
            "the assembly is one watertight solid. Length = cubetruss_dist(3,1) = 84 mm."
        ),
        proof=None,
        tags=["segment", "corner", "support", "clip", "foot", "joiner"],
    ),
    "joiners": dict(
        title="joiners",
        tests=8,
        svg=dovetail_svg(),
        subtitle=(
            "Shapes that connect two separately-printed parts: a tapered-or-straight dovetail "
            "joint — male tenon or female socket — and a press-and-click snap pin."
        ),
        part='dovetail("male", width=15, height=8, slide=30)',
        code='Joiners.<span class="k">dovetail</span>("male", width=15, height=8, slide=30)',
        metrics=[
            ("male dovetail", 12, "3,920.0", "18×30×8"),
            ("snap pin", 1718, "199.5", "6×6×15"),
        ],
        note=(
            'The dovetail flares to <span class="mono">w + 2·h/slope</span> at the top so it '
            "resists pulling apart; a taper lets a long joint slide home and wedge tight. The "
            "female is the same shape grown by <b>slop</b> for a press fit."
        ),
        proof=None,
        tags=["dovetail", "taper", "male / female", "snap-pin", "socket"],
    ),
    "ball_bearings": dict(
        title="ball_bearings",
        tests=10,
        svg=bearing_svg(9),
        subtitle=(
            "Standard cartridge models from a trade-size name — shielded (ZZ) or open, "
            "with the balls modelled rolling in the race."
        ),
        part='ball_bearing("608")',
        code='BallBearings.<span class="k">ball_bearing</span>("608")',
        metrics=[("608 · open", 2328, "1,640.6", "22×22×7")],
        note=(
            "The open 608 skate bearing: inner and outer races, a toroidal ball groove, and 9 balls "
            "spaced around it — one watertight assembly. 136 trade sizes are tabulated."
        ),
        proof=None,
        tags=["136 sizes", "608", "6902ZZ", "R8", "open / shielded"],
    ),
    "modular_hose": dict(
        title="modular_hose",
        tests=16,
        svg=hose_svg(),
        subtitle=(
            'The ball-and-socket segments of a modular "Loc-Line" style adjustable hose — '
            'a ball end, a socket end, or a full segment, for the 1/4", 1/2" and 3/4" sizes.'
        ),
        part='modular_hose(0.5, "segment")',
        code='ModularHose.<span class="k">modular_hose</span>(0.5, "segment")',
        metrics=[
            ('1/2" segment', 2760, "3,432.6", "25×25×30"),
            ('1/2" ball end', 1500, "1,465.7", "22×21×13"),
        ],
        note=(
            "The ball/socket cross-section is the exact turtle-path profile BOSL2 uses, revolved "
            "into a segment. Segments chain into a bendy hose; <b>clearance</b> loosens the joint."
        ),
        proof=None,
        tags=["ball & socket", '1/4" · 1/2" · 3/4"', "clearance fit", "through bore"],
    ),
    "nema_steppers": dict(
        title="nema_steppers",
        tests=13,
        svg=nema_svg(),
        subtitle=(
            "Models of NEMA-standard stepper motors — body, plinth, shaft and mounting holes — "
            "plus the bolt-pattern mask to difference out of a mounting plate."
        ),
        part="nema_stepper_motor(17)",
        code='NemaSteppers.<span class="k">nema_stepper_motor</span>(17)',
        metrics=[
            ("NEMA 17 motor", 300, "43,714.4", "42×42×44"),
            ("NEMA 23 motor", 456, "79,389.8", "57×57×44"),
        ],
        note=(
            "NEMA 17 is the 3-D-printer classic: a 42.3 mm body on a 31 mm bolt circle with a 5 mm "
            'shaft. Eight sizes (NEMA 6 → 42) are tabulated as a <span class="mono">NemaSpec</span>.'
        ),
        proof=None,
        tags=["NEMA 6 → 42", "mount mask", "bolt pattern", "shaft + plinth"],
    ),
    "linear_bearings": dict(
        title="linear_bearings",
        tests=10,
        svg=linear_bearing_svg(),
        subtitle=(
            "LMxUU linear ball bearings that run along a rod, plus the pillow-block housings "
            "that clamp them to a plate with a teardrop bore and a screw."
        ),
        part="lmXuu_bearing(8)",
        code='LinearBearings.<span class="k">lmXuu_bearing</span>(8)',
        metrics=[
            ("LM8UU bearing", 816, "2,997.1", "15×15×24"),
            ("LM8UU housing", 508, "6,499.2", "27×24×25"),
        ],
        note=(
            "The bearing is four nested shells modelling the outer race, liner and ball tracks; "
            "the housing prints without support thanks to its teardrop bore. 17 LMxUU sizes are tabulated."
        ),
        proof=None,
        tags=["LMxUU", "17 sizes", "pillow-block", "teardrop bore"],
    ),
    "polyhedra": dict(
        title="polyhedra",
        tests=19,
        svg=poly_svg(),
        subtitle=(
            "The five Platonic solids as watertight polyhedra — sized by circumradius, diameter, "
            "inradius or side. The dodecahedron is built as the dual of the icosahedron."
        ),
        part='regular_polyhedron("dodecahedron", side=12)',
        code='Polyhedra.<span class="k">regular_polyhedron</span>("dodecahedron", side=12)',
        metrics=[
            ("dodecahedron · side=12", 36, "13,241.9", "31×31×31"),
            ("icosahedron · r=15", 20, "8,559.5", "26×26×26"),
        ],
        note=(
            "Vertices come from exact &phi;-based coordinates, normalised to a unit circumradius and "
            "scaled to the requested size. Every one closes watertight, winding included."
        ),
        proof=(
            "V&minus;E+F=2",
            "<b>Euler's formula holds for all five.</b> The icosahedron's 12 "
            "vertices, 30 edges and 20 faces satisfy it — the test suite checks each solid.",
        ),
        tags=[
            "tetrahedron",
            "cube",
            "octahedron",
            "dodecahedron",
            "icosahedron",
            "dual",
        ],
    ),
    "walls": dict(
        title="walls",
        tests=12,
        svg=wall_svg(),
        subtitle=(
            "FDM-optimised walls that use less plastic and print without support: a cross-braced "
            "sparse wall, a corrugated wall, thick-edged thinning walls and triangles, and struts."
        ),
        part="sparse_wall(h=50, l=100, thick=4)",
        code='Walls.<span class="k">sparse_wall</span>(h=50, l=100, thick=4)',
        metrics=[
            ("sparse wall · l=100", 280, "12,007.0", "4×101×50"),
            ("thinning wall · l=80", 44, "9,422.6", "4×80×50"),
        ],
        note=(
            "The diagonal braces are held under <b>maxang</b> from vertical so every overhang prints "
            "clean; the thinning wall is BOSL2's exact 24-point polyhedron, transcribed and closed watertight."
        ),
        proof=(
            "40%",
            "<b>The sparse lattice fills its 4×100×50 envelope with 12,007 mm&sup3;</b> — 40% "
            "less plastic than the 20,000 mm&sup3; solid wall, and it needs no support.",
        ),
        tags=[
            "sparse",
            "corrugated",
            "thinning-wall",
            "thinning-triangle",
            "narrowing-strut",
            "support-free",
        ],
    ),
    "wiring": dict(
        title="wiring",
        tests=11,
        svg=wire_svg(13),
        subtitle=(
            "A routed bundle of round wires: hex-packed in cross-section and swept along a path "
            "whose corners are rounded, each wire coloured from a 17-entry table."
        ),
        part="wire_bundle(path, wires=13, rounding=10)",
        code='Wiring.<span class="k">wire_bundle</span>(path, wires=13, rounding=10)',
        metrics=[
            ("1 wire · watertight", 796, "529.0", "52×52×51"),
            ("13-wire bundle", 10348, "6,877.0", "60×60×55"),
        ],
        note=(
            "The wires pack into the optimal hex arrangement (rings of 1, 6, 12, …) and each sweeps "
            "along the rounded route as its own tube — kept separate and coloured, exactly as BOSL2 draws them."
        ),
        proof=(
            "529.0 mm³ ×13",
            "<b>One wire seals watertight at 796 triangles.</b> Thirteen of them, "
            "hex-packed and tangent, are 13 independent tubes — 13 × 529.0 = 6,877 mm&sup3; of copper, no overlap.",
        ),
        tags=[
            "hex-packed",
            "path-sweep",
            "rounded corners",
            "17 colours",
            "separate tubes",
        ],
    ),
    "hooks": dict(
        title="hooks",
        tests=14,
        svg=hook_svg(),
        subtitle=(
            "A ring hook: a rectangular mounting base that flares up and joins tangentially to a "
            "Y-axis cylinder — the ring — with a round, D-shaped or custom through-hole."
        ),
        part="ring_hook([50, 10], 25, or_=25, ir=20)",
        code='Hooks.<span class="k">ring_hook</span>([50, 10], 25, or_=25, ir=20)',
        metrics=[
            ("ring · ir=20", 208, "9,771.2", "50×10×50"),
            ("D-hole ring", 144, "18,737.4", "50×10×50"),
        ],
        note=(
            "Give exactly two of <b>or/od</b>, <b>ir/id</b> and <b>wall</b> to size the ring. The "
            "base flares to the tangent points computed by <b>circle_point_tangents()</b>, so the "
            "paddle meets the cylinder seamlessly. Circle, D and custom-path holes all close watertight."
        ),
        proof=(
            "tangent join",
            "<b>The base corners must lie outside the ring</b> so a tangent exists; "
            "the flare follows it exactly. Verified watertight for round, D and octagonal holes.",
        ),
        tags=[
            "ring hook",
            "tangent base",
            "circle / D / custom hole",
            "or·ir·wall",
            "solid paddle",
        ],
    ),
}

# gallery order and the modules that only get an API link (no rendered spec sheet)
GALLERY = [
    "gears",
    "nema_steppers",
    "hinges",
    "joiners",
    "hooks",
    "polyhedra",
    "walls",
    "wiring",
    "threading",
    "cubetruss",
    "screw_drive",
    "ball_bearings",
    "linear_bearings",
    "modular_hose",
    "bottlecaps",
    "sliders",
]
API_ONLY = {
    "threading": (
        25,
        "Watertight helical threads swept as one polyhedron; ISO / trapezoidal / acme / square / buttress.",
    ),
    "screw_drive": (
        19,
        "Phillips, hex, Torx and Robertson driver-recess masks; subtract from a head to make the socket.",
    ),
    "bottlecaps": (
        7,
        "Standard soda-bottle threadings — a PCO-1810 / PCO-1881 neck and its matching cap.",
    ),
    "sliders": (
        5,
        "A V-groove slider and its mating rail, both shaped to 3-D print without support.",
    ),
}

# --------------------------------------------------------------------------
# variants: the clickable set per module. Each is (id, label, render-expression). The example code,
# the caption and the measured metrics are all derived from the expression + a real render.
# --------------------------------------------------------------------------

_HOOK_OCT = "hole=[[10*math.cos(math.radians(22.5+45*k)),10*math.sin(math.radians(22.5+45*k))] for k in range(8)]"

SETUP = {
    "gears": "from bosl2.gears import Gears\n",
    "walls": "from bosl2.walls import Walls\n",
    "wiring": "from bosl2.wiring import Wiring\nPATH=[[50,0,-50],[50,50,-50],[0,50,-50],[0,0,-50],[0,0,0]]\n",
    "hooks": "import math\nfrom bosl2.hooks import Hooks\n",
    "polyhedra": "from bosl2.polyhedra import Polyhedra\n",
    "hinges": "from bosl2.hinges import Hinges\n",
    "joiners": "from bosl2.joiners import Joiners\n",
    "cubetruss": "from bosl2.cubetruss import CubeTruss\n",
    "ball_bearings": "from bosl2.ball_bearings import BallBearings\n",
    "linear_bearings": "from bosl2.linear_bearings import LinearBearings\n",
    "modular_hose": "from bosl2.modular_hose import ModularHose\n",
    "nema_steppers": "from bosl2.nema_steppers import NemaSteppers\n",
}

VARIANTS = {
    "gears": [
        ("spur", "spur", "Gears.spur_gear(mod=4, teeth=20, thickness=8, shaft_diam=6)"),
        (
            "profile-shift",
            "profile-shift",
            "Gears.spur_gear(mod=4, teeth=7, thickness=8)",
        ),
        (
            "helical",
            "helical",
            "Gears.spur_gear(mod=4, teeth=20, thickness=8, helical=25, shaft_diam=6)",
        ),
        (
            "herringbone",
            "herringbone",
            "Gears.spur_gear(mod=4, teeth=20, thickness=12, helical=25, herringbone=True, shaft_diam=6)",
        ),
        ("rack", "rack", "Gears.rack(mod=4, teeth=8, thickness=8, height=10)"),
        (
            "ring",
            "ring gear",
            "Gears.ring_gear(mod=4, teeth=24, thickness=8, backing=4)",
        ),
        (
            "bevel",
            "bevel",
            "Gears.bevel_gear(mod=4, teeth=20, face_width=10, pitch_angle=45, shaft_diam=6)",
        ),
        ("worm", "worm", "Gears.worm(mod=4, d=30, l=50, starts=1)"),
    ],
    "walls": [
        ("sparse", "sparse", "Walls.sparse_wall(h=50, l=100, thick=4)"),
        ("corrugated", "corrugated", "Walls.corrugated_wall(h=50, l=100, thick=5)"),
        ("thinning-wall", "thinning wall", "Walls.thinning_wall(h=50, l=80, thick=4)"),
        (
            "thinning-triangle",
            "thinning triangle",
            "Walls.thinning_triangle(h=50, l=80, thick=4, center=True)",
        ),
        (
            "strut",
            "narrowing strut",
            "Walls.narrowing_strut(w=10, l=80, wall=5, ang=30)",
        ),
        (
            "sparse-cuboid",
            "sparse cuboid",
            "Walls.sparse_cuboid([20, 40, 30], strut=2)",
        ),
    ],
    "wiring": [
        ("13", "13 wires", "Wiring.wire_bundle(PATH, wires=13, rounding=10)"),
        ("7", "7 wires", "Wiring.wire_bundle(PATH, wires=7, rounding=10)"),
        ("1", "1 wire", "Wiring.wire_bundle(PATH, wires=1, rounding=10)"),
        (
            "thick",
            "thick gauge",
            "Wiring.wire_bundle(PATH, wires=7, wirediam=3, rounding=15)",
        ),
    ],
    "hooks": [
        ("ring", "ring hole", "Hooks.ring_hook([50, 10], 25, or_=25, ir=20)"),
        ("solid", "solid paddle", "Hooks.ring_hook([70, 10], 25, or_=25, ir=0)"),
        ("d-hole", "D hole", 'Hooks.ring_hook([50, 10], 25, or_=25, ir=15, hole="D")'),
        (
            "rounded",
            "rounded",
            "Hooks.ring_hook([50, 10], 40, or_=25, ir=15, rounding=5)",
        ),
        (
            "custom",
            "custom hole",
            f"Hooks.ring_hook([50, 20], 30, or_=25, {_HOOK_OCT})",
        ),
    ],
    "polyhedra": [
        ("tetrahedron", "tetrahedron", "Polyhedra.tetrahedron(r=15)"),
        ("cube", "cube", "Polyhedra.cube(r=15)"),
        ("octahedron", "octahedron", "Polyhedra.octahedron(r=15)"),
        ("dodecahedron", "dodecahedron", "Polyhedra.dodecahedron(side=12)"),
        ("icosahedron", "icosahedron", "Polyhedra.icosahedron(r=15)"),
    ],
    "hinges": [
        ("pair", "knuckle pair", "Hinges.knuckle_hinge_pair(length=40, segs=5)"),
        ("knuckle", "single leaf", "Hinges.knuckle_hinge(length=40, segs=5)"),
        ("snap-lock", "snap lock", "Hinges.snap_lock()"),
        ("snap-socket", "snap socket", "Hinges.snap_socket()"),
    ],
    "joiners": [
        (
            "male",
            "male dovetail",
            'Joiners.dovetail("male", width=15, height=8, slide=30)',
        ),
        (
            "female",
            "female socket",
            'Joiners.dovetail("female", width=15, height=8, slide=30)',
        ),
        (
            "taper",
            "tapered",
            'Joiners.dovetail("male", width=15, height=8, slide=30, taper=4)',
        ),
        ("snap-pin", "snap pin", "Joiners.snap_pin()"),
        ("socket", "pin socket", "Joiners.snap_pin_socket()"),
    ],
    "cubetruss": [
        ("truss", "3-truss", "CubeTruss.cubetruss(extents=3)"),
        ("segment", "segment", "CubeTruss.cubetruss_segment()"),
        ("corner", "corner", "CubeTruss.cubetruss_corner()"),
        ("support", "support", "CubeTruss.cubetruss_support(extents=1)"),
        ("clip", "clip", "CubeTruss.cubetruss_clip()"),
    ],
    "ball_bearings": [
        ("608", "608", 'BallBearings.ball_bearing("608")'),
        ("6902zz", "6902ZZ", 'BallBearings.ball_bearing("6902ZZ")'),
        ("r8", "R8", 'BallBearings.ball_bearing("R8")'),
    ],
    "linear_bearings": [
        ("lm8uu", "LM8UU", "LinearBearings.lmXuu_bearing(8)"),
        ("housing", "LM8UU housing", "LinearBearings.lmXuu_housing(8)"),
        ("lm12uu", "LM12UU", "LinearBearings.lmXuu_bearing(12)"),
    ],
    "modular_hose": [
        ("segment", "segment", 'ModularHose.modular_hose(0.5, "segment")'),
        ("ball", "ball end", 'ModularHose.modular_hose(0.5, "ball")'),
        ("socket", "socket end", 'ModularHose.modular_hose(0.5, "socket")'),
    ],
    "nema_steppers": [
        ("17", "NEMA 17", "NemaSteppers.nema_stepper_motor(17)"),
        ("23", "NEMA 23", "NemaSteppers.nema_stepper_motor(23)"),
        ("8", "NEMA 8", "NemaSteppers.nema_stepper_motor(8)"),
        ("mask", "mount mask", "NemaSteppers.nema_mount_mask(17)"),
    ],
}


def _derive_code(expr: str) -> tuple[str, str]:
    """From a render expression, produce (html code with the method bolded, plain-text caption)."""
    m = re.match(r"([A-Za-z_][\w]*)\.([A-Za-z_]\w*)\((.*)\)\s*$", expr, re.S)
    if not m:
        return expr, expr
    cls, method, args = m.groups()
    return f'{cls}.<span class="k">{method}</span>({args})', f"{method}({args})"


def build_variant_stls(force: bool = False) -> dict:
    """Render every variant to specs/_stl/<module>-<id>.stl and measure it; cache to metrics.json.

    Returns {module: {id: {tris, vol, bbox, wt}}}. Renders only what's missing unless *force*."""
    STL_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = STL_DIR / "metrics.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    have_app = render_object is not None and find_pythonscad_binary() is not None
    for mod, variants in VARIANTS.items():
        cache.setdefault(mod, {})
        for vid, _label, expr in variants:
            stl = STL_DIR / f"{mod}-{vid}.stl"
            if not force and stl.exists() and vid in cache[mod]:
                continue
            if not have_app:
                if vid not in cache[mod]:
                    print(f"  ! no app and no cache for {mod}-{vid}; viewer will show the poster")
                continue
            res = render_object(expr, stl, setup=SETUP[mod], timeout=240, export_format="binstl")
            if not res.ok:
                print(f"  ! render FAILED {mod}-{vid}: {(res.error or '')[:120]}")
                continue
            mm = stl_metrics(stl)
            size = "×".join(str(round(float(v))) for v in mm.size)
            cache[mod][vid] = {
                "tris": mm.ntris,
                "vol": f"{mm.volume:,.1f}",
                "bbox": size,
                "wt": bool(mm.watertight),
            }
            print(f"  rendered {mod}-{vid}: {mm.ntris} tris, wt={mm.watertight}")
    cache_path.write_text(json.dumps(cache, indent=1))
    return cache


HEAD = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>{title}</title><link rel="stylesheet" href="spec.css"></head><body>'
)
BAR = (
    '<header class="bar"><div class="wrap"><a class="logo" href="index.html">py<b>bosl2</b></a>'
    '<span class="sep">/</span><span class="meta">{crumb}</span>'
    '<nav><a href="index.html">catalog</a><a href="../index.html">API docs &rarr;</a></nav></div></header>'
)
# module pages get an extra header link straight to that module's own API reference page.
MODBAR = (
    '<header class="bar"><div class="wrap"><a class="logo" href="index.html">py<b>bosl2</b></a>'
    '<span class="sep">/</span><span class="meta">spec sheet · {mod}.py</span>'
    '<nav><a href="index.html">catalog</a><a href="../{mod}.html">{mod}.py API &rarr;</a>'
    '<a href="../index.html">all API docs &rarr;</a></nav></div></header>'
)
FOOT = (
    '<footer><div class="wrap"><span class="mono">pybosl2</span>'
    '<span class="mono" style="color:var(--ink-faint)">·</span>'
    '<span class="mono">metrics measured from the exported STL via the PythonSCAD app</span>'
    '<span class="r mono">BSD-2-Clause</span></div></footer></body></html>'
)


_VIEWER_JS = """<script type="module">
import * as THREE from "https://esm.sh/three@0.160.0";
import { STLLoader } from "https://esm.sh/three@0.160.0/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";
const V = __DATA__;
const box = document.getElementById("viewer"), poster = document.getElementById("poster");
let renderer, scene, camera, controls, mesh, ready = false;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || n;
function resize() { const w = box.clientWidth, h = box.clientHeight || 300;
  renderer.setSize(w, h, false); camera.aspect = w / Math.max(1, h); camera.updateProjectionMatrix(); }
function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(38, 1, 0.01, 1e6); camera.up.set(0, 0, 1);
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio); box.appendChild(renderer.domElement);
  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const k = new THREE.DirectionalLight(0xffffff, 0.85); k.position.set(1, 0.6, 1); scene.add(k);
  const f = new THREE.DirectionalLight(0xffffff, 0.4); f.position.set(-1, -0.8, 0.5); scene.add(f);
  controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
  window.addEventListener("resize", resize); ready = true;
  (function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
}
const loader = new STLLoader();
function load(uri) {
  if (!ready) init();
  loader.load(uri, geo => {
    if (mesh) { scene.remove(mesh); mesh.geometry.dispose(); }
    geo.computeVertexNormals(); geo.computeBoundingBox();
    const c = new THREE.Vector3(); geo.boundingBox.getCenter(c);
    const s = new THREE.Vector3(); geo.boundingBox.getSize(s);
    geo.translate(-c.x, -c.y, -c.z);
    mesh = new THREE.Mesh(geo, new THREE.MeshPhongMaterial({ color: css("--accent"), specular: 0x222222, shininess: 22 }));
    scene.add(mesh);
    const r = Math.max(s.x, s.y, s.z) || 1;
    camera.position.set(r * 1.4, -r * 1.8, r * 1.15); controls.target.set(0, 0, 0);
    poster.style.display = "none"; box.querySelector(".hint")?.remove(); resize();
  }, undefined, () => {
    if (!box.querySelector(".hint")) { const h = document.createElement("div");
      h.className = "hint"; h.textContent = "serve the docs over HTTP for the interactive 3-D view"; box.appendChild(h); }
  });
}
function select(i) {
  const v = V[i];
  document.querySelectorAll(".tags button.tag").forEach((b, j) => b.setAttribute("aria-selected", j === i ? "true" : "false"));
  document.getElementById("code").innerHTML = "&gt;&gt;&gt; " + v.code;
  document.getElementById("s-tris").textContent = v.tris == null ? "\\u2014" : v.tris.toLocaleString();
  document.getElementById("s-vol").textContent = v.vol; document.getElementById("s-bbox").textContent = v.bbox;
  document.getElementById("vpart").textContent = v.part;
  document.getElementById("wtpill").style.display = v.wt ? "" : "none";
  load(v.uri);
}
document.querySelectorAll(".tags button.tag").forEach((b, i) => b.addEventListener("click", () => select(i)));
select(0);
</script>"""


def module_page(key, m, metrics):
    variants = VARIANTS[key]
    data, cache = [], metrics.get(key, {})
    for vid, label, expr in variants:
        code, part = _derive_code(expr)
        mm = cache.get(vid, {})
        data.append(
            {
                "id": vid,
                "label": label,
                "uri": f"_stl/{key}-{vid}.stl",
                "code": code,
                "part": part,
                "tris": mm.get("tris"),
                "vol": mm.get("vol", "—"),
                "bbox": mm.get("bbox", "—"),
                "wt": mm.get("wt", True),
            }
        )
    first = data[0]
    tris0 = f"{first['tris']:,}" if first["tris"] is not None else "—"
    pill = "" if first["wt"] else ' style="display:none"'
    tags = "".join(f'<button class="tag" type="button">{d["label"]}</button>' for d in data)
    proof = ""
    if m["proof"]:
        big, txt = m["proof"]
        proof = f'<div class="proof"><div class="big">{big}</div><div class="txt">{txt}</div></div>'
    script = _VIEWER_JS.replace("__DATA__", json.dumps(data))
    return (
        HEAD.format(title=f"{m['title']} · pybosl2")
        + MODBAR.format(mod=m["title"])
        + '<main><section class="hero"><div class="wrap">'
        f'<div class="eyebrow">Spec sheet · {m["title"]}.py</div>'
        f'<h1>{m["title"]}<span class="dim">.py</span></h1>'
        f'<p class="lede">{m["subtitle"]}</p>'
        '<div class="spec"><div class="draw">'
        f'<div class="caption"><span id="vpart">{first["part"]}</span><span>interactive · drag to orbit</span></div>'
        f'<div class="viewer" id="viewer"><div class="poster" id="poster">{m["svg"]}</div></div></div>'
        '<div class="info">'
        '<div style="display:flex;align-items:center;gap:12px"><h2>rendered &amp; measured</h2>'
        f'<span class="pill pass" id="wtpill"{pill}>watertight</span></div>'
        f"<p>{m['note']}</p>"
        '<div class="taglabel">variants · click to load</div>'
        f'<div class="tags">{tags}</div>'
        '<div class="stats">'
        f'<div><span class="v" id="s-tris">{tris0}</span><span class="l">triangles</span></div>'
        f'<div><span class="v" id="s-vol">{first["vol"]}</span><span class="l">mm&sup3; volume</span></div>'
        f'<div><span class="v" id="s-bbox">{first["bbox"]}</span><span class="l">bbox mm</span></div></div>'
        f'<div class="code" id="code">&gt;&gt;&gt; {first["code"]}</div>'
        f"{proof}"
        '<div style="font-family:var(--mono);font-size:12px;color:var(--ink-dim)">'
        f'{m["tests"]} tests · <a href="../{m["title"]}.html">full API reference &rarr;</a></div>'
        "</div></div></div></section></main>" + script + FOOT
    )


def gallery_page():
    cards = ""
    for key in GALLERY:
        if key in MODULES:
            m = MODULES[key]
            cards += (
                f'<a class="card" href="{key}.html"><div class="top">'
                f'<span class="name">{m["title"]}<span class="py">.py</span></span>'
                f'<span class="arrow">spec &rarr;</span></div>'
                f'<p class="desc">{m["subtitle"]}</p></a>'
            )
        else:
            tests, desc = API_ONLY[key]
            cards += (
                f'<a class="card" href="../{key}.html"><div class="top">'
                f'<span class="name">{key}<span class="py">.py</span></span>'
                f'<span class="tests">{tests} tests</span></div>'
                f'<p class="desc">{desc}</p></a>'
            )
    return (
        HEAD.format(title="pybosl2 · parts catalog")
        + BAR.format(crumb="BOSL2 &rarr; Python · renders through PythonSCAD")
        + '<main><section class="hero"><div class="wrap">'
        '<div class="eyebrow">Parts catalog</div>'
        '<h1>BOSL2 parts,<br><span class="dim">ported to Python and verified against the real app.</span></h1>'
        '<p class="lede">Every mechanical part here is a pure-Python port that builds real, watertight, '
        "3-D-printable geometry through PythonSCAD. The featured modules carry a spec sheet with "
        "metrics measured straight off the exported STL.</p>"
        '</div></section><section style="padding-top:0"><div class="wrap">'
        '<div class="sec-head"><div class="eyebrow" style="color:var(--ink-dim)">§</div>'
        '<h3>The library</h3><span class="count">click a featured module for its spec sheet</span></div>'
        f'<div class="grid">{cards}</div></div></section></main>' + FOOT
    )


# --------------------------------------------------------------------------
# pretty-printer: reindent the generated one-line markup so the .html files are
# human-readable, WITHOUT changing what the browser renders. Lines break only at
# block-element boundaries; inline runs (text and inline tags) are never split, so
# no significant whitespace is ever inserted between inline siblings.
# --------------------------------------------------------------------------

# Tags kept on the same line as surrounding text (breaking around these could insert visible spaces).
_INLINE = {
    "a",
    "b",
    "i",
    "u",
    "em",
    "strong",
    "span",
    "small",
    "code",
    "sup",
    "sub",
    "abbr",
    "br",
    "img",
    "text",
    "tspan",
    "title",
}
# Elements with no closing tag; they must not open an indent level.
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


def _tagname(tok: str) -> str:
    m = re.match(r"</?\s*([a-zA-Z0-9]+)", tok)
    return m.group(1).lower() if m else ""


def _is_block(tok: str) -> bool:
    """A markup token that forces a line break (a non-inline, non-declaration tag)."""
    return tok.startswith("<") and not tok.startswith("<!") and _tagname(tok) not in _INLINE


def _closes_simple(toks: list[str], i: int) -> int:
    """If the block element opening at *i* contains only inline/text content, return the index of its
    matching close tag; otherwise -1. 'Simple' elements are emitted on a single line."""
    name = _tagname(toks[i])
    depth = 1
    for j in range(i + 1, len(toks)):
        t = toks[j]
        if not _is_block(t):
            continue  # text or inline tag: still simple
        if t.rstrip().endswith("/>") or _tagname(t) in _VOID:
            return -1  # a block void/self-close child (e.g. an SVG shape)
        if t.startswith("</"):
            depth -= 1
            if depth == 0 and _tagname(t) == name:
                return j
        else:
            return -1  # a nested block element -> not simple
    return -1


def _format_html(html: str, indent: str = "  ") -> str:
    """Reindent well-formed generated HTML for readability without changing what it renders.

    Block elements go on their own indented lines; an element whose content is only text and inline
    tags is kept whole on one line, so no whitespace is ever inserted inside a run of inline content.
    ``<script>`` blocks are emitted verbatim (their JS contains ``<``/``>`` that isn't markup)."""
    out: list[str] = []
    buf: list[str] = []
    depth = 0

    def flush():
        if buf:
            line = "".join(buf).strip()
            if line:
                out.append(indent * depth + line)
            buf.clear()

    def emit(substr: str):
        nonlocal depth
        toks = [t for t in re.split(r"(<[^>]+>)", substr) if t]
        i = 0
        while i < len(toks):
            tok = toks[i]
            if not _is_block(tok):
                buf.append(tok)  # text, inline tag, or declaration run
                i += 1
                continue
            flush()
            if tok.startswith("</"):  # block close
                depth = max(0, depth - 1)
                out.append(indent * depth + tok)
            elif tok.rstrip().endswith("/>") or _tagname(tok) in _VOID:
                out.append(indent * depth + tok)  # self-closing / void
            else:
                end = _closes_simple(toks, i)
                if end >= 0:  # inline-only element: keep on one line
                    out.append(indent * depth + "".join(toks[i : end + 1]))
                    i = end
                else:  # block container: open and indent
                    out.append(indent * depth + tok)
                    depth += 1
            i += 1

    # Split off <script>...</script> so its JS is passed through untouched (odd chunks are scripts).
    for idx, part in enumerate(re.split(r"(<script\b[^>]*>.*?</script>)", html, flags=re.S | re.I)):
        if not part:
            continue
        if idx % 2 == 1:
            flush()
            out.append(indent * depth + part.strip())
        else:
            emit(part)
    flush()
    return "\n".join(out) + "\n"


def _norm(html: str) -> str:
    """Collapse insignificant inter-tag whitespace, for proving the reindent is render-safe."""
    return re.sub(r">\s+<", "><", html).strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "spec.css").write_text(CSS)
    metrics = build_variant_stls(force="--force" in sys.argv)
    pages = {
        "index.html": gallery_page(),
        **{f"{k}.html": module_page(k, m, metrics) for k, m in MODULES.items()},
    }
    for name, raw in pages.items():
        pretty = _format_html(raw)
        assert _norm(pretty) == _norm(raw), f"reindent changed the markup of {name}"  # render-safe check
        (OUT / name).write_text(pretty)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
