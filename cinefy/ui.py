"""Identidade visual Frutiger Aero do Cinefy: tema CSS, ícones SVG e componentes HTML.

Validado com Streamlit 1.67. Os seletores usam `data-testid`, que muda menos entre versões
do que as classes geradas; se uma atualização quebrar algum, o app continua funcional, só
perde o acabamento vítreo daquele elemento.

Contraste (WCAG): texto branco sobre botões e hero usa tons com razão >= 4,5:1 na faixa onde
o texto aparece; o brilho especular fica só na metade superior, acima do texto.
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

# ----------------------------------------------------------------------------------------------
# Paleta (também usada pelos gráficos Plotly)
# ----------------------------------------------------------------------------------------------
AERO_INK = "#0e3b57"
AERO_MUTED = "#3e6a82"
AERO_COLORWAY = ["#168fca", "#2fc7b4", "#74d08a", "#0b4f7a", "#53d8e8", "#c5e86c", "#9bd7f5", "#e8a94a"]

# Ícones desenhados à mão em grade 24x24, traço único de 2px com pontas arredondadas.
_ICONS: dict[str, str] = {
    "overview": '<path d="M2.5 9.5c2.4-3 4.8-3 7.2 0s4.8 3 7.2 0c1.6-2 3.2-2.4 4.6-1.4"/><path d="M2.5 16c2.4-3 4.8-3 7.2 0s4.8 3 7.2 0c1.6-2 3.2-2.4 4.6-1.4"/>',
    "film": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M7.5 4v16M16.5 4v16M3 9h4.5M3 15h4.5M16.5 9H21M16.5 15H21"/>',
    "headphones": '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4.2" height="6.5" rx="1.8"/><rect x="16.8" y="14" width="4.2" height="6.5" rx="1.8"/>',
    "clapper": '<rect x="3.5" y="9.5" width="17" height="10.5" rx="2"/><path d="M3.8 9.5 5.6 4.6l4.2 1.1-1.7 3.8M9.8 5.7l4.2 1.1-1.7 2.7M14 6.8l4.2 1.1-1.5 1.6"/>',
    "mirror": '<ellipse cx="12" cy="10.5" rx="6.8" ry="7.8"/><path d="M8.6 7.6c.9-1.3 2.1-1.9 3.6-2M12 18.3V21M8.5 21h7"/>',
    "star": '<path d="m12 3.2 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5M12 14.5v2.5"/>',
    "wand": '<path d="m4 20 10.5-10.5M13 4.5l.8 1.9 1.9.8-1.9.8-.8 1.9-.8-1.9-1.9-.8 1.9-.8zM18.5 12l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6z"/>',
    "cloud": '<path d="M7 18.5a4.2 4.2 0 0 1-.6-8.3 5.6 5.6 0 0 1 10.8 1.2 3.6 3.6 0 0 1-.4 7.1z"/>',
    "bubble": '<circle cx="12" cy="12" r="8.2"/><path d="M7.6 10.2c.7-1.6 2-2.6 3.7-2.8"/>',
    "check": '<path d="m5.5 12.5 4.2 4.2 8.8-9.4"/>',
}


def icon(name: str) -> str:
    """SVG inline (traço branco) para uso dentro de um orb."""
    body = _ICONS.get(name, _ICONS["bubble"])
    return (f'<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{body}</svg>')


def orb(name: str, size: str = "md") -> str:
    """Ícone 3D: esfera vítrea com realce especular e o símbolo desenhado dentro."""
    return f'<span class="orb orb-{html.escape(size)}" aria-hidden="true">{icon(name)}</span>'


# ----------------------------------------------------------------------------------------------
# Fundo: formas orgânicas em SVG (data URI). `#` precisa virar %23 dentro de url().
# ----------------------------------------------------------------------------------------------
_BACKDROP_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 1000' preserveAspectRatio='xMidYMid slice'>"
    "<defs>"
    "<linearGradient id='sky' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%23ffffff' stop-opacity='.85'/>"
    "<stop offset='1' stop-color='%23b9ecf8' stop-opacity='.25'/></linearGradient>"
    "<linearGradient id='leaf' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%2395e6a8' stop-opacity='.55'/>"
    "<stop offset='1' stop-color='%2353d8e8' stop-opacity='.30'/></linearGradient>"
    "<linearGradient id='aqua' x1='0' y1='1' x2='1' y2='0'><stop offset='0' stop-color='%2330b4de' stop-opacity='.38'/>"
    "<stop offset='1' stop-color='%23ffffff' stop-opacity='.10'/></linearGradient>"
    "</defs>"
    "<path d='M-40 120C180 40 360 150 520 260s330 120 470 20 300-170 460-120 190 150 190 150V-40H-40z' fill='url(%23sky)'/>"
    "<path d='M-40 640C200 540 330 700 560 740s420-60 620-190 330-110 460-20v520H-40z' fill='url(%23aqua)'/>"
    "<path d='M900 1040C940 880 1080 800 1240 820s300 120 420 40v180z' fill='url(%23leaf)'/>"
    "<path d='M-40 860C120 780 300 830 420 920s150 120 150 120H-40z' fill='url(%23leaf)'/>"
    "<path d='M1180 -20C1250 90 1390 120 1500 80s140-60 140-60V-20z' fill='%23ffffff' fill-opacity='.55'/>"
    "</svg>"
)

# Bolhas: anéis translúcidos com realce, feitas só com radial-gradient.
def _bubble(x: str, y: str, size: int) -> tuple[str, str, str]:
    gradient = (
        "radial-gradient(circle at 32% 28%, rgba(255,255,255,.95) 0 7%, rgba(255,255,255,.28) 8% 58%, "
        "rgba(255,255,255,.70) 61% 64%, rgba(120,220,240,.18) 66%, transparent 69%)"
    )
    return gradient, f"{x} {y}", f"{size}px {size}px"


_BUBBLES = [
    _bubble("8%", "22%", 120), _bubble("93%", "34%", 78), _bubble("84%", "78%", 150),
    _bubble("18%", "86%", 64), _bubble("52%", "8%", 54), _bubble("66%", "58%", 38),
]

_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap');

:root {
  --aero-ink: __INK__;
  --aero-muted: __MUTED__;
  --aero-blue: #168fca;
  --aero-deep: #065a85;
  --aero-cyan: #53d8e8;
  --aero-green: #8adf9b;
  --aero-link: #066a94;
  --aero-font: 'Nunito', 'Segoe UI', 'Frutiger', 'Trebuchet MS', sans-serif;
  --glass-top: rgba(255,255,255,.86);
  --glass-bottom: rgba(255,255,255,.50);
  --rim: rgba(255,255,255,.95);
  --shadow-soft: 0 2px 4px rgba(24,110,150,.06), 0 14px 32px rgba(24,110,150,.12);
  --ease-out: cubic-bezier(.16, 1, .3, 1);
}

html, body, [class*="css"], .stApp { font-family: var(--aero-font); }
.stApp {
  color: var(--aero-ink);
  background:
    url("data:image/svg+xml;utf8,__BACKDROP__") center / cover no-repeat fixed,
    radial-gradient(ellipse at 12% 6%, rgba(255,255,255,.95) 0 3%, transparent 16%),
    linear-gradient(150deg, #e7f9ff 0%, #c4eefb 42%, #e1f7e8 100%);
  background-attachment: fixed;
}
/* Bolhas flutuando devagar: o único movimento ambiente da página. */
.stApp::before {
  content: ""; position: fixed; inset: -4%; z-index: 0; pointer-events: none;
  background-image: __BUBBLE_IMAGES__;
  background-position: __BUBBLE_POSITIONS__;
  background-size: __BUBBLE_SIZES__;
  background-repeat: no-repeat;
  animation: aero-drift 46s ease-in-out infinite alternate;
}
@keyframes aero-drift { from { transform: translate3d(0,0,0); } to { transform: translate3d(1.2%, -2.4%, 0); } }
[data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stHeader"] { position: relative; z-index: 1; }
[data-testid="stHeader"] { background: rgba(255,255,255,.35); backdrop-filter: blur(10px); }
.block-container { max-width: 1480px; padding-top: 1.6rem; padding-bottom: 3rem; }

h1, h2, h3, h4 { color: #0a5c88 !important; letter-spacing: -.03em; font-weight: 800; text-wrap: balance; }
a { color: var(--aero-link); font-weight: 700; text-underline-offset: .2em; }
::selection { background: rgba(83,216,232,.55); color: var(--aero-ink); }
input, textarea { caret-color: var(--aero-blue); }
* { scrollbar-width: thin; scrollbar-color: rgba(22,143,202,.55) rgba(255,255,255,.4); }
*::-webkit-scrollbar { width: 11px; height: 11px; }
*::-webkit-scrollbar-track { background: rgba(255,255,255,.4); border-radius: 99px; }
*::-webkit-scrollbar-thumb { background: linear-gradient(180deg,#7ad9ec,#168fca); border: 2px solid rgba(255,255,255,.7); border-radius: 99px; }
:focus-visible { outline: 3px solid #ffffff !important; outline-offset: 2px; box-shadow: 0 0 0 5px #0a6fa6 !important; border-radius: 12px; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stMetricValue"], [data-testid="stDataFrame"], .metric-value { font-variant-numeric: tabular-nums; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  min-width: 250px;
  background: linear-gradient(180deg, rgba(255,255,255,.90), rgba(188,238,249,.80) 70%, rgba(207,246,222,.78));
  border-right: 1px solid var(--rim);
  box-shadow: 8px 0 30px rgba(24,110,150,.10), inset -1px 0 0 rgba(255,255,255,.9);
  backdrop-filter: blur(14px);
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--aero-ink); }
.brand { display: flex; align-items: center; gap: 12px; margin: 2px 0 2px; }
.brand-name { font-size: 1.9rem; font-weight: 900; color: #0a5c88; letter-spacing: -.04em; }
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  border-radius: 14px; padding: 7px 12px; margin-bottom: 4px; border: 1px solid transparent;
  transition: background .25s var(--ease-out), box-shadow .25s var(--ease-out), border-color .25s var(--ease-out);
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background: rgba(255,255,255,.65); border-color: var(--rim); }
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
  background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(190,236,248,.85));
  border-color: var(--rim);
  box-shadow: inset 0 1px 0 #fff, inset 0 -3px 6px rgba(22,143,202,.12), 0 4px 10px rgba(22,143,202,.16);
}
[data-testid="stSidebar"] [data-testid="stRadio"] label p { font-weight: 700; color: var(--aero-ink); }

/* ---------- hero ---------- */
.hero {
  position: relative; overflow: hidden; display: flex; align-items: center; gap: 20px;
  padding: 26px 30px 24px; border-radius: 28px; margin: 3px 0 22px; color: #fff;
  border: 1px solid rgba(255,255,255,.9);
  background: linear-gradient(118deg, #0a5f95 0%, #0b78a9 52%, #0d7f8a 100%);
  box-shadow: 0 2px 4px rgba(10,95,149,.18), 0 18px 38px rgba(14,126,173,.26),
              inset 0 0 0 1px rgba(255,255,255,.35), inset 0 -10px 22px rgba(3,60,95,.28);
}
/* Reflexo especular curvo na metade de cima. */
.hero::before {
  content: ""; position: absolute; left: 1.5%; right: 1.5%; top: 2px; height: 46%;
  border-radius: 26px 26px 70% 70% / 26px 26px 44% 44%;
  background: linear-gradient(180deg, rgba(255,255,255,.46), rgba(255,255,255,.14) 55%, rgba(255,255,255,0));
  pointer-events: none;
}
.hero::after {
  content: ""; position: absolute; width: 260px; height: 260px; right: -50px; top: -140px; border-radius: 50%;
  background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.28);
  box-shadow: 0 0 0 24px rgba(255,255,255,.05), 0 0 0 50px rgba(255,255,255,.035); pointer-events: none;
}
.hero-text { position: relative; z-index: 1; min-width: 0; }
.hero h1 { color: #fff !important; font-size: clamp(1.6rem, 3.4vw, 2.5rem); margin: 0; font-weight: 900; line-height: 1.1;
           text-shadow: 0 2px 6px rgba(2,50,85,.45); }
.hero p { color: #fff; font-size: 1.04rem; font-weight: 600; margin: .45rem 0 0; max-width: 68ch; text-shadow: 0 1px 3px rgba(2,50,85,.5); }
.hero .orb { position: relative; z-index: 1; }

/* ---------- orb (ícone 3D) ---------- */
.orb {
  position: relative; display: inline-flex; align-items: center; justify-content: center; flex: none;
  border-radius: 50%; color: #fff; border: 1px solid rgba(255,255,255,.85);
  background:
    radial-gradient(circle at 50% 118%, rgba(143,238,172,.95), transparent 58%),
    linear-gradient(160deg, #62d6ec 0%, #138dc4 62%, #0b6a9e 100%);
  box-shadow: inset 0 -5px 9px rgba(0,70,110,.38), inset 0 3px 5px rgba(255,255,255,.75), 0 2px 3px rgba(5,80,120,.25), 0 8px 16px rgba(10,110,160,.30);
}
.orb::after {  /* realce especular */
  content: ""; position: absolute; left: 14%; right: 14%; top: 5%; height: 42%; border-radius: 50% 50% 46% 46% / 62% 62% 38% 38%;
  background: linear-gradient(180deg, rgba(255,255,255,.88), rgba(255,255,255,.08)); pointer-events: none;
}
.orb svg { position: relative; z-index: 1; width: 52%; height: 52%; filter: drop-shadow(0 1px 1.5px rgba(0,50,85,.55)); }
.orb-sm { width: 30px; height: 30px; } .orb-md { width: 46px; height: 46px; } .orb-lg { width: 64px; height: 64px; }
.hero .orb-lg { width: 66px; height: 66px; }

/* ---------- cartões de vidro ---------- */
.glass-card, .callout {
  position: relative; overflow: hidden; padding: 18px 20px; border-radius: 22px; margin-bottom: 12px;
  background: linear-gradient(150deg, var(--glass-top), var(--glass-bottom));
  border: 1px solid var(--rim);
  box-shadow: var(--shadow-soft), inset 0 0 0 1px rgba(255,255,255,.55), inset 0 -10px 18px rgba(130,215,238,.14);
  backdrop-filter: blur(14px) saturate(1.35);
}
.glass-card::before, .callout::before {  /* reflexo no topo */
  content: ""; position: absolute; left: 0; right: 0; top: 0; height: 42%;
  background: linear-gradient(180deg, rgba(255,255,255,.62), rgba(255,255,255,0)); pointer-events: none;
}
.glass-card > *, .callout > * { position: relative; }
.callout { padding: 15px 18px; border-radius: 18px; background: linear-gradient(150deg, rgba(255,255,255,.82), rgba(214,244,251,.55)); }
.card-head { display: flex; align-items: center; gap: 14px; }
.metric-label { color: var(--aero-muted); font-size: .8rem; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; }
.metric-value { color: #07557f; font-size: 1.95rem; font-weight: 900; line-height: 1.2; }
.metric-note { color: var(--aero-muted); font-size: .86rem; font-weight: 600; }
.muted { color: var(--aero-muted); }

/* st.container(border=True) vira cartão de vidro. */
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {
  position: relative; padding: 16px 18px; border-radius: 22px; border: 1px solid var(--rim) !important;
  background: linear-gradient(150deg, var(--glass-top), var(--glass-bottom));
  box-shadow: var(--shadow-soft), inset 0 0 0 1px rgba(255,255,255,.55), inset 0 -10px 18px rgba(130,215,238,.14);
  backdrop-filter: blur(14px) saturate(1.35);
}
/* Métricas dentro de um cartão não ganham outro cartão por cima. */
[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] [data-testid="stMetric"] {
  background: none; border: 0; box-shadow: none; padding: 2px 0;
}
.card-title h3 { margin: 0; padding: 0; font-size: 1.15rem; }
.card-title { margin-bottom: .5rem; }

/* ---------- badges ---------- */
.aero-pill {
  display: inline-flex; align-items: center; gap: 7px; border-radius: 999px; padding: 4px 12px; margin: 3px 4px 3px 0;
  color: #0c5170; font-size: .8rem; font-weight: 800; border: 1px solid #a9e1ef;
  background: linear-gradient(180deg, #ffffff 0%, #e6f8fd 48%, #cdeef8 52%, #e3f7fc 100%);
  box-shadow: inset 0 1px 1px #fff, inset 0 -2px 3px rgba(60,170,200,.18), 0 2px 5px rgba(37,142,170,.14);
}
.gem { width: 11px; height: 11px; border-radius: 50%; flex: none; border: 1px solid rgba(255,255,255,.9);
  background: radial-gradient(circle at 34% 28%, #fff 0 14%, transparent 30%), linear-gradient(160deg, #c4d3da, #8fa4af);
  box-shadow: inset 0 -1px 2px rgba(0,0,0,.2), 0 1px 3px rgba(0,0,0,.18); }
.gem.on { background: radial-gradient(circle at 34% 28%, #fff 0 14%, transparent 30%), linear-gradient(160deg, #8cf0a6, #1fa24f);
  box-shadow: inset 0 -1px 2px rgba(0,60,20,.35), 0 0 0 3px rgba(120,230,150,.25), 0 1px 3px rgba(0,60,20,.3); }

/* ---------- botões "gel" ---------- */
div.stButton > button, div.stDownloadButton > button, [data-testid^="stBaseLinkButton"], a[kind="primary"] {
  position: relative; overflow: hidden; min-height: 2.7rem; border-radius: 14px; font-weight: 800; color: #fff !important;
  border: 1px solid rgba(255,255,255,.92);
  background: linear-gradient(180deg, #0c75a5 0%, #09669a 50%, #065a85 52%, #0a6d9d 100%);
  text-shadow: 0 1px 2px rgba(0,45,80,.55);
  box-shadow: 0 1px 2px rgba(5,80,120,.3), 0 8px 16px rgba(14,126,173,.26),
              inset 0 0 0 1px rgba(8,100,150,.55), inset 0 -4px 8px rgba(120,225,245,.35);
  transition: transform .2s var(--ease-out), box-shadow .2s var(--ease-out), filter .2s var(--ease-out);
}
div.stButton > button::before, div.stDownloadButton > button::before, [data-testid^="stBaseLinkButton"]::before {
  content: ""; position: absolute; left: 3px; right: 3px; top: 2px; height: 36%; border-radius: 12px 12px 40% 40% / 12px 12px 55% 55%;
  background: linear-gradient(180deg, rgba(255,255,255,.40), rgba(255,255,255,.03)); pointer-events: none;
}
div.stButton > button p, div.stDownloadButton > button p { color: #fff !important; position: relative; }
div.stButton > button:hover, div.stDownloadButton > button:hover, [data-testid^="stBaseLinkButton"]:hover {
  color: #fff !important; border-color: #fff; filter: brightness(1.08) saturate(1.1); transform: translateY(-1px);
}
div.stButton > button:active, div.stDownloadButton > button:active, [data-testid^="stBaseLinkButton"]:active {
  transform: translateY(1px); filter: brightness(.96);
  box-shadow: 0 1px 2px rgba(5,80,120,.3), inset 0 3px 8px rgba(0,40,70,.45), inset 0 0 0 1px rgba(8,100,150,.55);
}
div.stButton > button:disabled { filter: grayscale(.6) opacity(.65); transform: none; }
/* Botões secundários: vidro claro, texto escuro. */
div.stButton > button[kind="secondary"], div.stDownloadButton > button[kind="secondary"] {
  color: var(--aero-ink) !important; text-shadow: none;
  background: linear-gradient(180deg, #ffffff 0%, #e4f7fc 50%, #c9edf8 52%, #def5fb 100%);
  box-shadow: 0 1px 2px rgba(5,80,120,.18), 0 6px 12px rgba(14,126,173,.14), inset 0 0 0 1px rgba(120,205,228,.8);
}
div.stButton > button[kind="secondary"] p, div.stDownloadButton > button[kind="secondary"] p { color: var(--aero-ink) !important; }
div.stButton > button[kind="secondary"]::before { background: linear-gradient(180deg, rgba(255,255,255,.9), rgba(255,255,255,.1)); }

/* ---------- componentes do Streamlit ---------- */
[data-testid="stMetric"] {
  position: relative; background: linear-gradient(150deg, rgba(255,255,255,.85), rgba(255,255,255,.52)); border: 1px solid var(--rim);
  padding: 14px 16px; border-radius: 20px; box-shadow: var(--shadow-soft), inset 0 1px 0 #fff;
}
[data-testid="stMetricLabel"] p { color: var(--aero-muted); font-weight: 800; }
[data-testid="stMetricValue"] { color: #07557f; font-weight: 900; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] > div { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; line-height: 1.15; max-width: 100%; overflow-wrap: anywhere; word-break: normal; }
[data-testid="stMetric"], [data-testid="stMetric"] > div { min-width: 0; max-width: 100%; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
  border: 1px solid var(--rim); border-radius: 16px; overflow: hidden; background: rgba(255,255,255,.72); box-shadow: var(--shadow-soft);
}
[data-testid="stExpander"] { border: 1px solid var(--rim); border-radius: 18px; background: rgba(255,255,255,.55); box-shadow: var(--shadow-soft); }
[data-testid="stAlert"] { border-radius: 16px; border: 1px solid var(--rim); box-shadow: 0 6px 16px rgba(24,110,150,.10), inset 0 1px 0 rgba(255,255,255,.8); }
[data-testid="stPlotlyChart"] { border: 1px solid var(--rim); border-radius: 20px; padding: 8px; background: linear-gradient(150deg, rgba(255,255,255,.62), rgba(255,255,255,.30)); box-shadow: var(--shadow-soft); }
[data-testid="stTabs"] button { font-weight: 800; }
[data-testid="stProgressBarTrack"] {
  background: rgba(255,255,255,.75) !important; border: 1px solid var(--rim); border-radius: 99px; overflow: hidden;
  box-shadow: inset 0 2px 4px rgba(24,110,150,.22);
}
[data-testid="stProgressBarTrack"] > div {
  background: linear-gradient(180deg, #a6f4b8 0%, #4fd07a 48%, #2fb862 52%, #62d88a 100%) !important; border-radius: 99px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.85), inset 0 -2px 3px rgba(0,90,40,.25);
}
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div {
  border-radius: 12px !important; background: rgba(255,255,255,.88) !important; border-color: rgba(120,205,228,.8) !important;
  box-shadow: inset 0 2px 4px rgba(24,110,150,.10);
}
hr { border-color: rgba(71,170,195,.22); }
img { border-radius: 14px; }

@media (max-width: 760px) {
  .block-container { padding: 3.4rem .85rem 2rem; }
  .hero { padding: 20px 18px; border-radius: 22px; gap: 14px; }
  .hero .orb-lg { width: 48px; height: 48px; }
  .hero p { font-size: .94rem; }
  .glass-card { padding: 15px; border-radius: 18px; }
  .metric-value { font-size: 1.55rem; }
  [data-testid="stMetric"] { padding: 10px 12px; }
  [data-testid="stMetricValue"] { font-size: 1.7rem; }
  div.stButton > button, div.stDownloadButton > button { min-height: 2.9rem; }
}
@media (prefers-reduced-motion: reduce) {
  .stApp::before { animation: none; }
  * { transition: none !important; }
}
</style>
"""


