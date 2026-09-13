#!/usr/bin/env python3
"""워드마크·락업 SVG 를 만든다.

  python3 tools/build-wordmark.py            # assets/ 에 12개 파일을 쓴다
  python3 tools/build-wordmark.py --font X   # 로컬 에이투지체 7Bold 파일로 만든다

글자는 페이지가 실제로 쓰는 에이투지체 7Bold(jsdelivr woff2)의 윤곽선을 그대로 옮긴다.
서체가 없는 곳(Figma·PPT·메일 서명·인쇄소)에서도 같은 모양이 나오게 하려는 것.
마크는 assets/mark*.svg 의 path 를 읽어 쓰므로, 마크를 고치면 이 스크립트만 다시 돌리면 된다.

비율은 문서 페이지에서 가져왔다.
  가로형 = 사이드바 로고(.ds-brand): 마크 박스 32px · 간격 12px · 글자 18px
  세로형 = 브랜드 타일(.brand-tile):  마크 박스 48px · 간격 16px · 글자 22px
간격은 CSS 가 그리는 실제 잉크 사이 거리를 재서 유지하고, 정렬만 잉크 기준으로 바꿨다
(가로형은 잉크 세로 중심, 세로형은 잉크 왼쪽 끝). 자간은 t3 와 같은 -0.01em.
"""
import argparse, io, pathlib, re, urllib.request
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.misc.transform import Transform
from fontTools.svgLib.path import parse_path

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'assets'
FONT_URL = 'https://cdn.jsdelivr.net/gh/projectnoonnu/2601-6@1.0/%EC%97%90%EC%9D%B4%ED%88%AC%EC%A7%80%EC%B2%B4-7Bold.woff2'
WORD = '가볍지이지'
TRACK = -0.01          # em
VB = 1056              # 마크 viewBox 한 변

# 색 — 마크 파일의 그라데이션과 브랜드 타일의 글자색
WAYS = {
    '':        {'stops': ('#5fe2cf', '#2ed8c3', '#0fa08d'), 'text': '#16202b', 'label': ''},
    '-dark':   {'stops': ('#93ebde', '#5fe2cf', '#2ed8c3'), 'text': '#eef1f5', 'label': ' (어두운 바탕)'},
    '-onbrand':{'stops': ('#043d36', '#06544a', '#0b7f70'), 'text': '#04211e', 'label': ' (민트 바탕)'},
    '-flat':   {'stops': None,                               'text': 'currentColor', 'label': ' (단색)'},
}

def num(v):
    s = f'{v:.1f}'.rstrip('0').rstrip('.')
    return '0' if s in ('', '-0') else s

def mark_path():
    s = (ASSETS / 'mark.svg').read_text()
    return re.search(r'<path[^>]*\sd="([^"]+)"', s).group(1)

def bounds_of_path(d):
    bp = BoundsPen(None); parse_path(d, bp); return bp.bounds   # (xmin, ymin, xmax, ymax), y 아래로

def load_font(path):
    if path:
        return TTFont(path)
    data = urllib.request.urlopen(FONT_URL, timeout=30).read()
    return TTFont(io.BytesIO(data))

def word_outline(font, size, x0, baseline):
    """글자 윤곽을 (x0, baseline) 에서 시작해 size px 로 그린다. SVG 좌표(y 아래로)."""
    gs, cmap, upem = font.getGlyphSet(), font.getBestCmap(), font['head'].unitsPerEm
    s, x, cmds = size / upem, x0, []
    bp = BoundsPen(gs)
    for i, ch in enumerate(WORD):
        g = gs[cmap[ord(ch)]]
        t = Transform(s, 0, 0, -s, x, baseline)
        sp = SVGPathPen(gs, ntos=num); g.draw(TransformPen(sp, t)); cmds.append(sp.getCommands())
        g.draw(TransformPen(bp, t))
        x += g.width * s + (TRACK * size if i < len(WORD) - 1 else 0)
    return ' '.join(cmds), bp.bounds

def css_baseline(font, size, line_height, box_top):
    """CSS 가 줄 상자 안에 놓는 베이스라인 위치."""
    upem = font['head'].unitsPerEm
    asc, desc = font['hhea'].ascent, -font['hhea'].descent
    s = size / upem
    return box_top + (size * line_height - (asc + desc) * s) / 2 + asc * s

