#!/usr/bin/env python3
"""토큰 색이 종이(CMYK)에서 얼마나 달라지는지 잰다 — index.html #theme-print 의 '종이 인쇄 색' 표.

  python3 tools/print-color.py                          # macOS Generic CMYK Profile
  python3 tools/print-color.py --profile 인쇄소.icc     # 인쇄소가 준 프로파일

화면 hex → CMYK → 다시 화면색으로 되돌려 원래 색과의 차이를 CIEDE2000 으로 낸다(상대 색도).
ΔE00 < 2 그대로 나와요 · < 5 살짝 달라요 · 그 이상 탁해져요.
Generic 프로파일은 대략치다. 넓은 면적의 민트를 찍기 전에는 인쇄소 프로파일로 다시 뽑고 교정쇄로 확인한다.
"""
import argparse, math
from PIL import Image, ImageCms

def srgb_to_lab(rgb):
    def lin(c):
        c /= 255
        return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
    r, g, b = map(lin, rgb)
    X = (0.4124564*r + 0.3575761*g + 0.1804375*b) / 0.95047
    Y = (0.2126729*r + 0.7151522*g + 0.0721750*b) / 1.00000
    Z = (0.0193339*r + 0.1191920*g + 0.9503041*b) / 1.08883
    f = lambda t: t**(1/3) if t > (6/29)**3 else t/(3*(6/29)**2) + 4/29
    fx, fy, fz = f(X), f(Y), f(Z)
    return (116*fy-16, 500*(fx-fy), 200*(fy-fz))

def de2000(l1, l2):
    L1,a1,b1 = l1; L2,a2,b2 = l2
    C1, C2 = math.hypot(a1,b1), math.hypot(a2,b2)
    Cb = (C1+C2)/2
    G = 0.5*(1-math.sqrt(Cb**7/(Cb**7+25**7)))
    a1p, a2p = (1+G)*a1, (1+G)*a2
    C1p, C2p = math.hypot(a1p,b1), math.hypot(a2p,b2)
    h = lambda b,a: math.degrees(math.atan2(b,a)) % 360
    h1p, h2p = h(b1,a1p), h(b2,a2p)
    dLp, dCp = L2-L1, C2p-C1p
    dh = h2p-h1p
    if C1p*C2p == 0: dh = 0
    elif dh > 180: dh -= 360
    elif dh < -180: dh += 360
    dHp = 2*math.sqrt(C1p*C2p)*math.sin(math.radians(dh/2))
    Lbp, Cbp = (L1+L2)/2, (C1p+C2p)/2
    if C1p*C2p == 0: hbp = h1p+h2p
    elif abs(h1p-h2p) > 180: hbp = (h1p+h2p+360)/2 if h1p+h2p < 360 else (h1p+h2p-360)/2
    else: hbp = (h1p+h2p)/2
    T = 1-0.17*math.cos(math.radians(hbp-30))+0.24*math.cos(math.radians(2*hbp))+0.32*math.cos(math.radians(3*hbp+6))-0.20*math.cos(math.radians(4*hbp-63))
    dth = 30*math.exp(-((hbp-275)/25)**2)
    RC = 2*math.sqrt(Cbp**7/(Cbp**7+25**7))
    SL = 1+0.015*(Lbp-50)**2/math.sqrt(20+(Lbp-50)**2)
    SC, SH = 1+0.045*Cbp, 1+0.015*Cbp*T
    RT = -math.sin(math.radians(2*dth))*RC
    return math.sqrt((dLp/SL)**2+(dCp/SC)**2+(dHp/SH)**2+RT*(dCp/SC)*(dHp/SH))


def hx(h): return tuple(int(h[i:i+2],16) for i in (1,3,5))
def analyse(h, to_c, back):
    rgb = hx(h)
    c = ImageCms.applyTransform(Image.new('RGB',(1,1),rgb), to_c).getpixel((0,0))
    rt = ImageCms.applyTransform(Image.new('CMYK',(1,1),c), back).getpixel((0,0))
    return {'cmyk': [round(v/2.55) for v in c], 'print': '#%02x%02x%02x' % rt,
            'de': round(de2000(srgb_to_lab(rgb), srgb_to_lab(rt)), 1)}

TOKENS = [
    ('mint-50', '#e6fbf8'), ('mint-100', '#c2f4ec'), ('mint-200', '#93ebde'), ('mint-300', '#5fe2cf'),
    ('mint-400', '#2ed8c3'), ('mint-500', '#17bfa9'), ('mint-600', '#0fa08d'), ('mint-700', '#0b7f70'),
    ('mint-800', '#075e53'), ('mint-900', '#043d36'), ('on-mint 잉크', '#04211e'), ('마크 onbrand 중간', '#06544a'),
    ('grey-100', '#eef1f5'), ('grey-300', '#cbd3db'), ('grey-500', '#6e7a88'), ('grey-600', '#4c5866'), ('grey-900', '#16202b'),
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', default='/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc')
    args = ap.parse_args()

    # 자기 검증 — Sharma(2005) CIEDE2000 표준 쌍
    for a, b, exp in [((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
                      ((50, 2.5, 0), (56, -27, -3), 31.9030),
                      ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644)]:
        assert abs(de2000(a, b) - exp) < 1e-3

    srgb = ImageCms.createProfile('sRGB'); cmyk = ImageCms.getOpenProfile(args.profile)
    rel = ImageCms.Intent.RELATIVE_COLORIMETRIC
    to_c = ImageCms.buildTransform(srgb, cmyk, 'RGB', 'CMYK', renderingIntent=rel)
    back = ImageCms.buildTransform(cmyk, srgb, 'CMYK', 'RGB', renderingIntent=rel)

    print(f'프로파일: {args.profile}\n')
    print('| 토큰 | 화면 | 인쇄 예상 | CMYK | ΔE00 | 판정 |\n|---|---|---|---|---|---|')
    for name, h in TOKENS:
        r = analyse(h, to_c, back)
        word = '그대로 나와요' if r['de'] < 2 else '살짝 달라요' if r['de'] < 5 else '탁해져요'
        c = ' '.join(f'{k}{v}' for k, v in zip('CMYK', r['cmyk']))
        print(f"| {name} | `{h}` | `{r['print']}` | {c} | {r['de']} | {word} |")

if __name__ == '__main__':
    main()