def _theme_css() -> str:
    images = ", ".join(item[0] for item in _BUBBLES)
    positions = ", ".join(item[1] for item in _BUBBLES)
    sizes = ", ".join(item[2] for item in _BUBBLES)
    return (_THEME_CSS
            .replace("__INK__", AERO_INK).replace("__MUTED__", AERO_MUTED)
            .replace("__BACKDROP__", _BACKDROP_SVG.replace('"', "'"))
            .replace("__BUBBLE_IMAGES__", images)
            .replace("__BUBBLE_POSITIONS__", positions)
            .replace("__BUBBLE_SIZES__", sizes))


def inject_theme() -> None:
    st.markdown(_theme_css(), unsafe_allow_html=True)


# ----------------------------------------------------------------------------------------------
# Componentes
# ----------------------------------------------------------------------------------------------
def brand_html() -> str:
    return f'<div class="brand">{orb("cloud", "md")}<span class="brand-name">Cinefy</span></div>'


def page_header(title: str, subtitle: str, icon_name: str = "bubble") -> None:
    st.markdown(
        f'<div class="hero">{orb(icon_name, "lg")}<div class="hero-text"><h1>{html.escape(title)}</h1>'
        f'<p>{html.escape(subtitle)}</p></div></div>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, note: str = "", icon_name: str | None = None) -> None:
    lead = orb(icon_name, "md") if icon_name else ""
    st.markdown(
        f'<div class="glass-card"><div class="card-head">{lead}<div>'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f'<div class="metric-note">{html.escape(note)}</div></div></div></div>',
        unsafe_allow_html=True,
    )


def card_title(icon_name: str, title: str) -> None:
    """Título de cartão com orb; use dentro de `st.container(border=True)`."""
    st.markdown(f'<div class="card-head card-title">{orb(icon_name, "sm")}<h3>{html.escape(title)}</h3></div>', unsafe_allow_html=True)


def status_pill(label: str, connected: bool) -> str:
    return f'<span class="aero-pill"><span class="gem{" on" if connected else ""}"></span>{html.escape(label)}</span>'


def aero_layout(fig: Any, **overrides: Any) -> Any:
    """Aplica o visual Aero a uma figura Plotly (fundo vítreo, fonte e paleta do app)."""
    layout: dict[str, Any] = dict(
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,.35)",
        font=dict(family="Nunito, Segoe UI, sans-serif", color=AERO_INK),
        colorway=AERO_COLORWAY,
        margin=dict(l=8, r=8, t=24, b=8),
        hoverlabel=dict(bgcolor="rgba(255,255,255,.96)", font_color=AERO_INK, bordercolor="#7ad9ec"),
    )
    layout.update(overrides)
    fig.update_layout(**layout)
    fig.update_xaxes(gridcolor="rgba(22,143,202,.14)", zerolinecolor="rgba(22,143,202,.25)")
    fig.update_yaxes(gridcolor="rgba(22,143,202,.14)", zerolinecolor="rgba(22,143,202,.25)")
    return fig
