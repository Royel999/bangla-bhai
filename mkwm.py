import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
def shape(path,text,size,x0,y0):
    blob=hb.Blob.from_file_path(path); face=hb.Face(blob); font=hb.Font(face)
    buf=hb.Buffer(); buf.add_str(text); buf.guess_segment_properties(); hb.shape(font,buf)
    tt=TTFont(path); gs=tt.getGlyphSet(); order=tt.getGlyphOrder(); upm=tt['head'].unitsPerEm; s=size/upm
    pen=SVGPathPen(gs); x=0
    for i,p in zip(buf.glyph_infos,buf.glyph_positions):
        tp=TransformPen(pen,(s,0,0,-s,x0+(x+p.x_offset)*s,y0-p.y_offset*s)); gs[order[i.codepoint]].draw(tp); x+=p.x_advance
    return pen.getCommands(),x*s
F='fonts/Galada-Regular.ttf'
a,wa=shape(F,"বাংলা",120,20,142)
b,wb=shape(F,"ভাই",120,20+wa+26,142)
W=int(20+wa+26+wb+30)
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 200" width="{W}" height="200">
<defs>
<linearGradient id="bl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b8cff"/><stop offset=".55" stop-color="#1d4ed8"/><stop offset="1" stop-color="#0b2a8a"/></linearGradient>
<linearGradient id="rd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff5a6e"/><stop offset=".6" stop-color="#c8102e"/><stop offset="1" stop-color="#7a0718"/></linearGradient>
<linearGradient id="gd" x1="0" x2="1"><stop offset="0" stop-color="#f5c542" stop-opacity="0"/><stop offset=".2" stop-color="#f5c542"/><stop offset=".5" stop-color="#fff3b0"/><stop offset=".8" stop-color="#f5c542"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></linearGradient>
<filter id="gl" x="-10%" y="-20%" width="120%" height="140%"><feGaussianBlur stdDeviation="3" result="b"/><feFlood flood-color="#22d3ee" flood-opacity=".55"/><feComposite in2="b" operator="in"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<g filter="url(#gl)">
<path d="{a}" fill="url(#bl)" stroke="#05070f" stroke-width="7" paint-order="stroke" stroke-linejoin="round"/>
<path d="{b}" fill="url(#rd)" stroke="#05070f" stroke-width="7" paint-order="stroke" stroke-linejoin="round"/>
</g>
<path d="M30 182 Q {W/2} 154 {W-25} 174" fill="none" stroke="url(#gd)" stroke-width="5" stroke-linecap="round"/>
<g transform="translate({20+wa+26+wb*0.08},6) scale(1.25)" fill="#f5c542" stroke="#7a5a00" stroke-width=".8"><path d="M0 22 L3 6 L10 15 L16 2 L22 15 L29 6 L32 22 Z"/><rect x="0" y="23" width="32" height="5" rx="1.5"/><circle cx="16" cy="2" r="2.4" fill="#c8102e"/></g>
</svg>'''
open('static/wordmark.svg','w').write(svg); print(W)