def css_ink_gaps(font, mb):
    """문서 페이지가 그리는 그대로 배치했을 때의 잉크 간격(마크 viewBox 단위)."""
    # 가로형 — .ds-brand: 박스 32, gap 12, 18px, 줄높이 1.45, 세로 가운데
    k = 32 / VB
    base = css_baseline(font, 18, 1.45, (32 - 18 * 1.45) / 2)
    _, (tx0, _, _, _) = word_outline(font, 18, 32 + 12, base)
    gap_h = (tx0 - (mb[2] - 52) * k) / k
    # 세로형 — .brand-tile: 박스 48, gap 16, 22px, 줄높이 1.4, 왼쪽 정렬
    k = 48 / VB
    base = css_baseline(font, 22, 1.4, 48 + 16)
    _, (_, ty0, _, _) = word_outline(font, 22, 0, base)
    gap_v = (ty0 - (mb[3] - 81) * k) / k
    return gap_h, gap_v

def svg_doc(vb, title, body, defs=''):
    x0, y0, x1, y1 = vb
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{num(x0)} {num(y0)} {num(x1 - x0)} {num(y1 - y0)}" '
            f'role="img" aria-labelledby="t"><title id="t">{title}</title>{defs}{body}</svg>\n')

def grad(gid, stops):
    a, b, c = stops
    return (f'<defs><linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" y1="126" x2="0" y2="1088">'
            f'<stop offset="0" stop-color="{a}"/><stop offset="0.5" stop-color="{b}"/><stop offset="1" stop-color="{c}"/>'
            f'</linearGradient></defs>')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--font'); args = ap.parse_args()
    font = load_font(args.font)
    d = mark_path(); mb = bounds_of_path(d)
    H = mb[3] - mb[1]
    gap_h, gap_v = css_ink_gaps(font, mb)

    # 글자 크기 — 마크 viewBox 단위로 환산
    size_h = 18 * VB / 32
    size_v = 22 * VB / 48

    written = []
    for suf, w in WAYS.items():
        fill_text = w['text']

        # ── 워드마크 단독 ────────────────────────────────────────────
        wd, wb = word_outline(font, size_v, 0, 0)
        doc = svg_doc(wb, f'가볍지이지 워드마크{w["label"]}', f'<path fill="{fill_text}" d="{wd}"/>')
        written.append(('wordmark' + suf, doc))

        mark_fill = 'currentColor'; defs = ''
        # ── 가로형 ───────────────────────────────────────────────────
        gid = f'lez-lockup-h{suf}'
        if w['stops']: defs = grad(gid, w['stops']); mark_fill = f'url(#{gid})'
        _, b0 = word_outline(font, size_h, 0, 0)
        cy = (mb[1] + mb[3]) / 2
        x = mb[2] + gap_h - b0[0]
        y = cy - (b0[1] + b0[3]) / 2
        td, tb = word_outline(font, size_h, x, y)
        vb = (mb[0], min(mb[1], tb[1]), tb[2], max(mb[3], tb[3]))
        body = f'<path fill="{mark_fill}" d="{d}"/><path fill="{fill_text}" d="{td}"/>'
        written.append(('lockup-horizontal' + suf, svg_doc(vb, f'가볍지이지 가로형 로고{w["label"]}', body, defs)))

        # ── 세로형 ───────────────────────────────────────────────────
        gid = f'lez-lockup-v{suf}'
        if w['stops']: defs = grad(gid, w['stops']); mark_fill = f'url(#{gid})'
        _, b0 = word_outline(font, size_v, 0, 0)
        x = mb[0] - b0[0]
        y = mb[3] + gap_v - b0[1]
        td, tb = word_outline(font, size_v, x, y)
        vb = (min(mb[0], tb[0]), mb[1], max(mb[2], tb[2]), tb[3])
        body = f'<path fill="{mark_fill}" d="{d}"/><path fill="{fill_text}" d="{td}"/>'
        written.append(('lockup-vertical' + suf, svg_doc(vb, f'가볍지이지 세로형 로고{w["label"]}', body, defs)))

    for name, doc in written:
        (ASSETS / f'{name}.svg').write_text(doc)
        print(f'assets/{name}.svg  {len(doc.encode()):>6,} bytes')
    print(f'마크 잉크 높이 {num(H)} · 가로 간격 {num(gap_h)} ({gap_h / H:.2f}H) · 세로 간격 {num(gap_v)} ({gap_v / H:.2f}H)')

if __name__ == '__main__':
    main()
