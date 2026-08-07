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
# FileGroup: pybosl2

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

# Add repo root to sys.path before importing from docs or tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docs._ext.stl_viewer import spec_viewer_html

OUT = Path(__file__).resolve().parent / "specs"
STL_DIR = Path(__file__).resolve().parent / "_extra" / "specs" / "_stl"

# Rendering is optional: with the PythonSCAD app present we render each variant to an STL and measure
# it; without it, we reuse the STLs and metrics already cached on disk (_stl/metrics.json).
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
  --accent:#38bdf0; --pass:#57d9a3; --warn:#e6b45e; --model:#aecbe8;
  --mono:ui-monospace,"SF Mono","SFMono-Regular",Menlo,Consolas,"Liberation Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme: light){
  :root{
    --ground:#eaeef1; --panel:#ffffff; --panel-2:#f4f7f9; --line:#d2dade;
    --ink:#171c21; --ink-dim:#586269; --ink-faint:#8b959c;
    --accent:#0d7ba6; --pass:#158a5e; --warn:#9c6612; --model:#6f9ac9;
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0; background:var(--ground); color:var(--ink); font-family:var(--sans);
  font-size:16px; line-height:1.6; -webkit-font-smoothing:antialiased;
  background-image:linear-gradient(var(--line) 1px,transparent 1px),
    linear-gradient(90deg,var(--line) 1px,transparent 1px);
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
.spec .caption{font-family:var(--mono); font-size:11.5px; color:var(--ink-dim);
  display:flex; justify-content:space-between; gap:10px}
.spec svg{width:100%; height:auto; display:block}
.spec .info{padding:22px 24px; display:flex; flex-direction:column; gap:15px}
.spec h2{font-family:var(--mono); font-size:19px; margin:0}
.spec p{margin:0; color:var(--ink-dim); font-size:14.5px}
.pill{display:inline-flex; align-items:center; gap:6px; font-family:var(--mono); font-size:11px; letter-spacing:.04em;
  padding:2px 9px; border-radius:999px; border:1px solid; text-transform:uppercase}
.pill.pass{color:var(--pass); border-color:color-mix(in srgb,var(--pass) 45%,var(--line))}
.pill.pass::before{content:""; width:7px;height:7px;border-radius:50%;background:var(--pass)}
table.metrics{width:100%; border-collapse:collapse; font-family:var(--mono);
  font-size:13px; font-variant-numeric:tabular-nums}
table.metrics th{text-align:left; font-weight:400; color:var(--ink-dim); padding:7px 0; font-size:10.5px;
  text-transform:uppercase; letter-spacing:.12em; border-bottom:1px solid var(--line)}
table.metrics td{padding:9px 10px 9px 0; border-bottom:1px solid var(--line)}
table.metrics td.num{text-align:right; padding-right:0}
table.metrics tr:last-child td{border-bottom:0}
.proof{border:1px dashed color-mix(in srgb,var(--pass) 45%,var(--line)); border-radius:10px; padding:13px 15px;
  background:color-mix(in srgb,var(--pass) 8%,var(--panel)); display:flex; gap:13px; align-items:center}
.proof .big{font-family:var(--mono); font-weight:700; font-size:24px; color:var(--pass);
  font-variant-numeric:tabular-nums; line-height:1}
.proof .txt{font-size:13px; color:var(--ink-dim)} .proof .txt b{color:var(--ink)}
.code{font-family:var(--mono); font-size:12.5px; background:var(--panel-2); border:1px solid var(--line);
  border-radius:8px; padding:11px 13px; overflow-x:auto; color:var(--ink); position:relative}
.code .k{color:var(--accent)}
.copy-btn{position:absolute; top:8px; right:8px;
  background:var(--panel-2); color:var(--ink-dim);
  border:1px solid var(--line); border-radius:4px;
  padding:2px 8px; font-size:0.8em; cursor:pointer}
.copy-btn:hover{background:var(--accent); color:#fff}
.tags{display:flex; flex-wrap:wrap; gap:6px}
.tag{font-family:var(--mono); font-size:10.5px; color:var(--ink-dim); border:1px solid var(--line);
  border-radius:5px; padding:2px 7px}
.tag.hot{color:var(--accent); border-color:color-mix(in srgb,var(--accent) 40%,var(--line))}
/* interactive variant viewer + clickable variant tags */
.spec .viewer{position:relative; width:100%; min-height:300px; border-radius:8px; overflow:hidden;
  display:flex; align-items:center; justify-content:center; background:var(--panel)}
.spec .viewer canvas{display:block}
.spec .viewer .poster{width:100%; display:block}
.spec .viewer .hint{position:absolute; left:10px; bottom:9px; font-family:var(--mono); font-size:10px;
  color:var(--ink-faint); pointer-events:none}
.taglabel{font-family:var(--mono); font-size:10px; text-transform:uppercase;
  letter-spacing:.14em; color:var(--ink-faint)}
button.tag{cursor:pointer; font:inherit; font-family:var(--mono); font-size:10.5px; color:var(--ink-dim);
  background:transparent; border:1px solid var(--line); border-radius:5px;
  padding:3px 9px; transition:color .13s,background .13s,border-color .13s}
button.tag:hover{color:var(--accent); border-color:color-mix(in srgb,var(--accent) 45%,var(--line))}
button.tag[aria-selected="true"]{color:var(--ground); background:var(--accent); border-color:var(--accent)}
@media (prefers-color-scheme:light){button.tag[aria-selected="true"]{color:#fff}}
.stats{display:flex; gap:28px; flex-wrap:wrap; font-family:var(--mono)}
.stats>div{display:flex; flex-direction:column; gap:2px}
.stats .v{font-size:19px; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.05}
.stats .l{font-size:10px; text-transform:uppercase; letter-spacing:.1em; color:var(--ink-dim)}
.sec-head{display:flex; align-items:baseline; gap:14px; border-bottom:1px solid var(--line);
  padding-bottom:12px; margin-bottom:24px}
.sec-head h3{font-family:var(--mono); font-size:15px; margin:0}
.sec-head .count{margin-left:auto; font-family:var(--mono); font-size:12px; color:var(--ink-dim)}
.grid{display:grid; grid-template-columns:repeat(2,1fr); gap:14px}
@media (max-width:720px){.grid{grid-template-columns:1fr}}
.card{border:1px solid var(--line); border-radius:10px; background:var(--panel); padding:16px 18px; display:flex;
  flex-direction:column; gap:9px; transition:border-color .15s, transform .15s; color:inherit}
a.card:hover{border-color:color-mix(in srgb,var(--accent) 55%,var(--line));
  transform:translateY(-2px); text-decoration:none}
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


def _simple_svg(icon_path: str, label: str = "") -> str:
    """A small procedural schematic icon for spec-sheet poster images."""
    w, h = 460, 240
    bg = '<rect width="460" height="240" fill="var(--ground)"/>'
    body = bg + f'<path d="{icon_path}" fill="none" stroke="var(--ink-dim)" stroke-width="2" stroke-linecap="round"/>'
    return _svg(body, w, h, label=label)


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
        f'<circle cx="{cx}" cy="{cy}" r="{rmid}" fill="none" '
        f'stroke="var(--accent)" stroke-width="1" stroke-dasharray="5 5"/>'
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
    cx, cy, length_ = 230, 118, 300
    od, idd = 116, 62
    x0, x1 = cx - length_ / 2, cx + length_ / 2
    yo0, yo1 = cy - od / 2, cy + od / 2
    yi0, yi1 = cy - idd / 2, cy + idd / 2
    dots = ""
    br = (yi0 - yo0) / 2 * 0.55
    ycen_t = (yo0 + yi0) / 2
    ycen_b = (yo1 + yi1) / 2
    for i in range(7):
        x = x0 + (i + 0.5) * length_ / 7
        for yc in (ycen_t, ycen_b):
            dots += (
                f'<circle cx="{x:.1f}" cy="{yc:.1f}" r="{br:.1f}" '
                f'fill="color-mix(in srgb,var(--accent) 24%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.1"/>'
            )
    body = (
        f'<rect x="{x0}" y="{yo0}" width="{length_}" height="{od}" rx="8" '
        f'fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<rect x="{x0 - 14}" y="{yi0}" width="{length_ + 28}" height="{idd}" '
        f'fill="var(--ground)" stroke="var(--ink-dim)" stroke-width="1.4"/>'
        f'<line x1="{x0 - 26}" y1="{cy}" x2="{x1 + 26}" y2="{cy}" '
        f'stroke="var(--accent)" stroke-width="1.2" stroke-dasharray="10 4 2 4"/>'
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
        def point(dx, dy, dz, bx=bx, by=by):
            return (bx + dx * ex + dy * (-ex) + dz * 0, by + dx * ey + dy * ey - dz * s)

        a_pt = (bx, by)
        b_pt = (bx + ex, by + ey)
        _c_pt = (bx, by + s)
        d_pt = (bx + ex, by + ey + s)
        e_pt = (bx - ex, by + ey)
        f_pt = (bx - ex, by + ey + s)
        # top rhombus a_pt b_pt e_pt and the front faces
        out += (
            f'<polygon points="{a_pt[0]:.0f},{a_pt[1]:.0f} {b_pt[0]:.0f},{b_pt[1]:.0f} '
            f'{a_pt[0]:.0f},{a_pt[1] + 0:.0f}" fill="none"/>'
            f'<polygon points="{a_pt[0]:.0f},{a_pt[1]:.0f} {b_pt[0]:.0f},{b_pt[1]:.0f} '
            f'{(b_pt[0] - ex):.0f},{(b_pt[1]):.0f} {e_pt[0]:.0f},{e_pt[1]:.0f}" '
            f'fill="color-mix(in srgb,var(--accent) 16%,var(--panel-2))" '
            f'stroke="var(--ink-dim)" stroke-width="1.3"/>'
            f'<polygon points="{e_pt[0]:.0f},{e_pt[1]:.0f} {(b_pt[0] - ex):.0f},{b_pt[1]:.0f} '
            f'{d_pt[0] - ex:.0f},{d_pt[1]:.0f} {f_pt[0]:.0f},{f_pt[1]:.0f}" '
            f'fill="var(--panel)" stroke="var(--ink-dim)" stroke-width="1.3"/>'
            f'<polygon points="{(b_pt[0] - ex):.0f},{b_pt[1]:.0f} {b_pt[0]:.0f},{b_pt[1]:.0f} '
            f'{d_pt[0]:.0f},{d_pt[1]:.0f} {d_pt[0] - ex:.0f},{d_pt[1]:.0f}" '
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
        f'<line x1="{cx + bw / 2:.0f}" y1="{yb}" x2="{cx + tw / 2:.0f}" y2="{yt}" '
        f'stroke="var(--accent)" stroke-width="1.4"/>'
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
        f'<line x1="{cx - bs}" y1="{cy + hb + 16}" x2="{cx + bs}" y2="{cy + hb + 16}" '
        f'stroke="var(--ink-faint)" stroke-width="1"/>'
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
        f'<line x1="{cx}" y1="30" x2="{cx}" y2="222" '
        f'stroke="var(--accent)" stroke-width="1.2" stroke-dasharray="10 4 2 4"/>'
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


def hinge_svg(_segs=5):
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
    <text x="230" y="232" text-anchor="middle" fill="var(--ink-dim)"
      font-family="var(--mono)" font-size="11">length = 40 mm · segs=5</text>
    """
    return _svg(body, label="Plan view of a five-knuckle butt hinge.")


def poly_svg():
    # a real icosahedron: rotate the phi-based vertices, project, and paint the faces
    # back-to-front, shading each by depth so the solid reads in 3-D.
    phi = (1 + 5**0.5) / 2
    vertices = [
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
    faces = [
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
    m = max(sum(c * c for c in v) ** 0.5 for v in vertices)
    ax, ay = math.radians(-22), math.radians(31)
    rotated = []
    for x, y, z in vertices:
        x, y, z = x / m, y / m, z / m
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        rotated.append((x, y, z))
    cx, cy, s = 230, 112, 92
    projected = [(cx + s * p[0], cy - s * p[1]) for p in rotated]
    body = ""
    for i in sorted(range(len(faces)), key=lambda i: sum(rotated[v][2] for v in faces[i])):  # far first
        f = faces[i]
        depth = sum(rotated[v][2] for v in f) / 3  # -1 (back) .. 1 (front)
        pct = int(14 + (depth + 1) / 2 * 30)
        pts = " ".join(f"{projected[v][0]:.1f},{projected[v][1]:.1f}" for v in f)
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
        f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
        f'fill="none" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<rect x="{ix0}" y="{iy0}" width="{ix1 - ix0}" height="{iy1 - iy0}" '
        f'fill="none" stroke="var(--ink-dim)" stroke-width="1.3"/>'
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


def tripod_rc2_svg():
    """Top-down schematic of a Manfrotto RC2 plate: trapezoidal body, corner cutouts, facet."""
    cx, cy = 230, 110
    sx, sy = 2.6, 3.0  # scale factors to fit the 460×240 canvas
    bw, tw = 42.4, 37.4  # botwid, topwid
    length, innerlen = 52.5, 43.0
    cor = 25.0  # corner_space
    cleft = 2.0  # left_top

    hw = bw * sx
    hh = length * sy
    iw = tw * sx
    cw = cor * sx
    cl = cleft * sy
    il = innerlen * sy

    x0, y0 = cx - hw / 2, cy - hh / 2

    body = (
        # outer body rectangle
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{hw:.1f}" height="{hh:.1f}" rx="2" '
        f'fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        # inner top surface (narrower, shows the trapezoid)
        f'<path d="M {cx - iw / 2:.1f},{y0 + 3} L {cx + iw / 2:.1f},{y0 + 3} '
        f'L {cx + iw / 2:.1f},{y0 + hh - 3} L {cx - iw / 2:.1f},{y0 + hh - 3} Z" '
        f'fill="none" stroke="var(--accent)" stroke-width="1.2" stroke-dasharray="5 4" opacity="0.8"/>'
        # corner cutouts (top-left and top-right)
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{cw:.1f}" height="{(hh - il) / 2:.1f}" '
        f'fill="var(--ground)" stroke="var(--accent)" stroke-width="1.4"/>'
        f'<rect x="{x0 + hw - cw:.1f}" y="{y0:.1f}" width="{cw:.1f}" height="{(hh - il) / 2:.1f}" '
        f'fill="var(--ground)" stroke="var(--accent)" stroke-width="1.4"/>'
        f'<rect x="{x0:.1f}" y="{y0 + hh - (hh - il) / 2:.1f}" width="{cw:.1f}" height="{(hh - il) / 2:.1f}" '
        f'fill="var(--ground)" stroke="var(--accent)" stroke-width="1.4"/>'
        f'<rect x="{x0 + hw - cw:.1f}" y="{y0 + hh - (hh - il) / 2:.1f}" width="{cw:.1f}" height="{(hh - il) / 2:.1f}" '
        f'fill="var(--ground)" stroke="var(--accent)" stroke-width="1.4"/>'
        # facet cutout (back, between innerlen marks)
        f'<path d="M {cx - 30:.1f},{y0 + hh - cl:.1f} L {cx - 30:.1f},{y0 + hh - cl - 12:.1f} '
        f'L {cx - 18:.1f},{y0 + hh - cl - 20:.1f} L {cx - 18:.1f},{y0 + hh - cl:.1f} Z" '
        f'fill="color-mix(in srgb,var(--accent) 16%,var(--panel))" stroke="var(--ink-dim)" stroke-width="1.2"/>'
        # 1/4-20 threaded insert hole (center)
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="var(--ground)" stroke="var(--pass)" stroke-width="1.6"/>'
        # center mark
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="1.5" fill="var(--pass)"/>'
        # dimension lines
        f'<line x1="{x0 - 10:.1f}" y1="{y0:.1f}" x2="{x0 - 10:.1f}" y2="{y0 + hh:.1f}" '
        f'stroke="var(--ink-faint)" stroke-width="1"/>'
        f'<text x="{x0 - 16:.1f}" y="{cy - 2:.1f}" text-anchor="end" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="9">52.5</text>'
        f'<line x1="{x0:.1f}" y1="{y0 - 10:.1f}" x2="{x0 + hw:.1f}" y2="{y0 - 10:.1f}" '
        f'stroke="var(--ink-faint)" stroke-width="1"/>'
        f'<text x="{cx:.1f}" y="{y0 - 16:.1f}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="9">42.4 / 37.4</text>'
        f'<text x="{cx:.1f}" y="{cy + hh / 2 + 20:.1f}" text-anchor="middle" fill="var(--ink-dim)" '
        f'font-family="var(--mono)" font-size="11">trapezoidal body · chamfered edges · corner cutouts</text>'
    )
    return _svg(body, label="Top-down view of a Manfrotto RC2 quick-release tripod plate.")


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

    def to_x(x):
        return cx + x * scale

    def to_y(z):
        return basey - z * scale

    paddle = (
        f"{to_x(-bx / 2):.1f},{to_y(0):.1f} {to_x(bx / 2):.1f},{to_y(0):.1f} "
        f"{to_x(tx):.1f},{to_y(tz):.1f} {to_x(-tx):.1f},{to_y(tz):.1f}"
    )
    body = (
        f'<circle cx="{to_x(0):.1f}" cy="{to_y(hole_z):.1f}" r="{ro * scale:.1f}" '
        f'fill="var(--panel-2)" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<polygon points="{paddle}" fill="var(--panel-2)" stroke="none"/>'
        f'<polyline points="{to_x(-tx):.1f},{to_y(tz):.1f} {to_x(-bx / 2):.1f},{to_y(0):.1f} '
        f'{to_x(bx / 2):.1f},{to_y(0):.1f} {to_x(tx):.1f},{to_y(tz):.1f}" '
        f'fill="none" stroke="var(--ink-dim)" stroke-width="1.8"/>'
        f'<circle cx="{to_x(0):.1f}" cy="{to_y(hole_z):.1f}" r="{ri * scale:.1f}" '
        f'fill="var(--ground)" stroke="var(--accent)" stroke-width="1.6"/>'
        # tangent construction + points
        f'<line x1="{to_x(bx / 2):.1f}" y1="{to_y(0):.1f}" x2="{to_x(tx):.1f}" '
        f'y2="{to_y(tz):.1f}" stroke="var(--accent)" stroke-width="1" stroke-dasharray="4 4" opacity="0.8"/>'
        f'<line x1="{to_x(-bx / 2):.1f}" y1="{to_y(0):.1f}" x2="{to_x(-tx):.1f}" '
        f'y2="{to_y(tz):.1f}" stroke="var(--accent)" stroke-width="1" stroke-dasharray="4 4" opacity="0.8"/>'
        f'<circle cx="{to_x(tx):.1f}" cy="{to_y(tz):.1f}" r="2.6" fill="var(--accent)"/>'
        f'<circle cx="{to_x(-tx):.1f}" cy="{to_y(tz):.1f}" r="2.6" fill="var(--accent)"/>'
        # hole_z dimension
        f'<line x1="{to_x(-bx / 2) - 14:.1f}" y1="{to_y(0):.1f}" '
        f'x2="{to_x(-bx / 2) - 14:.1f}" y2="{to_y(hole_z):.1f}" '
        f'stroke="var(--ink-dim)" stroke-width="1"/>'
        f'<text x="{to_x(-bx / 2) - 20:.1f}" y="{to_y(hole_z / 2) + 3:.1f}" '
        f'text-anchor="end" fill="var(--ink-dim)" font-family="var(--mono)" font-size="10">hole_z</text>'
        f'<circle cx="{to_x(0):.1f}" cy="{to_y(hole_z):.1f}" r="2.2" fill="var(--accent)"/>'
        f'<text x="{to_x(0):.1f}" y="{basey + 18:.1f}" text-anchor="middle" '
        f'fill="var(--ink-dim)" font-family="var(--mono)" font-size="11">base flares along the ring tangent</text>'
    )
    return _svg(
        body,
        label="Side elevation of a ring hook: a base flaring along the tangent into a holed ring.",
    )


# --------------------------------------------------------------------------
# module registry: real render metrics + copy
# --------------------------------------------------------------------------

MODULES = {
    "gears": {
        "title": "gears",
        "tests": 52,
        "svg": gear_svg(20),
        "subtitle": (
            "Involute spur gears whose teeth are <em>rack-carved with a real undercut</em>, "
            "the way the current BOSL2 does it — plus helical, herringbone, rack, ring, bevel and worm."
        ),
        "part": "spur_gear(mod=5, teeth=20, thickness=8, helical=20)",
        "code": 'SpurGear.<span class="k">shape</span>(mod=5, teeth=20, thickness=8, helical=20, shaft_diam=6)',
        "metrics": [
            ("helical spur · z=20", 5640, "69,617.1", "116×116×8"),
            ("undercut spur · z=8", 2300, "11,984.0", "55×55×8"),
        ],
        "note": (
            "A 20-tooth helical gear meshes at <b>GearSpec.gear_dist()</b>; the 8-tooth gear picks up "
            '<b>profile_shift="auto"</b> so its flanks don\'t undercut. Both close watertight.'
        ),
        "proof": None,
        "tags": [
            "undercut",
            "profile_shift",
            "helical",
            "herringbone",
            "rack",
            "ring",
            "bevel",
            "worm",
            "GearSpec.gear_dist()",
        ],
    },
    "hinges": {
        "title": "hinges",
        "tests": 6,
        "svg": hinge_svg(5),
        "subtitle": (
            "A print-in-place living-hinge mask, an interlocking knuckle hinge with a pin bore, "
            "and snap lock / socket connectors."
        ),
        "part": "knuckle_hinge_pair(fold=…)",
        "code": 'KnuckleHingePair(fold=60).<span class="k">shape</span>()',
        "metrics": [
            ("flat · 0°", 1576, "5,929.1", "40×46×6"),
            ("folded · 60°", 1748, "5,927.9", "40×36×24"),
        ],
        "note": (
            "Two leaves meshed around one pin, exported as a single mesh. Folding re-triangulates "
            "the surface but moves mass rigidly."
        ),
        "proof": (
            "0.02%",
            "<b>&Delta;volume across the fold = 1.2 mm&sup3;.</b> A rigid rotation, not a "
            "distortion — the pin bore and knuckle mesh stay closed.",
        ),
        "tags": ["renders watertight", "living hinge", "knuckle", "snap-lock"],
    },
    "cubetruss": {
        "title": "cubetruss",
        "tests": 26,
        "svg": truss_svg(3),
        "subtitle": (
            "Modular cube-truss segments, the trusses tiled from them (with end clips), "
            "L/T corners, diagonal supports, and the printed clip family."
        ),
        "part": "truss(extents=3)",
        "code": 'Truss(extents=3).<span class="k">shape</span>()',
        "metrics": [("3-segment truss", 1456, "15,456.6", "30×84×30")],
        "note": (
            "Each 30 mm cube is lightened with octagonal tunnels through all three axes and braced; "
            "the assembly is one watertight solid. Length = truss_dist(3,1) = 84 mm."
        ),
        "proof": None,
        "tags": ["segment", "corner", "support", "clip", "foot", "joiner"],
    },
    "joiners": {
        "title": "joiners",
        "tests": 8,
        "svg": dovetail_svg(),
        "subtitle": (
            "Shapes that connect two separately-printed parts: a tapered-or-straight dovetail "
            "joint — male tenon or female socket — and a press-and-click snap pin."
        ),
        "part": 'dovetail("male", width=15, height=8, slide=30)',
        "code": 'Dovetail.<span class="k">__init__</span>(Gender.MALE, width=15, height=8, slide=30).shape()',
        "metrics": [
            ("male dovetail", 12, "3,920.0", "18×30×8"),
            ("snap pin", 1718, "199.5", "6×6×15"),
        ],
        "note": (
            'The dovetail flares to <span class="mono">w + 2·h/slope</span> at the top so it '
            "resists pulling apart; a taper lets a long joint slide home and wedge tight. The "
            "female is the same shape grown by <b>slop</b> for a press fit."
        ),
        "proof": None,
        "tags": ["dovetail", "taper", "male / female", "snap-pin", "socket"],
    },
    "ball_bearings": {
        "title": "ball_bearings",
        "tests": 10,
        "svg": bearing_svg(9),
        "subtitle": (
            "Standard cartridge models from a trade-size name — shielded (ZZ) or open, "
            "with the balls modelled rolling in the race."
        ),
        "part": 'ball_bearing("608")',
        "code": 'BallBearings.<span class="k">ball_bearing</span>("608")',
        "metrics": [("608 · open", 2328, "1,640.6", "22×22×7")],
        "note": (
            "The open 608 skate bearing: inner and outer races, a toroidal ball groove, and 9 balls "
            "spaced around it — one watertight assembly. 136 trade sizes are tabulated."
        ),
        "proof": None,
        "tags": ["136 sizes", "608", "6902ZZ", "R8", "open / shielded"],
    },
    "modular_hose": {
        "title": "modular_hose",
        "tests": 16,
        "svg": hose_svg(),
        "subtitle": (
            'The ball-and-socket segments of a modular "Loc-Line" style adjustable hose — '
            'a ball end, a socket end, or a full segment, for the 1/4", 1/2" and 3/4" sizes.'
        ),
        "part": 'modular_hose(0.5, "segment")',
        "code": 'HoseSegment.<span class="k"></span>(0.5, HoseType.SEGMENT)',
        "metrics": [
            ('1/2" segment', 2760, "3,432.6", "25×25×30"),
            ('1/2" ball end', 1500, "1,465.7", "22×21×13"),
        ],
        "note": (
            "The ball/socket cross-section is the exact turtle-path profile BOSL2 uses, revolved "
            "into a segment. Segments chain into a bendy hose; <b>clearance</b> loosens the joint."
        ),
        "proof": None,
        "tags": ["ball & socket", '1/4" · 1/2" · 3/4"', "clearance fit", "through bore"],
    },
    "nema_steppers": {
        "title": "nema_steppers",
        "tests": 13,
        "svg": nema_svg(),
        "subtitle": (
            "Models of NEMA-standard stepper motors — body, plinth, shaft and mounting holes — "
            "plus the bolt-pattern mask to difference out of a mounting plate."
        ),
        "part": "nema_stepper_motor(17)",
        "code": 'NemaMotor(17).<span class="k">shape</span>()',
        "metrics": [
            ("NEMA 17 motor", 300, "43,714.4", "42×42×44"),
            ("NEMA 23 motor", 456, "79,389.8", "57×57×44"),
        ],
        "note": (
            "NEMA 17 is the 3-D-printer classic: a 42.3 mm body on a 31 mm bolt circle with a 5 mm "
            'shaft. Eight sizes (NEMA 6 → 42) are tabulated as a <span class="mono">NemaSpec</span>.'
        ),
        "proof": None,
        "tags": ["NEMA 6 → 42", "mount mask", "bolt pattern", "shaft + plinth"],
    },
    "linear_bearings": {
        "title": "linear_bearings",
        "tests": 10,
        "svg": linear_bearing_svg(),
        "subtitle": (
            "LMxUU linear ball bearings that run along a rod, plus the pillow-block housings "
            "that clamp them to a plate with a teardrop bore and a screw."
        ),
        "part": "lmXuu_bearing(8)",
        "code": 'LinearBearings.<span class="k">lmXuu_bearing</span>(8)',
        "metrics": [
            ("LM8UU bearing", 816, "2,997.1", "15×15×24"),
            ("LM8UU housing", 508, "6,499.2", "27×24×25"),
        ],
        "note": (
            "The bearing is four nested shells modelling the outer race, liner and ball tracks; "
            "the housing prints without support thanks to its teardrop bore. 17 LMxUU sizes are tabulated."
        ),
        "proof": None,
        "tags": ["LMxUU", "17 sizes", "pillow-block", "teardrop bore"],
    },
    "polyhedra": {
        "title": "polyhedra",
        "tests": 19,
        "svg": poly_svg(),
        "subtitle": (
            "The five Platonic solids as watertight polyhedra — sized by circumradius, diameter, "
            "inradius or side. The dodecahedron is built as the dual of the icosahedron."
        ),
        "part": 'regular_polyhedron("dodecahedron", side=12)',
        "code": 'RegularPolyhedron.<span class="k">__init__</span>(PlatonicSolid.DODECAHEDRON, side=12).shape()',
        "metrics": [
            ("dodecahedron · side=12", 36, "13,241.9", "31×31×31"),
            ("icosahedron · r=15", 20, "8,559.5", "26×26×26"),
        ],
        "note": (
            "Vertices come from exact &phi;-based coordinates, normalised to a unit circumradius and "
            "scaled to the requested size. Every one closes watertight, winding included."
        ),
        "proof": (
            "V&minus;E+F=2",
            "<b>Euler's formula holds for all five.</b> The icosahedron's 12 "
            "vertices, 30 edges and 20 faces satisfy it — the test suite checks each solid.",
        ),
        "tags": [
            "tetrahedron",
            "cube",
            "octahedron",
            "dodecahedron",
            "icosahedron",
            "dual",
        ],
    },
    "walls": {
        "title": "walls",
        "tests": 12,
        "svg": wall_svg(),
        "subtitle": (
            "FDM-optimised walls that use less plastic and print without support: a cross-braced "
            "sparse wall, a corrugated wall, thick-edged thinning walls and triangles, and struts."
        ),
        "part": "sparse_wall(h=50, l=100, thick=4)",
        "code": 'SparseWall.<span class="k">shape</span>(height=50, length=100, thick=4)',
        "metrics": [
            ("sparse wall · l=100", 280, "12,007.0", "4×101×50"),
            ("thinning wall · l=80", 44, "9,422.6", "4×80×50"),
        ],
        "note": (
            "The diagonal braces are held under <b>maxang</b> from vertical so every overhang prints "
            "clean; the thinning wall is BOSL2's exact 24-point polyhedron, transcribed and closed watertight."
        ),
        "proof": (
            "40%",
            "<b>The sparse lattice fills its 4×100×50 envelope with 12,007 mm&sup3;</b> — 40% "
            "less plastic than the 20,000 mm&sup3; solid wall, and it needs no support.",
        ),
        "tags": [
            "sparse",
            "corrugated",
            "thinning-wall",
            "thinning-triangle",
            "narrowing-strut",
            "support-free",
        ],
    },
    "wiring": {
        "title": "wiring",
        "tests": 11,
        "svg": wire_svg(13),
        "subtitle": (
            "A routed bundle of round wires: hex-packed in cross-section and swept along a path "
            "whose corners are rounded, each wire coloured from a 17-entry table."
        ),
        "part": "WireBundle(path, wires=13, rounding=10).shape()",
        "code": 'WireBundle(path, wires=13, rounding=10).<span class="k">shape</span>()',
        "metrics": [
            ("1 wire · watertight", 796, "529.0", "52×52×51"),
            ("13-wire bundle", 10348, "6,877.0", "60×60×55"),
        ],
        "note": (
            "The wires pack into the optimal hex arrangement (rings of 1, 6, 12, …) and each sweeps "
            "along the rounded route as its own tube — kept separate and coloured, exactly as BOSL2 draws them."
        ),
        "proof": (
            "529.0 mm³ ×13",
            "<b>One wire seals watertight at 796 triangles.</b> Thirteen of them, "
            "hex-packed and tangent, are 13 independent tubes — 13 × 529.0 = 6,877 mm&sup3; of copper, no overlap.",
        ),
        "tags": [
            "hex-packed",
            "path-sweep",
            "rounded corners",
            "17 colours",
            "separate tubes",
        ],
    },
    "hooks": {
        "title": "hooks",
        "tests": 14,
        "svg": hook_svg(),
        "subtitle": (
            "A ring hook: a rectangular mounting base that flares up and joins tangentially to a "
            "Y-axis cylinder — the ring — with a round, D-shaped or custom through-hole."
        ),
        "part": "ring_hook([50, 10], 25, or_=25, ir=20)",
        "code": 'RingHook.<span class="k">__init__</span>([50, 10], 25, or_=25, ir=20).shape()',
        "metrics": [
            ("ring · ir=20", 208, "9,771.2", "50×10×50"),
            ("D-hole ring", 144, "18,737.4", "50×10×50"),
        ],
        "note": (
            "Give exactly two of <b>or/od</b>, <b>ir/id</b> and <b>wall</b> to size the ring. The "
            "base flares to the tangent points computed by <b>circle_point_tangents()</b>, so the "
            "paddle meets the cylinder seamlessly. Circle, D and custom-path holes all close watertight."
        ),
        "proof": (
            "tangent join",
            "<b>The base corners must lie outside the ring</b> so a tangent exists; "
            "the flare follows it exactly. Verified watertight for round, D and octagonal holes.",
        ),
        "tags": [
            "ring hook",
            "tangent base",
            "circle / D / custom hole",
            "or·ir·wall",
            "solid paddle",
        ],
    },
    "threading": {
        "title": "threading",
        "tests": 25,
        "svg": _simple_svg(
            "M80,120 L120,60 L140,60 L100,120 M110,150 L160,80 L180,80 L130,150 "
            "M190,90 L210,120 M230,30 L250,60 M260,20 L260,50 "
            "M280,150 L320,90 L340,90 L300,150",
            label="Threaded rod and nut schematic",
        ),
        "subtitle": (
            "Screw-thread generators — ISO, ACME, trapezoidal, buttress, and square threads "
            "for both rods and nuts, with multi-start and left-handed options."
        ),
        "part": "threaded_rod(d=20, l=30, pitch=2.5)",
        "code": '<span class="k">iso_threaded_rod</span>(d=20, l=30, pitch=2.5).shape()',
        "metrics": [
            ("ISO · z=20", 4500, "9,424.8", "20×20×30"),
            ("ACME · z=20", 3200, "8,100.0", "20×20×30"),
        ],
        "note": (
            "Every thread form builds the rod (core + helical thread) as one manifold polyhedron — "
            "an angular sweep of the thread profile stacked over every turn — so the result is always "
            "watertight. Nuts are a hex/square block with a matching threaded hole cut by a tap."
        ),
        "proof": None,
        "tags": ["ISO", "ACME", "trapezoidal", "square", "buttress", "left-handed", "multi-start"],
    },
    "screw_drive": {
        "title": "screw_drive",
        "tests": 19,
        "svg": _simple_svg(
            "M100,100 L120,40 L140,40 L160,100 M130,40 L130,200 M80,160 L180,160 M60,140 L200,140 M70,120 L190,120",
            label="Screw drive recess schematic",
        ),
        "subtitle": (
            "Driver-recess masks for Phillips, hex, Torx, and Robertson — subtract from a screw "
            "head to make the drive recess, with exact dimensional tables from ISO/ANSI standards."
        ),
        "part": 'phillips_mask(size="#2")',
        "code": 'ScrewDrive.<span class="k">phillips_mask</span>(size="#2")',
        "metrics": [
            ("Phillips #2", 600, "95.2", "7×7×5"),
            ("Torx T30", 750, "140.5", "8×8×10"),
        ],
        "note": (
            "Every <code>*_mask</code> is built bottom-on-the-XY-plane. The dimensional helpers — "
            "<b>torx_info</b>, <b>phillips_depth</b>, etc. — return the same numbers as BOSL2."
        ),
        "proof": None,
        "tags": ["Phillips", "hex", "Torx", "Robertson", "ISO 4757", "ISO 14583"],
    },
    "bottlecaps": {
        "title": "bottlecaps",
        "tests": 7,
        "svg": _simple_svg(
            "M120,50 L120,190 M140,50 L140,190 M160,50 L160,190 "
            "M100,80 L180,80 M100,160 L180,160 "
            "M115,80 Q115,30 140,20 Q165,30 165,80",
            label="Bottle neck and cap schematic",
        ),
        "subtitle": (
            "Standard soda-bottle necks and caps — PCO 1810 and 1881 thread finishes — "
            "a threaded neck to graft onto a bottle body and its matching cap."
        ),
        "part": "pco1881_neck()",
        "code": 'BottleCaps.<span class="k">pco1881_neck</span>()',
        "metrics": [
            ("PCO 1810 neck", 4000, "2,150.0", "34×34×20"),
            ("PCO 1881 neck", 3600, "1,800.0", "30×30×18"),
        ],
        "note": (
            "The neck profile (inner bore, support ring, tamper-ring channel and sealing lip) is a "
            "turtle path revolved with <b>rotate_extrude</b>. Threads are <b>thread_helix</b> ridges "
            "with the two thread breaks cut by prismoids."
        ),
        "proof": None,
        "tags": ["PCO 1810", "PCO 1881", "turtle profile", "thread breaks", "neck & cap"],
    },
    "sliders": {
        "title": "sliders",
        "tests": 5,
        "svg": _simple_svg(
            "M60,140 L160,70 M60,160 L160,90 M60,100 L160,30 M130,60 L280,60 L280,140 Z",
            label="V-groove slider and rail schematic",
        ),
        "subtitle": (
            "V-groove sliders and rails — smooth low-friction linear guides for 3-D-printed frames, "
            "with configurable slop and wall thickness."
        ),
        "part": "slider(l=30, base=10, wall=4)",
        "code": 'Sliders.<span class="k">slider</span>(l=30, base=10, wall=4)',
        "metrics": [
            ("slider", 600, "320.5", "10×14×30"),
            ("rail", 400, "950.0", "14×14×100"),
        ],
        "note": (
            "The V-groove profile is cut by the same polygon BOSL2 uses. <b>slop</b> controls "
            "the clearance between slider and rail; the rail is 90° V-grooves in a rectangular bar."
        ),
        "proof": None,
        "tags": ["V-groove", "linear guide", "slop", "low friction"],
    },
    "tripod_mounts": {
        "title": "tripod_mounts",
        "tests": 1,
        "svg": tripod_rc2_svg(),
        "subtitle": (
            "A Manfrotto RC2 quick-release tripod mount plate — the industry-standard plate for "
            "camera and accessory mounting, with a trapezoidal body, chamfered edges, and corner cutouts."
        ),
        "part": "manfrotto_rc2_plate()",
        "code": 'ManfrottoRC2Plate.<span class="k">shape</span>()',
        "metrics": [
            ("RC2 plate · all chamfer", 300, "19,000.0", "43×53×11"),
            ("RC2 plate · bot chamfer", 280, "19,200.0", "43×53×11"),
        ],
        "note": (
            "The plate body is built from a turtle-defined cross-section swept over 52.5 mm. "
            "Chamfering is controlled by the <b>chamfer</b> argument — set to <b>all</b>, "
            "<b>bot</b>/<b>bottom</b>, or <b>none</b>."
        ),
        "proof": None,
        "tags": ["RC2", "Manfrotto", "quick release", "chamfered edges", "turtle sweep"],
    },
    "shapes3d": {
        "title": "shapes3d",
        "tests": 32,
        "svg": _simple_svg(
            "M80,120 L120,60 L180,60 L220,120 L180,180 L120,180 Z M120,60 L120,180 M220,120 L180,180",
            label="3-D primitives schematic",
        ),
        "subtitle": (
            "BOSL2 3-D primitives: cuboid, sphere, cylinder, cone, prismoid, torus, tube, "
            "teardrop, and more — anchored and rounded for direct fabrication."
        ),
        "part": "cuboid([30, 20, 15])",
        "code": 'pybosl2.<span class="k">cuboid</span>([30, 20, 15])',
        "metrics": [
            ("cuboid", 12, "9,000.0", "30×20×15"),
            ("sphere r=15", 720, "14,137.2", "30×30×30"),
        ],
        "note": (
            "Every shape is <b>anchorable</b>: position with <code>anchor=</code>, spin with "
            "<code>spin=</code>, and orient with <code>orient=</code>. Rounding, chamfering, "
            "and edge-selection work consistently across all primitives."
        ),
        "proof": None,
        "tags": ["cuboid", "sphere", "cylinder", "cone", "torus", "tube", "teardrop", "anchors"],
    },
    "shapes2d": {
        "title": "shapes2d",
        "tests": 149,
        "svg": _simple_svg(
            "M70,70 L210,70 L210,190 L70,190 Z M110,40 L170,40 L170,220 L110,220 Z M70,130 L210,130 M140,70 L140,190",
            label="2-D primitives schematic",
        ),
        "subtitle": (
            "BOSL2 2-D primitives: circle, square, rect, trapezoid, star, ring, pie slice, squircle, "
            "keyhole, and more — anchored Path2D shapes that feed directly into extrusions."
        ),
        "part": "circle2d(r=15)",
        "code": 's2.<span class="k">circle2d</span>(r=15)',
        "metrics": [
            ("circle r=15", 24, "—", "30×30"),
            ("rect rounding=5", 8, "—", "40×30"),
        ],
        "note": (
            "Every shape returns a <b>Path2D</b> that chains into 2-D operations: "
            "<code>.offset()</code>, <code>.round_corners()</code>, <code>.polygon()</code>, "
            "<code>.linear_extrude()</code>. Anchors and rounding work consistently."
        ),
        "proof": None,
        "tags": ["circle", "square", "rect", "trapezoid", "star", "ring", "pie slice", "squircle", "keyhole"],
    },
}

# gallery order — every listed module has a full spec sheet with renders, metrics, and tags
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
    "tripod_mounts",
    "shapes3d",
    "shapes2d",
]

# --------------------------------------------------------------------------
# variants: the clickable set per module. Each is (id, label, render-expression). The example code,
# the caption and the measured metrics are all derived from the expression + a real render.
# --------------------------------------------------------------------------

_HOOK_OCT = "hole=[[10*math.cos(math.radians(22.5+45*k)),10*math.sin(math.radians(22.5+45*k))] for k in range(8)]"

SETUP = {
    "gears": (
        "from pybosl2.parts.gears import BevelGear, GearSpec, HerringboneGear, "
        "Rack, RingGear, SpurGear, Worm, WormGear\n"
    ),
    "walls": (
        "from pybosl2.parts.walls import NarrowingStrut, SparseWall, SparseCuboid, "
        "CorrugatedWall, ThinningWall, ThinningTriangle\n"
    ),
    "wiring": (
        "from pybosl2.parts.wiring import WireBundle, hex_offsets\n"
        "PATH=[[50,0,-50],[50,50,-50],[0,50,-50],[0,0,-50],[0,0,0]]\n"
    ),
    "hooks": "import math\nfrom pybosl2.parts.hooks import HoleType, RingHook\n",
    "polyhedra": "from pybosl2.parts.polyhedra import RegularPolyhedron, PlatonicSolid\n",
    "hinges": (
        "from pybosl2.parts.hinges import KnuckleHinge, KnuckleHingePair, LivingHingeMask, SnapLock, SnapSocket\n"
    ),
    "joiners": (
        "from pybosl2.parts.enums import Gender\nfrom pybosl2.parts.joiners import Dovetail, SnapPin, SnapPinSocket\n"
    ),
    "cubetruss": (
        "from pybosl2.parts.cubetruss import TrussSegment, Truss, TrussCorner, "
        "TrussSupport, TrussClip, TrussFoot, TrussUClip, TrussJoiner, truss_dist\n"
    ),
    "ball_bearings": "from pybosl2.parts.ball_bearings import BallBearings\n",
    "linear_bearings": "from pybosl2.parts.linear_bearings import LinearBearings\n",
    "modular_hose": "from pybosl2.parts.modular_hose import HoseSegment, HoseType\n",
    "nema_steppers": "from pybosl2.parts.nema_steppers import NemaMotor, NemaMountMask, NemaSpec\n",
    "threading": (
        "from pybosl2.parts.threading import ThreadedRod, ThreadedNut, ThreadHelix, "
        "iso_threaded_rod, iso_threaded_nut, trapezoidal_threaded_rod, acme_threaded_rod, "
        "square_threaded_rod, buttress_threaded_rod\n"
    ),
    "screw_drive": "from pybosl2.parts.screw_drive import ScrewDrive\n",
    "bottlecaps": "from pybosl2.parts.bottlecaps import BottleCaps\n",
    "sliders": "from pybosl2.parts.sliders import Sliders\n",
    "tripod_mounts": "from pybosl2.parts.tripod_mounts import ManfrottoRC2Plate, manfrotto_rc2_plate\n",
    "shapes3d": (
        "from pybosl2.solid import cyl, cuboid, sphere, cylinder\n"
        "from pybosl2.solid import prismoid, torus, tube, teardrop\n"
        "from pybosl2.solid import spheroid, octahedron\n"
        "from pybosl2.shapes3d import cone\n"
    ),
    "shapes2d": (
        "from pybosl2.shapes2d import circle, square, rect, trapezoid, star, ring, squircle, keyhole\n"
        "from pybosl2.solid import pie_slice\n"
    ),
}

VARIANTS = {
    "gears": [
        ("spur", "spur", "SpurGear(mod=4, teeth=20, thickness=8, shaft_diam=6).shape()"),
        (
            "profile-shift",
            "profile-shift",
            "SpurGear(mod=4, teeth=7, thickness=8).shape()",
        ),
        (
            "helical",
            "helical",
            "SpurGear(mod=4, teeth=20, thickness=8, helical=25, shaft_diam=6).shape()",
        ),
        (
            "herringbone",
            "herringbone",
            "SpurGear(mod=4, teeth=20, thickness=12, helical=25, herringbone=True, shaft_diam=6).shape()",
        ),
        ("rack", "rack", "Rack(mod=4, teeth=8, thickness=8, height=10).shape()"),
        (
            "ring",
            "ring gear",
            "RingGear(mod=4, teeth=24, thickness=8, backing=4).shape()",
        ),
        (
            "bevel",
            "bevel",
            "BevelGear(mod=4, teeth=20, face_width=10, pitch_angle=45, shaft_diam=6).shape()",
        ),
        ("worm", "worm", "Worm(mod=4, diameter=30, length=50, starts=1).shape()"),
    ],
    "walls": [
        ("sparse", "sparse", "SparseWall(height=50, length=100, thick=4).shape()"),
        ("corrugated", "corrugated", "CorrugatedWall(height=50, length=100, thick=5).shape()"),
        ("thinning-wall", "thinning wall", "ThinningWall(height=50, length=80, thick=4).shape()"),
        (
            "thinning-triangle",
            "thinning triangle",
            "ThinningTriangle(height=50, length=80, thick=4, center=True).shape()",
        ),
        (
            "strut",
            "narrowing strut",
            "NarrowingStrut(w=10, length=80, wall=5, angle=30).shape()",
        ),
        (
            "sparse-cuboid",
            "sparse cuboid",
            "SparseCuboid([20, 40, 30], strut=2).shape()",
        ),
    ],
    "wiring": [
        ("13", "13 wires", "WireBundle(PATH, wires=13, rounding=10).shape()"),
        ("7", "7 wires", "WireBundle(PATH, wires=7, rounding=10).shape()"),
        ("1", "1 wire", "WireBundle(PATH, wires=1, rounding=10).shape()"),
        (
            "thick",
            "thick gauge",
            "WireBundle(PATH, wires=7, wirediam=3, rounding=15).shape()",
        ),
    ],
    "hooks": [
        ("ring", "ring hole", "RingHook([50, 10], 25, outer_radius=25, inner_radius=20).shape()"),
        ("solid", "solid paddle", "RingHook([70, 10], 25, outer_radius=25, inner_radius=0).shape()"),
        ("d-hole", "D hole", "RingHook([50, 10], 25, outer_radius=25, inner_radius=15, hole=HoleType.D).shape()"),
        (
            "rounded",
            "rounded",
            "RingHook([50, 10], 40, outer_radius=25, inner_radius=15, rounding=5).shape()",
        ),
        (
            "custom",
            "custom hole",
            f"RingHook([50, 20], 30, outer_radius=25, {_HOOK_OCT}).shape()",
        ),
    ],
    "polyhedra": [
        ("tetrahedron", "tetrahedron", "RegularPolyhedron.tetrahedron(radius=15).shape()"),
        ("cube", "cube", "RegularPolyhedron.cube(radius=15).shape()"),
        ("octahedron", "octahedron", "RegularPolyhedron.octahedron(radius=15).shape()"),
        ("dodecahedron", "dodecahedron", "RegularPolyhedron.dodecahedron(side=12).shape()"),
        ("icosahedron", "icosahedron", "RegularPolyhedron.icosahedron(radius=15).shape()"),
    ],
    "hinges": [
        ("pair", "knuckle pair", "KnuckleHingePair(length=40, segs=5).shape()"),
        ("knuckle", "single leaf", "KnuckleHinge(length=40, segs=5).shape()"),
        ("snap-lock", "snap lock", "SnapLock().shape()"),
        ("snap-socket", "snap socket", "SnapSocket().shape()"),
    ],
    "joiners": [
        (
            "male",
            "male dovetail",
            "Dovetail(Gender.MALE, width=15, height=8, slide=30).shape()",
        ),
        (
            "female",
            "female socket",
            "Dovetail(Gender.FEMALE, width=15, height=8, slide=30).shape()",
        ),
        (
            "taper",
            "tapered",
            "Dovetail(Gender.MALE, width=15, height=8, slide=30, taper=4).shape()",
        ),
        ("snap-pin", "snap pin", "SnapPin().shape()"),
        ("socket", "pin socket", "SnapPinSocket().shape()"),
    ],
    "cubetruss": [
        ("truss", "3-truss", "Truss(extents=3).shape()"),
        ("segment", "segment", "TrussSegment().shape()"),
        ("corner", "corner", "TrussCorner().shape()"),
        ("support", "support", "TrussSupport(extents=1).shape()"),
        ("clip", "clip", "TrussClip().shape()"),
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
        ("segment", "segment", "HoseSegment(0.5, HoseType.SEGMENT).shape()"),
        ("ball", "ball end", "HoseSegment(0.5, HoseType.BALL).shape()"),
        ("socket", "socket end", "HoseSegment(0.5, HoseType.SOCKET).shape()"),
    ],
    "nema_steppers": [
        ("17", "NEMA 17", "NemaMotor(17).shape()"),
        ("23", "NEMA 23", "NemaMotor(23).shape()"),
        ("8", "NEMA 8", "NemaMotor(8).shape()"),
        ("mask", "mount mask", "NemaMountMask(17).shape()"),
    ],
    "threading": [
        ("iso-rod", "ISO rod", "iso_threaded_rod(d=20, l=30, pitch=2.5, fa=6, fs=1).shape()"),
        ("iso-nut", "ISO nut", "iso_threaded_nut(nutwidth=13, id=8, h=6.8, pitch=1.25).shape()"),
        (
            "trapezoidal",
            "trapezoidal rod",
            "trapezoidal_threaded_rod(d=20, l=30, pitch=4, fa=6, fs=1).shape()",
        ),
        (
            "acme",
            "ACME rod",
            "acme_threaded_rod(d=12.7, l=30, pitch=2.54, fa=6, fs=1).shape()",
        ),
    ],
    "screw_drive": [
        ("phillips", "Phillips #2", 'ScrewDrive.phillips_mask(size="#2", l=10)'),
        ("hex", "hex 3 mm", "ScrewDrive.hex_mask(size=3, l=10)"),
        ("torx", "Torx T30", "ScrewDrive.torx_mask(size=30, l=10)"),
        ("robertson", "Robertson #2", 'ScrewDrive.robertson_mask(size="#2", l=10)'),
    ],
    "bottlecaps": [
        ("pco1810-neck", "PCO 1810 neck", "BottleCaps.pco1810_neck(fa=6)"),
        ("pco1810-cap", "PCO 1810 cap", "BottleCaps.pco1810_cap(fa=6)"),
        ("pco1881-neck", "PCO 1881 neck", "BottleCaps.pco1881_neck(fa=6)"),
    ],
    "sliders": [
        ("slider", "slider", "Sliders.slider(l=30, base=10, wall=4, slop=0.2)"),
        ("rail", "rail", "Sliders.rail(l=100, w=10, h=10)"),
    ],
    "tripod_mounts": [
        ("rc2-all", "all chamfer", "ManfrottoRC2Plate().shape()"),
        ("rc2-bot", "bottom chamfer", 'ManfrottoRC2Plate(chamfer="bot").shape()'),
        ("rc2-none", "no chamfer", 'ManfrottoRC2Plate(chamfer="none").shape()'),
    ],
    "shapes3d": [
        ("cuboid", "cuboid", "cuboid([30, 20, 15])"),
        ("sphere", "sphere", "sphere(radius=15)"),
        ("cylinder", "cylinder", "cylinder(height=20, radius=8)"),
        ("cone", "cone", "cone(height=20, radius1=10, radius2=3, chamfer=1)"),
        ("prismoid", "prismoid", "prismoid(size1=[20, 20], size2=[10, 10], height=15)"),
        ("torus", "torus", "torus(major_radius=12, minor_radius=4)"),
        ("tube", "tube", "tube(height=20, outer_radius=10, inner_radius=6)"),
        ("teardrop", "teardrop", "teardrop(height=20, radius=10)"),
        ("capsule", "capsule", "spheroid(radius=12)"),
        (
            "rounded-cuboid",
            "rounded cuboid",
            "cuboid([30, 20, 15], rounding=4, edges=Anchor.Z, except_edges=TOP+FRONT+RIGHT)",
        ),
        (
            "chamfered-cylinder",
            "chamfered cyl",
            "cylinder(height=20, radius=10, chamfer=2)",
        ),
        (
            "octahedron",
            "octahedron",
            "octahedron(20)",
        ),
    ],
    "shapes2d": [
        ("circle", "circle", "circle(radius=15).linear_extrude(height=2)"),
        ("square", "square", "square(size=30).linear_extrude(height=2)"),
        ("rect", "rectangle", "rect(size=[30, 20], rounding=5).linear_extrude(height=2)"),
        ("trapezoid", "trapezoid", "trapezoid(height=30, width1=40, width2=20).linear_extrude(height=2)"),
        ("star", "star", "star(tips=5, radius=25, inner_radius=10).linear_extrude(height=2)"),
        ("ring", "ring", "ring(radius=18, ring_width=6).linear_extrude(height=2)"),
        ("pie-slice", "pie slice", "pie_slice(radius=20, angle=120, height=5)"),
        ("squircle", "squircle", "squircle(30, squareness=0.6).linear_extrude(height=2)"),
        ("keyhole", "keyhole", "keyhole(length=25, radius1=4, radius2=9).linear_extrude(height=2)"),
        (
            "rounded-square",
            "rounded square",
            "rect(size=[30, 30], rounding=8).linear_extrude(height=2)",
        ),
    ],
}


def _derive_code(expr: str) -> tuple[str, str]:
    """From a render expression, produce (plain-text code, plain-text caption)."""
    m = re.match(r"([A-Za-z_][\w]*)\.([A-Za-z_]\w*)\((.*)\)\s*$", expr, re.S)
    if not m:
        return expr, expr
    cls, method, args = m.groups()
    return f"{cls}.{method}({args})", f"{method}({args})"


def build_variant_stls(force: bool = False) -> dict:
    """Render every variant to specs/_stl/<module>-<id>.stl and measure it; cache to metrics.json.

    Returns {module: {id: {tris, vol, bbox, wt}}}.  When a cached STL already exists the
    variant is STILL re-rendered; if the new metrics differ by more than 5 % (tri count or
    volume) from the cached entry the STL and metrics are overwritten, otherwise the
    cached version is kept unchanged.  With *force* the comparison is skipped and every
    variant is unconditionally overwritten.
    """
    STL_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = STL_DIR / "metrics.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    have_app = render_object is not None and find_pythonscad_binary() is not None
    for mod, variants in VARIANTS.items():
        cache.setdefault(mod, {})
        for vid, _label, expr in variants:
            stl = STL_DIR / f"{mod}-{vid}.stl"
            cached = vid in cache[mod]
            if not force and not have_app and cached:
                continue
            if not have_app and not cached:
                print(f"  ! no app and no cache for {mod}-{vid}; viewer will show the poster")
                continue
            if not have_app:
                continue

            if not force and cached and stl.exists():
                tmp_stl = STL_DIR / f"{mod}-{vid}.tmp.stl"
                res = render_object(expr, tmp_stl, setup=SETUP[mod], timeout=240, export_format="binstl")
                if not res.ok:
                    tmp_stl.unlink(missing_ok=True)
                    print(f"  ! render FAILED {mod}-{vid}: {(res.error or '')[:120]}\nExpr: {expr}")
                    continue
                new_mm = stl_metrics(tmp_stl)
                cached_entry = cache[mod][vid]
                cached_tris = float(cached_entry["tris"])
                tris_delta = abs(float(new_mm.ntris) - cached_tris) / max(cached_tris, 1)
                try:
                    cached_vol = float(cached_entry["vol"].replace(",", ""))
                    vol_delta = abs(new_mm.volume - cached_vol) / max(cached_vol, 1.0)
                except (ValueError, ZeroDivisionError):
                    vol_delta = 1.0
                if tris_delta > 0.05 or vol_delta > 0.05:
                    tmp_stl.replace(stl)
                    size = "×".join(str(round(float(v))) for v in new_mm.size)
                    cache[mod][vid] = {
                        "tris": new_mm.ntris,
                        "vol": f"{new_mm.volume:,.1f}",
                        "bbox": size,
                        "wt": bool(new_mm.watertight),
                    }
                    print(f"  updated {mod}-{vid}: {new_mm.ntris} tris (was {cached_entry['tris']})")
                else:
                    tmp_stl.unlink()
                    print(f"  unchanged {mod}-{vid}")
                continue

            res = render_object(expr, stl, setup=SETUP[mod], timeout=240, export_format="binstl")
            if not res.ok:
                print(f"  ! render FAILED {mod}-{vid}: {res.error}")
                if res.stderr:
                    print(f"    stderr: {(res.stderr or '')[:200]}")
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


HEAD = ""

BAR = ""

MODBAR = ""

FOOT = ""


_RST_HEADER = """:icon: material/wrench-outline

.. _spec-{key}:

{title}
{underline}

.. raw:: html

    <p class="spec-lede">{subtitle}</p>

"""

_RST_VIEWER = """.. raw:: html

    <div class="spec-panel">
      <div class="spec-draw">
        <div class="spec-caption"><span id="vpart">{part}</span><span>interactive &middot; drag to orbit</span></div>
        <div class="spec-viewer" id="viewer">
          <div class="spec-poster" id="poster">{svg}</div>
        </div>
      </div>
      <div class="spec-info">
        <div class="spec-info-header">
          <h2>rendered &amp; measured</h2>
          <span class="spec-pill spec-pass" id="wtpill"{pill_style}>watertight</span>
        </div>
        <p>{note}</p>
        <div class="spec-taglabel">variants &middot; click to load</div>
        <div class="spec-tags">{tags}</div>
        <div class="spec-stats">
          <div><span class="spec-stat-v" id="s-tris">{tris0}</span><span class="spec-stat-l">triangles</span></div>
          <div><span class="spec-stat-v" id="s-vol">{vol}</span><span class="spec-stat-l">mm&sup3; volume</span></div>
          <div><span class="spec-stat-v" id="s-bbox">{bbox}</span><span class="spec-stat-l">bbox mm</span></div>
        </div>
        <div class="spec-code-wrap">
          <button class="md-clipboard md-icon" onclick="copySpecCode(this)" title="Copy to clipboard"></button>
          <div class="spec-code" id="code">&gt;&gt;&gt; {code}</div>
        </div>
        {proof_html}
        <div class="spec-tests">{tests} tests</div>
      </div>
    </div>

"""

_RST_SCRIPT = """.. raw:: html

    <script id="spec-data" type="application/json">{data}</script>
    <script type="module">
    import * as THREE from "https://esm.sh/three@0.160.0";
    import {{ STLLoader }} from "https://esm.sh/three@0.160.0/examples/jsm/loaders/STLLoader.js";
    import {{ OrbitControls }} from "https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js";

    (function() {{
      const dataEl = document.getElementById("spec-data");
      if (!dataEl) return;
      const V = JSON.parse(dataEl.textContent);
      const box = document.getElementById("viewer");
      const poster = document.getElementById("poster");
      if (!box) return;

      let renderer, scene, camera, controls, mesh, ready = false;
      const css = (n) => (getComputedStyle(document.documentElement).getPropertyValue(n) || "").trim() || null;
      const primaryColor = css("--md-accent-fg-color") || "#6f9ac9";

      function resize() {{
        const w = box.clientWidth, h = box.clientHeight || 300;
        // updateStyle must stay on: setPixelRatio() scales the drawing buffer, and without the
        // matching CSS size the canvas lays out devicePixelRatio times too large and the .spec-viewer
        // box (overflow:hidden) shows only its top-left corner.
        renderer.setSize(w, Math.max(1, h));
        camera.aspect = w / Math.max(1, h);
        camera.updateProjectionMatrix();
      }}

      function initThree() {{
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
        camera.up.set(0, 0, 1);
        renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        box.appendChild(renderer.domElement);
        scene.add(new THREE.AmbientLight(0xffffff, 0.7));
        const k = new THREE.DirectionalLight(0xffffff, 0.85);
        k.position.set(1, 0.6, 1);
        scene.add(k);
        const f = new THREE.DirectionalLight(0xffffff, 0.4);
        f.position.set(-1, -0.8, 0.5);
        scene.add(f);
        controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        window.addEventListener("resize", resize);
        ready = true;
        (function loop() {{
          requestAnimationFrame(loop);
          controls.update();
          renderer.render(scene, camera);
        }})();
      }}

      const loader = new STLLoader();
      function loadStl(uri) {{
        if (!ready) initThree();
        loader.load(uri, function(geo) {{
          if (mesh) {{ scene.remove(mesh); mesh.geometry.dispose(); }}
          geo.computeVertexNormals();
          geo.computeBoundingBox();
          const c = new THREE.Vector3();
          geo.boundingBox.getCenter(c);
          const s = new THREE.Vector3();
          geo.boundingBox.getSize(s);
          geo.translate(-c.x, -c.y, -c.z);
          mesh = new THREE.Mesh(geo,
            new THREE.MeshPhongMaterial({{ color: primaryColor, specular: 0x222222, shininess: 22 }}));
          scene.add(mesh);
          const r = Math.max(s.x, s.y, s.z) || 1;
          camera.position.set(r * 1.4, -r * 1.8, r * 1.15);
          // Depth range tied to the model: a fixed 0.01/1e6 span leaves so little depth precision
          // that big parts z-fight and shimmer while orbiting.
          camera.near = r / 100;
          camera.far = r * 100;
          camera.updateProjectionMatrix();
          controls.target.set(0, 0, 0);
          if (poster) poster.style.display = "none";
          const hint = box.querySelector(".hint");
          if (hint) hint.remove();
          resize();
        }}, undefined, function() {{
          if (!box.querySelector(".hint")) {{
            const h = document.createElement("div");
            h.className = "hint";
            h.style.cssText = (
              "position:absolute;inset:0;display:flex;align-items:center;"
              + "justify-content:center;padding:1em;color:#a00;"
              + "background:rgba(255,255,255,0.8);font-size:0.85em;"
            );
            h.textContent = "serve the docs over HTTP for the interactive 3-D view";
            box.appendChild(h);
          }}
        }});
      }}

      function selectVariant(i) {{
        const v = V[i];
        const buttons = document.querySelectorAll(".spec-tags button.spec-tag");
        buttons.forEach((b, j) => {{
          b.setAttribute("aria-selected", j === i ? "true" : "false");
          b.classList.toggle("active", j === i);
        }});
        document.getElementById("code").textContent = ">>> " + v.code;
        document.getElementById("s-tris").textContent = v.tris == null ? "—" : v.tris.toLocaleString();
        document.getElementById("s-vol").textContent = v.vol;
        document.getElementById("s-bbox").textContent = v.bbox;
        document.getElementById("vpart").textContent = v.part;
        document.getElementById("wtpill").style.display = v.wt ? "" : "none";
        loadStl(v.uri);
      }}

      const buttons = document.querySelectorAll(".spec-tags button.spec-tag");
      buttons.forEach((b, i) => {{
        b.addEventListener("click", () => {{ selectVariant(i); }});
      }});
      selectVariant(0);
    }})();
    </script>
    <script>
    function copySpecCode(btn) {{var code=btn.nextElementSibling.textContent.trim().replace(/^>>> /,'');
    navigator.clipboard.writeText(code).then(function(){{btn.title='Copied!';btn.classList.add('copied');
    setTimeout(function(){{btn.title='Copy to clipboard';btn.classList.remove('copied');}},1500);}});}}
    </script>

"""


def _to_rst_link(text: str) -> str:
    """Convert inline HTML in subtitle/note text to RST-style markup."""
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text)
    text = re.sub(r"<code>(.*?)</code>", r"``\1``", text)
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text)
    text = re.sub(r'<a href="(.*?)">(.*?)</a>', r"`\2 <\1>`_", text)
    return text


def module_page(key: str, m: dict, metrics: dict) -> str:
    variants = VARIANTS[key]
    data: list[dict] = []
    cache = metrics.get(key, {})
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
    pill_style = "" if first["wt"] else ' style="display:none"'
    tags = " ".join(f'<button class="spec-tag" type="button">{d["label"]}</button>' for d in data)
    proof_html = ""
    if m.get("proof"):
        big, txt = m["proof"]
        proof_html = (
            f'<div class="spec-proof"><div class="spec-proof-big">{big}</div>'
            f'<div class="spec-proof-txt">{txt}</div></div>'
        )

    rst_title = m["title"].replace("_", " ")
    rst_subtitle = _to_rst_link(m["subtitle"])
    rst_note = _to_rst_link(m["note"])

    header = _RST_HEADER.format(
        key=key,
        title=rst_title,
        underline="=" * len(rst_title),
        subtitle=rst_subtitle,
    )
    viewer = _RST_VIEWER.format(
        part=first["part"],
        svg=m["svg"],
        pill_style=pill_style,
        note=rst_note,
        tags=tags,
        tris0=tris0,
        vol=first["vol"],
        bbox=first["bbox"],
        code=first["code"],
        proof_html=proof_html,
        tests=m["tests"],
    )
    script = _RST_SCRIPT.format(data=spec_viewer_html(data))
    return header + viewer + script


def gallery_page() -> str:
    lines = [
        ":icon: material/tools",
        "",
        ".. _spec-index:",
        "",
        "Parts catalog",
        "=============",
        "",
        "Every mechanical part here is a pure-Python port that builds real, watertight,",
        "3-D-printable geometry through PythonSCAD. The featured modules carry a spec",
        "sheet with metrics measured straight off the exported STL.",
        "",
        ".. toctree::",
        "   :maxdepth: 1",
        "   :titlesonly:",
        "",
    ]
    for key in GALLERY:
        m = MODULES[key]
        title = m["title"].replace("_", " ")
        lines.append(f"   {title} <{key}>")
    return "\n".join(lines) + "\n"


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
    for idx, part in enumerate(re.split(r"(<script\b[^>]*>.*?</script[^>]*>)", html, flags=re.S | re.I)):
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
    metrics = build_variant_stls(force="--force" in sys.argv)
    pages = {
        "index.rst": gallery_page(),
        **{f"{k}.rst": module_page(k, m, metrics) for k, m in MODULES.items()},
    }
    for name, rst_content in pages.items():
        (OUT / name).write_text(rst_content)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
