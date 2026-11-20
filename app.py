"""
De Musculatuur — AI performance assistent (web-app, v1)

Start lokaal:
    pip install streamlit pandas numpy matplotlib --break-system-packages
    streamlit run app.py

Gedeelde toegang: iedereen met de link + wachtwoord kan de tool gebruiken
(geen individuele accounts in v1 — zie roadmap voor multi-coach/login als
latere fase). Wachtwoord instellen via omgevingsvariabele DEMUSCULATUUR_PASSWORD
of via .streamlit/secrets.toml (key: APP_PASSWORD). Zonder configuratie geldt
een duidelijk zichtbaar standaardwachtwoord — wijzig dit voor echt gebruik.
"""
import os
import io
import re
import sys
import json
import time
import base64
import importlib
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
import matplotlib.dates as mdates


def _import_core():
    """Importeert core.py bestand tegen een race-conditie die de pagina leeg liet hangen.

    Streamlit bewaakt lokale modules en haalt core.py uit sys.modules zodra het bestand
    verandert. Bij een deploy valt dat samen met het opnieuw uitvoeren van dit script: de
    import-machinerie van Python vindt de module dan halverwege niet meer en gooit
    KeyError: 'core'. Het script stopt op regel 1 en de bezoeker blijft naar lege
    laad-balkjes kijken (waargenomen op Streamlit Cloud, telkens vlak na een push).
    Een nieuwe poging volstaat: dan staat sys.modules weer stabiel."""
    for _ in range(4):
        try:
            return importlib.import_module('core')
        except KeyError:
            sys.modules.pop('core', None)
            time.sleep(0.2)
    return importlib.import_module('core')


core = _import_core()


def _import_lokaal(naam):
    """Zelfde bescherming als _import_core: store.py en intake.py zijn ook lokale modules die
    Streamlit bewaakt en bij een deploy tijdelijk uit sys.modules kan halen."""
    for _ in range(4):
        try:
            return importlib.import_module(naam)
        except KeyError:
            sys.modules.pop(naam, None)
            time.sleep(0.2)
    return importlib.import_module(naam)


store = _import_lokaal('store')
intake = _import_lokaal('intake')

st.set_page_config(page_title='De Musculatuur — AI performance assistent', page_icon='static/logo.png' if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'logo.png')) else None, layout='wide')

DEFAULT_PASSWORD = 'musculatuur2026'

# ---------------------------------------------------------------------------
# Huisstijl De Musculatuur — premium, licht.
# Alle kleuren/typografie komen uit theme.py (gedeeld met intake.py en de
# prestatietest-suite), zodat elke tool exact dezelfde look heeft.
# ---------------------------------------------------------------------------
theme = _import_lokaal('theme')

DM_MAROON = theme.WINE
DM_GREEN = theme.GREEN
DM_GREEN_DARK = theme.GREEN_DARK
DM_CREAM = theme.SURFACE_2
DM_PEACH = theme.SAND
DM_BROWN = theme.TEXT
DM_MUTED = theme.MUTED
DM_BG = theme.BG


def _logo_pad():
    basis = os.path.dirname(os.path.abspath(__file__))
    for kandidaat in (os.path.join(basis, 'static', 'logo.png'), os.path.join(basis, 'logo.png')):
        if os.path.exists(kandidaat):
            return kandidaat
    return None


def _logo_b64():
    pad = _logo_pad()
    if not pad:
        return None
    with open(pad, 'rb') as f:
        return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')


_LOGO_URI = _logo_b64()
_LOGO_CSS = (f"background-image:url('{_LOGO_URI}');" if _LOGO_URI else '')

BRAND_CSS = f"""
<style>
@import url('{theme.FONT_URL}');
{theme.CSS_VARS}

/* ---------- Basis ---------- */
html, body, .stApp, [class*="css"], .stMarkdown, button, input, textarea, select,
[data-testid="stWidgetLabel"], [data-baseweb] {{
    font-family: var(--font) !important;
}}
.stApp {{ background: var(--bg); color: var(--text); }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.4rem; padding-bottom: 4rem; max-width: 1120px; }}
p, li {{ color: var(--text); line-height: 1.6; }}
strong {{ color: var(--ink); font-weight: 700; }}

h1, h2, h3, h4, h5 {{
    font-family: var(--font) !important; color: var(--wine) !important;
    font-weight: 700 !important; letter-spacing: -0.02em;
}}
h3 {{ font-size: 1.35rem !important; margin-top: .4rem !important; }}
h5 {{ font-size: 1.02rem !important; letter-spacing: -0.01em; }}
div[data-testid="stCaptionContainer"], div[data-testid="stCaptionContainer"] p, small {{
    color: var(--muted) !important; font-size: .86rem !important; line-height: 1.55;
}}
hr, [data-testid="stDivider"] hr {{ border-color: var(--line) !important; margin: 2rem 0 !important; }}
a {{ color: var(--wine); }}

/* ---------- Paginatitel & eyebrow ---------- */
.dm-page-title {{
    font-weight: 700; font-size: 2rem; line-height: 1.15; letter-spacing: -0.03em;
    color: var(--wine); margin: 0 0 .25rem 0;
}}
.dm-eyebrow {{
    font-size: .72rem; font-weight: 700; letter-spacing: .18em; text-transform: uppercase;
    color: var(--green-dark); margin-bottom: .55rem;
}}

/* ---------- Hero (startpagina + login) ---------- */
.dm-hero {{
    position: relative; overflow: hidden;
    background: var(--surface); border: 1px solid var(--line); border-radius: 28px;
    padding: 2.6rem 2.4rem 2.4rem 2.4rem; margin-bottom: 2.4rem; box-shadow: var(--shadow);
    display: flex; align-items: center; gap: 2.2rem;
}}
.dm-hero::after {{
    content: ''; position: absolute; right: -120px; top: -140px; width: 420px; height: 420px;
    border-radius: 50%; background: radial-gradient(circle, rgba(238,215,197,.55) 0%, rgba(238,215,197,0) 70%);
    pointer-events: none;
}}
.dm-hero-logo {{
    width: 132px; height: 132px; min-width: 132px; {_LOGO_CSS}
    background-size: contain; background-repeat: no-repeat; background-position: center;
    mix-blend-mode: multiply; position: relative; z-index: 1;
}}
.dm-hero-body {{ position: relative; z-index: 1; }}
.dm-hero-sub {{
    font-weight: 700; font-size: 2.35rem; line-height: 1.08; letter-spacing: -0.035em; color: var(--wine);
}}
.dm-hero-desc {{ color: var(--brown); font-size: 1.05rem; margin-top: .6rem; max-width: 560px; line-height: 1.55; }}
.dm-hero.center {{ flex-direction: column; text-align: center; gap: 1rem; padding: 2.8rem 2rem; }}
.dm-hero.center .dm-hero-desc {{ margin-left: auto; margin-right: auto; }}

/* ---------- Kaarten ---------- */
.dm-card {{
    background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 1.5rem 1.6rem; box-shadow: var(--shadow); margin-bottom: .9rem;
}}
.dm-card-title {{
    font-weight: 700; font-size: 1.12rem; letter-spacing: -0.015em; color: var(--wine); margin-bottom: .9rem;
}}
.dm-bullet-list {{ margin: 0; padding-left: 1.1rem; }}
.dm-bullet-list li {{ color: var(--text); line-height: 1.6; margin-bottom: .45rem; }}
.dm-bullet-list li::marker {{ color: var(--green); }}
.dm-bullet-list strong {{ color: var(--wine); }}

/* ---------- Lege staat ---------- */
.dm-empty-state {{
    background: var(--surface); border: 1px dashed var(--line-strong); border-radius: 24px;
    padding: 3.6rem 2rem; text-align: center;
}}
.dm-empty-icon {{
    width: 52px; height: 52px; margin: 0 auto 1rem auto; border-radius: 16px; background: var(--surface-2);
    display: flex; align-items: center; justify-content: center; color: var(--wine);
}}
.dm-empty-title {{ color: var(--wine); font-size: 1.25rem; font-weight: 700; margin-bottom: .45rem; letter-spacing: -0.02em; }}
.dm-empty-desc {{ color: var(--muted); font-size: .95rem; max-width: 460px; margin: 0 auto; line-height: 1.6; }}
.dm-empty-desc strong {{ color: var(--wine); }}

/* ---------- Sidebar (licht) ---------- */
section[data-testid="stSidebar"] {{
    background: var(--surface) !important; border-right: 1px solid var(--line);
}}
section[data-testid="stSidebar"] > div {{ padding-top: .4rem; }}
section[data-testid="stSidebar"] .dm-sidebar-section {{
    font-size: .7rem; font-weight: 700; letter-spacing: .18em; text-transform: uppercase;
    color: var(--muted); margin: .2rem 0 .75rem 0;
}}
section[data-testid="stSidebar"] .dm-step {{
    font-size: .8rem; font-weight: 700; color: var(--text); margin: 1rem 0 .35rem 0;
}}
.dm-sidebar-divider {{ height: 1px; background: var(--line); margin: 1.3rem 0; border: none; }}

/* ---------- Topbalk ---------- */
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {{ display: none !important; }}
.st-key-topbar {{
    background: rgba(255,255,255,.92); backdrop-filter: blur(8px); border: 1px solid var(--line); border-radius: 999px;
    padding: .35rem .55rem .35rem .9rem; box-shadow: var(--shadow); margin: -1rem 0 1.8rem; position: sticky; top: .7rem; z-index: 50;
}}
.st-key-logo_home button, .st-key-logo_home button:hover, .st-key-logo_home button:focus, .st-key-logo_home button:active {{
    {_LOGO_CSS} background-color: transparent !important; background-size: contain !important;
    background-repeat: no-repeat !important; background-position: left center !important; mix-blend-mode: multiply;
    border: none !important; box-shadow: none !important; padding: 0 !important;
    width: 56px !important; height: 56px !important; min-height: 56px !important;
}}
.st-key-logo_home button p {{ font-size: 0 !important; }}
.st-key-logo_home button:hover {{ opacity: .8; }}
.st-key-nav_atleten button, .st-key-nav_uit button, .st-key-topbar [data-testid="stPopover"] button {{
    background: transparent !important; border: none !important; color: var(--muted) !important; min-height: 2.4rem !important;
}}
.st-key-nav_atleten button:hover, .st-key-nav_uit button:hover, .st-key-topbar [data-testid="stPopover"] button:hover {{
    background: var(--surface-2) !important; color: var(--wine) !important;
}}
.st-key-nav_uit button p {{ font-weight: 600 !important; font-size: .82rem !important; }}
.st-key-switcher [data-testid="stPopover"] button {{
    background: #fff !important; border: 1px solid var(--line-strong) !important; color: var(--ink) !important;
    padding: .25rem 1rem .25rem .3rem !important; justify-content: flex-start !important;
}}
.st-key-switcher button p {{ display: flex !important; align-items: center; gap: .6rem; font-weight: 700 !important;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.st-key-switcher button p::before {{
    width: 30px; height: 30px; min-width: 30px; border-radius: 50%; background: var(--sand); color: var(--wine);
    display: inline-flex; align-items: center; justify-content: center; font-size: .72rem; font-weight: 800;
}}
[data-testid="stPopoverBody"] {{ border-radius: 16px !important; border: 1px solid var(--line) !important; box-shadow: var(--shadow-hover) !important; }}
[data-testid="stPopoverBody"] .stButton > button {{ justify-content: flex-start !important; border: none !important; background: transparent !important;
    font-weight: 600 !important; padding: .5rem .7rem !important; }}
[data-testid="stPopoverBody"] .stButton > button:hover {{ background: var(--surface-2) !important; color: var(--wine) !important; }}
[data-testid="stPopoverBody"] .stButton > button[kind="primary"] {{ justify-content: center !important; background: var(--green) !important; color: #fff !important; }}
.dm-pop-t {{ font-size: .68rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: var(--muted); margin: .1rem 0 .3rem .4rem; }}
.dm-pop-sep {{ height: 1px; background: var(--line); margin: .3rem 0 .5rem; }}

/* ---------- Atletenlijst ---------- */
.dm-roster-head {{ display: grid; grid-template-columns: 2.3fr 1fr 1.9fr 2.6fr .95fr; gap: 1rem; padding: .8rem 1.1rem .4rem;
    font-size: .66rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }}
[class*="st-key-rij_"] {{ background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: .55rem 1.1rem;
    margin-bottom: .1rem; box-shadow: var(--shadow); transition: box-shadow .15s ease, border-color .15s ease; }}
[class*="st-key-rij_"]:hover {{ box-shadow: var(--shadow-hover); border-color: var(--line-strong); }}
[class*="st-key-rij_"] p {{ margin: 0 !important; }}
.dm-who {{ display: flex; align-items: center; gap: .75rem; color: var(--ink); }}
.dm-who .dm-avatar {{ width: 36px; height: 36px; font-size: .78rem; flex: none; }}
.dm-cell {{ font-size: .9rem; color: var(--text); }}
.dm-muted {{ color: var(--faint); }}
.dm-chips {{ display: flex; gap: .35rem; flex-wrap: wrap; }}
.dm-chip {{ font-size: .72rem; font-weight: 700; border-radius: 999px; padding: .2rem .6rem; background: var(--surface-2); color: var(--faint); white-space: nowrap; }}
.dm-chip.ok {{ background: var(--green-soft); color: var(--ok); }}

/* ---------- Knoppen ---------- */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {{
    border-radius: 999px !important; font-weight: 700 !important; font-size: .9rem !important;
    padding: .55rem 1.35rem !important; min-height: 2.6rem;
    background: var(--surface) !important; color: var(--text) !important;
    border: 1px solid var(--line-strong) !important; box-shadow: none !important;
    transition: background .15s ease, border-color .15s ease, transform .15s ease;
}}
.stButton > button p, .stDownloadButton > button p, [data-testid="stFormSubmitButton"] > button p {{
    font-weight: 700 !important; color: inherit !important;
}}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {{
    border-color: var(--wine) !important; color: var(--wine) !important;
}}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"],
.stDownloadButton > button[kind="primary"] {{
    background: var(--green) !important; border-color: var(--green) !important; color: #FFFFFF !important;
}}
.stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:hover {{
    background: var(--green-dark) !important; border-color: var(--green-dark) !important; color: #FFFFFF !important;
    transform: translateY(-1px);
}}
.stButton > button:disabled, .stButton > button:disabled:hover {{
    background: var(--surface-2) !important; color: var(--muted) !important;
    border-color: var(--line) !important; opacity: 1 !important; transform: none !important;
}}
.stButton > button:disabled p {{ color: var(--muted) !important; }}

/* ---------- Invoervelden ---------- */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], [data-baseweb="base-input"] {{
    background: var(--surface) !important; border-radius: var(--radius-sm) !important;
    border-color: var(--line-strong) !important;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {{
    border-color: var(--green) !important; box-shadow: 0 0 0 3px rgba(99,185,149,.18) !important;
}}
input, textarea {{ color: var(--ink) !important; }}
[data-testid="stWidgetLabel"] p {{ font-weight: 700 !important; font-size: .82rem !important; color: var(--text) !important; }}

[data-testid="stFileUploaderDropzone"] {{
    background: var(--surface-2) !important; border: 1px dashed var(--line-strong) !important;
    border-radius: 16px !important; padding: 1rem !important; transition: border-color .15s ease, background .15s ease;
}}
[data-testid="stFileUploaderDropzone"]:hover {{ border-color: var(--green) !important; background: var(--green-soft) !important; }}
[data-testid="stFileUploaderDropzone"] button {{
    background: var(--surface) !important; color: var(--text) !important;
    border: 1px solid var(--line-strong) !important; border-radius: 999px !important;
}}

/* ---------- Tabs, expanders, meldingen, tabellen ---------- */
.stTabs [data-baseweb="tab-list"] {{ gap: .25rem; border-bottom: 1px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{
    font-weight: 500; color: var(--muted); padding: .55rem .9rem; background: transparent;
}}
.stTabs [data-baseweb="tab"] p {{ font-weight: 600 !important; font-size: .9rem !important; }}
.stTabs [aria-selected="true"] {{ color: var(--wine) !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: var(--wine) !important; height: 2px; }}
.stTabs [data-baseweb="tab-border"] {{ display: none; }}

[data-testid="stExpander"] details {{
    background: var(--surface); border: 1px solid var(--line) !important; border-radius: var(--radius) !important;
}}
[data-testid="stExpander"] summary p {{ font-weight: 700 !important; color: var(--text) !important; }}

div[data-testid="stAlert"] {{ border-radius: 14px; border: 1px solid var(--line); }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{
    border: 1px solid var(--line); border-radius: 14px; overflow: hidden; background: var(--surface);
}}
[data-testid="stMetric"] {{
    background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 1rem 1.2rem;
}}
[data-testid="stMetricValue"] {{ color: var(--wine); font-weight: 700; letter-spacing: -0.02em; }}
[data-testid="stRadio"] label p {{ font-size: .9rem; }}

/* ---------- Trainingsadvies ---------- */
.dm-advies-item {{
    border-radius: 14px; padding: .95rem 1.1rem; margin-bottom: .6rem; background: var(--surface-2);
}}
.dm-advies-item:last-child {{ margin-bottom: 0; }}
.dm-advies-title {{ font-weight: 700; font-size: .95rem; margin-bottom: .25rem; display: flex; align-items: center; gap: .55rem; }}
.dm-advies-title::before {{ content: ''; width: 8px; height: 8px; border-radius: 50%; background: currentColor; flex: none; }}
.dm-advies-text {{ font-size: .9rem; line-height: 1.6; color: var(--text); }}
.dm-advies-alert {{ background: {theme.ALERT_SOFT}; }}  .dm-advies-alert .dm-advies-title {{ color: var(--alert); }}
.dm-advies-warning {{ background: {theme.WARN_SOFT}; }} .dm-advies-warning .dm-advies-title {{ color: var(--warn); }}
.dm-advies-positive {{ background: {theme.OK_SOFT}; }}  .dm-advies-positive .dm-advies-title {{ color: var(--ok); }}
.dm-advies-info {{ background: {theme.INFO_SOFT}; }}    .dm-advies-info .dm-advies-title {{ color: {theme.INFO}; }}

/* ---------- Jaarplanning ---------- */
.dm-plan-block {{
    position: relative; border: 1px solid var(--line); border-radius: 16px; padding: 1.1rem 1.25rem 1.1rem 1.5rem;
    margin-bottom: .7rem; background: var(--surface);
}}
.dm-plan-block::before {{
    content: ''; position: absolute; left: 0; top: 14px; bottom: 14px; width: 3px; border-radius: 0 3px 3px 0;
    background: var(--phase, var(--line-strong));
}}
.dm-plan-block:last-child {{ margin-bottom: 0; }}
.dm-plan-header {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: .5rem; }}
.dm-plan-fase {{ font-weight: 700; font-size: 1.02rem; color: var(--ink); letter-spacing: -0.01em; }}
.dm-plan-dates {{ font-size: .8rem; color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }}
.dm-plan-meta {{ font-size: .8rem; color: var(--brown); margin-top: .2rem; font-weight: 600; }}
.dm-plan-focus {{ font-size: .9rem; color: var(--text); margin-top: .4rem; line-height: 1.6; }}
.dm-plan-note {{ font-size: .84rem; color: var(--wine); margin-top: .5rem; }}
.dm-plan-transitie {{ --phase: #B4A399; }}
.dm-plan-basis1, .dm-plan-basis2, .dm-plan-basis3 {{ --phase: #D9B48F; }}
.dm-plan-opbouw1, .dm-plan-opbouw2 {{ --phase: {theme.GREEN}; }}
.dm-plan-piek {{ --phase: #9A4A3A; }}
.dm-plan-taper_afbouw, .dm-plan-wedstrijdweek {{ --phase: {theme.WINE}; }}
.dm-volbar {{
    position: relative; height: 22px; border-radius: 999px; background: var(--surface-2);
    margin: .6rem 0 .45rem 0; overflow: hidden;
}}
.dm-volbar-fill {{ height: 100%; background: var(--phase, var(--green)); opacity: .35; border-radius: 999px; }}
.dm-volbar-lbl {{
    position: absolute; left: 11px; top: 0; line-height: 22px; font-size: .72rem; font-weight: 700; color: var(--text);
}}
.dm-cyc {{
    margin-top: .7rem; padding: .7rem .9rem; background: var(--surface-2); border-radius: 12px;
}}
.dm-cyc-kop {{
    display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: .4rem;
    font-size: .72rem; font-weight: 700; color: var(--wine); text-transform: uppercase; letter-spacing: .1em;
}}
.dm-cyc-dates {{ font-weight: 500; color: var(--muted); text-transform: none; letter-spacing: 0; font-variant-numeric: tabular-nums; }}
.dm-cyc-ritme {{ display: block; font-size: .78rem; color: var(--muted); margin-top: .2rem; }}
.dm-cyc-acties {{ margin: .5rem 0 0 0; padding-left: 1.05rem; }}
.dm-cyc-acties li {{ font-size: .87rem; line-height: 1.55; color: var(--text); margin-bottom: .3rem; }}
.dm-cyc-acties li::marker {{ color: var(--green); }}
.dm-cyc-acties li:last-child {{ margin-bottom: 0; }}
.dm-goal-chip {{
    display: inline-flex; align-items: center; gap: .5rem; background: var(--surface);
    border: 1px solid var(--line-strong); border-radius: 999px; padding: .4rem .95rem; margin: 0 .4rem .4rem 0;
    font-size: .85rem; font-weight: 600; color: var(--wine);
}}
.dm-goal-chip::before {{ content: ''; width: 7px; height: 7px; border-radius: 50%; background: var(--green); }}

/* ---------- Tool-tegels ---------- */
[class*="st-key-tile_"] {{
    background: var(--surface); border: 1px solid var(--line); border-radius: 22px;
    padding: 1.45rem 1.45rem 1.3rem; box-shadow: var(--shadow); height: 258px; overflow: hidden;
    display: flex; flex-direction: column; gap: 0 !important; transition: box-shadow .2s ease, transform .2s ease;
}}
[class*="st-key-tile_"]:hover {{ box-shadow: var(--shadow-hover); transform: translateY(-2px); }}
[class*="st-key-tile_"] > div:last-child {{ margin-top: auto; }}
[class*="st-key-tile_"] .stButton > button {{ width: 100%; }}
.dm-tool-head {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.1rem; }}
.dm-tool-icon {{
    width: 46px; height: 46px; border-radius: 14px; background: var(--surface-2); color: var(--wine);
    display: flex; align-items: center; justify-content: center;
}}
.dm-tool-nr {{ font-size: .75rem; font-weight: 700; color: var(--faint); letter-spacing: .1em; font-variant-numeric: tabular-nums; }}
.dm-tool-title {{ color: var(--ink); font-size: 1.15rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: .35rem;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.dm-tool-desc {{ color: var(--muted); font-size: .9rem; line-height: 1.55; height: 2.79rem; overflow: hidden;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
.dm-tool-link {{
    display: flex; align-items: center; justify-content: center; text-decoration: none !important;
    background: var(--surface); color: var(--text) !important; border: 1px solid var(--line-strong);
    border-radius: 999px; font-weight: 700; font-size: .9rem; min-height: 2.6rem; padding: .55rem 1.35rem;
    transition: border-color .15s ease, color .15s ease;
}}
.dm-tool-link:hover {{ border-color: var(--wine); color: var(--wine) !important; }}

/* ---------- Belastbaarheid-readout ---------- */
.dm-bel-readout {{
    background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 1.2rem 1.5rem; box-shadow: var(--shadow); display: flex; align-items: center; gap: 1.8rem; flex-wrap: wrap;
}}
.dm-bel-readout > div:first-child {{ padding-right: 1.8rem; border-right: 1px solid var(--line); }}
.dm-bel-value {{ font-size: 2.4rem; font-weight: 700; color: var(--ok); line-height: 1; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }}
.dm-bel-readout.warn .dm-bel-value {{ color: var(--warn); }}
.dm-bel-readout.alert .dm-bel-value {{ color: var(--alert); }}
.dm-bel-readout.none .dm-bel-value {{ color: var(--muted); }}
.dm-bel-label {{ font-size: .68rem; letter-spacing: .16em; text-transform: uppercase; color: var(--muted); font-weight: 700; margin-bottom: .35rem; }}
.dm-bel-status {{ font-size: .98rem; font-weight: 700; color: var(--ink); }}
.dm-bel-readout.none > div:first-child {{ border: none; padding-right: 0; }}
.dm-bel-meta {{ font-size: .82rem; color: var(--muted); margin-top: .2rem; }}
/* ---------- Atleten & dashboard ---------- */
.dm-card-sub {{ font-size: .78rem; font-weight: 500; color: var(--muted); margin-left: .6rem; letter-spacing: 0; }}
.dm-card-note {{ background: #FCF8F5; }}
.dm-kv {{ display: grid; grid-template-columns: 1fr; gap: .85rem; }}
.dm-kv-item {{ border-top: 1px solid var(--line); padding-top: .75rem; }}
.dm-kv-item:first-child {{ border-top: none; padding-top: 0; }}
.dm-kv-k {{ font-size: .68rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin-bottom: .25rem; }}
.dm-kv-v {{ font-size: .92rem; color: var(--text); line-height: 1.6; }}
.dm-stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: .9rem; margin: 1.4rem 0 1.1rem 0; }}
@media (max-width: 900px) {{ .dm-stats {{ grid-template-columns: repeat(2, 1fr); }} }}
.dm-stat {{ background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 1.05rem 1.2rem; box-shadow: var(--shadow); }}
.dm-stat-label {{ font-size: .68rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }}
.dm-stat-value {{ font-size: 1.9rem; font-weight: 700; letter-spacing: -0.03em; color: var(--ink); margin: .3rem 0 .15rem; font-variant-numeric: tabular-nums; }}
.dm-stat.ok .dm-stat-value {{ color: var(--ok); }} .dm-stat.warn .dm-stat-value {{ color: var(--warn); }} .dm-stat.alert .dm-stat-value {{ color: var(--alert); }}
.dm-stat-meta {{ font-size: .8rem; color: var(--muted); line-height: 1.4; min-height: 1.1em; }}
.dm-profile-head {{ display: flex; align-items: center; gap: 1.2rem; }}
.dm-profile-meta {{ color: var(--brown); font-size: .95rem; margin-top: .15rem; }}
.dm-avatar {{ width: 44px; height: 44px; border-radius: 50%; background: var(--sand); color: var(--wine);
    display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: .95rem; letter-spacing: .02em; }}
.dm-avatar.lg {{ width: 68px; height: 68px; font-size: 1.35rem; flex: none; }}
.dm-athlete-card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 20px; padding: 1.3rem 1.3rem 1.2rem;
    box-shadow: var(--shadow); min-height: 176px; transition: box-shadow .2s ease, transform .2s ease; }}
.dm-athlete-card:hover {{ box-shadow: var(--shadow-hover); transform: translateY(-2px); }}
.dm-athlete-name {{ font-weight: 700; font-size: 1.08rem; color: var(--ink); letter-spacing: -0.015em; margin-top: .85rem; }}
.dm-athlete-meta {{ font-size: .82rem; color: var(--muted); margin-top: .1rem; }}
.dm-athlete-goal {{ font-size: .87rem; color: var(--text); margin-top: .6rem; line-height: 1.5; }}
.dm-kv-grid {{ grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }}
.dm-kv-grid .dm-kv-item {{ border-top: none; padding-top: 0; }}
.dm-zones {{ width: 100%; border-collapse: collapse; margin-top: 1.1rem; font-size: .86rem; }}
.dm-zones th {{ text-align: left; font-size: .68rem; letter-spacing: .12em; text-transform: uppercase; color: var(--muted);
    font-weight: 700; padding: .45rem .6rem; border-bottom: 1px solid var(--line); }}
.dm-zones td {{ padding: .5rem .6rem; border-bottom: 1px solid var(--line); color: var(--text); font-variant-numeric: tabular-nums; }}
.dm-zones tr:last-child td {{ border-bottom: none; }}
[data-testid="stCustomComponentV1"], iframe[title^="dm_prestatietest"] {{ border: none; }}
.dm-traject {{ display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; background: var(--surface);
    border: 1px solid var(--line); border-radius: 999px; padding: .45rem .5rem .45rem 1.2rem; margin: .4rem 0 1.4rem; box-shadow: var(--shadow); }}
.dm-traject-who {{ font-size: .72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }}
.dm-tsteps {{ display: flex; gap: .3rem; flex: 1; flex-wrap: wrap; }}
.dm-tstep {{ display: flex; align-items: center; gap: .5rem; padding: .4rem .85rem; border-radius: 999px; font-size: .85rem;
    font-weight: 600; color: var(--muted); }}
.dm-tstep small {{ font-size: .68rem; font-weight: 500; margin-left: .35rem; color: var(--faint); }}
.dm-tstep .n {{ width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: .72rem; font-weight: 700; background: var(--surface-2); color: var(--muted); }}
.dm-tstep.done {{ color: var(--text); }}
.dm-tstep.done .n {{ background: var(--green-soft); color: var(--ok); }}
.dm-tstep.active {{ background: var(--wine); color: #fff; }}
.dm-tstep.active small {{ color: rgba(255,255,255,.7); }}
.dm-tstep.active .n {{ background: #fff; color: var(--wine); }}
.dm-cta {{ border-left: 4px solid var(--green); }}
</style>
"""


def inject_brand_css():
    st.markdown(BRAND_CSS, unsafe_allow_html=True)


def _logo_data_uri():
    return _LOGO_URI


def render_logo(tagline='RECOVERY & PERFORMANCE', clickable=True):
    """Het echte logo bovenaan de sidebar, tevens de weg terug naar het overzicht.

    Bewust een Streamlit-knop en geen <a href>: een echte link herlaadt de pagina, waardoor
    Streamlit een nieuwe sessie start (coach uitgelogd, analyses kwijt). De knop wordt via CSS
    (.st-key-logo_home) omgevormd tot het logo zelf; de tekst is enkel voor schermlezers."""
    if clickable:
        if st.button('De Musculatuur — naar overzicht', key='logo_home', help='Terug naar alle tools'):
            goto(PAGE_HOME)
    else:
        st.markdown('<div class="dm-logo-static" role="img" aria-label="De Musculatuur"></div>',
                    unsafe_allow_html=True)


def render_hero(subtitle, desc, eyebrow='Coach platform', center=False, logo=None):
    """Rustig, licht hero-blok — startpagina en login. Het logo staat standaard enkel in de
    gecentreerde (login-)variant; op de startpagina staat het al in de sidebar."""
    klasse = 'dm-hero center' if center else 'dm-hero'
    toon_logo = center if logo is None else logo
    logo_html = '<div class="dm-hero-logo" role="img" aria-label="De Musculatuur"></div>' if toon_logo else ''
    st.markdown(
        f'<div class="{klasse}">{logo_html}'
        f'<div class="dm-hero-body"><div class="dm-eyebrow">{eyebrow}</div>'
        f'<div class="dm-hero-sub">{subtitle}</div><div class="dm-hero-desc">{desc}</div></div></div>',
        unsafe_allow_html=True)


def page_header(titel, ondertitel=None, eyebrow=None):
    """Uniforme paginakop voor elke tool."""
    html = f'<div class="dm-eyebrow">{eyebrow}</div>' if eyebrow else ''
    html += f'<div class="dm-page-title">{titel}</div>'
    st.markdown(html, unsafe_allow_html=True)
    if ondertitel:
        st.caption(ondertitel)


def md_bold_to_html(text):
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)


# ---------------------------------------------------------------------------
# Navigatie: welkomstpagina met tool-tegels, daarachter de losse tools.
# Bewust eigen routing via session_state i.p.v. Streamlit's multipage-mechanisme:
# dat laatste zet z'n eigen paginanavigatie in de sidebar, wat botst met de
# huisstijl-sidebar hieronder.
# ---------------------------------------------------------------------------
PAGE_HOME = 'home'
PAGE_ATLETEN = 'atleten'
PAGE_INTAKE = 'intake'
PAGE_BELASTBAARHEID = 'belastbaarheid'
PAGE_JAARPLANNING = 'jaarplanning'
PAGE_DASHBOARD = 'dashboard'

PAGE_TESTEN = 'testen'
PAGE_VOEDING = 'voeding'

# De prestatietest-suite (lactaat, CP, CSS, looptest, voeding) is een uitgebreide HTML/JS-tool.
# Ze draait als Streamlit-component binnen de app: zelfde zijbalk, login en actieve atleet.
# De rekenlogica blijft ongewijzigd in components/prestatietest/index.html; de "brug" onderaan
# dat bestand krijgt de atleet binnen en stuurt bij "Bewaren bij atleet" de test terug.
_suite_component = _import_lokaal('suite').component
_verslag_component = _import_lokaal('suite').verslag

TOOLS = [
    {'key': PAGE_ATLETEN, 'icon': 'atleten', 'titel': 'Atleten',
     'desc': 'Eén dashboard per atleet: intake, belastbaarheid, planning en testen samen.'},
    {'key': PAGE_INTAKE, 'icon': 'intake', 'titel': 'Intake',
     'desc': 'Opname van het gesprek wordt uitgeschreven en een verslag in de huisstijl.'},
    {'key': PAGE_BELASTBAARHEID, 'icon': 'analyse', 'titel': 'Belastbaarheid',
     'desc': 'Trainingslast en A:C ratio uit Strava, met trend, blinde vlekken en advies.'},
    {'key': PAGE_JAARPLANNING, 'icon': 'planning', 'titel': 'Jaarplanning',
     'desc': 'Opbouw per A-doel terugwerkend vanaf de wedstrijd, afgestemd op de belasting.'},
    {'key': PAGE_TESTEN, 'icon': 'test', 'titel': 'Prestatietesten',
     'desc': 'Lactaat, Critical Power, CSS en looptest, met zones en printbaar verslag.'},
    {'key': PAGE_VOEDING, 'icon': 'voeding', 'titel': 'Voedingsplan',
     'desc': 'Wedstrijdvoeding per minuut: koolhydraten, vocht en zout op maat.'},
]


# Lijn-iconen (1.6px stroke, currentColor) i.p.v. emoji — rustiger en professioneler.
_SVG = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{}</svg>'
ICONS = {
    'atleten': _SVG.format('<circle cx="12" cy="8" r="3.6"/><path d="M4.5 20c1.2-3.6 4.1-5.4 7.5-5.4s6.3 1.8 7.5 5.4"/>'),
    'intake': _SVG.format('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>'),
    'analyse': _SVG.format('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'),
    'planning': _SVG.format('<rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4M8 14h3M8 17h6"/>'),
    'test': _SVG.format('<path d="M3 13h3.5l2.5-6 4 12 2.8-8.5L17.5 13H21"/>'),
    'voeding': _SVG.format('<path d="M7 3v8a3 3 0 0 0 6 0V3M10 3v18M17 3c-1.7 1.3-2.5 3.6-2.5 6.5V13h2.5v8"/>'),
    'upload': _SVG.format('<path d="M12 16V4M7 9l5-5 5 5M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16"/>'),
}


def goto(page):
    st.session_state['page'] = page
    st.rerun()


def current_page():
    return st.session_state.get('page', PAGE_HOME)


def render_tools_grid():

    for row_start in range(0, len(TOOLS), 3):
        cols = st.columns(3, gap='medium')
        for i, (col, tool) in enumerate(zip(cols, TOOLS[row_start:row_start + 3])):
            nr = row_start + i + 1
            with col:
                # Eén container per tegel (vaste hoogte via CSS .st-key-tile_*), zodat elke tegel exact
                # even groot is en de knop onderaan in de tegel zelf staat.
                with st.container(key=f"tile_{tool['key']}"):
                    st.markdown(
                        f'<div class="dm-tool-head"><div class="dm-tool-icon">{ICONS.get(tool["icon"], "")}</div>'
                        f'<div class="dm-tool-nr">{nr:02d}</div></div>'
                        f'<div class="dm-tool-title">{tool["titel"]}</div>'
                        f'<div class="dm-tool-desc">{tool["desc"]}</div>', unsafe_allow_html=True)
                    if st.button('Openen', key=f"open_{tool['key']}", use_container_width=True):
                        goto(tool['key'])
        st.markdown('<div style="height:.35rem"></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Navigatie zonder zijbalk: vaste topbalk (logo · Atleten · Losse tools · atleet-wisselaar)
# en de atletenlijst als startpagina. De coach werkt per atleet; de losse tools blijven
# altijd één klik weg via "Losse tools".
# ---------------------------------------------------------------------------
def _initialen(naam):
    return ''.join(w[0] for w in str(naam or '?').split()[:2]).upper() or '?'


@st.cache_data(ttl=30, show_spinner=False)
def _roster_status():
    return store.status_overzicht()


def render_topbar(page):
    atleet = st.session_state.get('atleet')
    with st.container(key='topbar'):
        c_logo, c_nav, c_tools, c_gap, c_sw, c_out = st.columns(
            [1.25, 1.0, 1.35, 1.4, 2.5, 1.0], vertical_alignment='center')
        with c_logo:
            if st.button('De Musculatuur', key='logo_home', help='Naar je atleten'):
                goto(PAGE_HOME)
        with c_nav:
            if st.button('Atleten', key='nav_atleten', use_container_width=True):
                goto(PAGE_HOME)
        with c_tools:
            with st.popover('Losse tools', use_container_width=True):
                st.markdown('<div class="dm-pop-t">Losse tools</div>', unsafe_allow_html=True)
                for tool in TOOLS:
                    if tool['key'] == PAGE_ATLETEN:
                        continue
                    if st.button(tool['titel'], key=f"nav_tool_{tool['key']}", use_container_width=True):
                        goto(tool['key'])
        with c_sw:
            label = atleet['naam'] if atleet else 'Kies een atleet'
            with st.container(key='switcher'):
                with st.popover(label, use_container_width=True):
                    _render_wisselaar(atleet)
        with c_out:
            if st.button('Uitloggen', key='nav_uit', use_container_width=True):
                st.session_state['authed'] = False
                st.rerun()
    # actieve navigatie + initialen in de wisselaar (CSS kan geen data lezen, dus even injecteren)
    actief = 'nav_atleten' if page in (PAGE_HOME, PAGE_ATLETEN) else None
    st.markdown(
        '<style>'
        + (f'.st-key-{actief} button {{ background: var(--surface-2) !important; color: var(--wine) !important; }}'
           if actief else '')
        + f'.st-key-switcher button p::before {{ content: "{_initialen(atleet["naam"]) if atleet else "+"}"; }}'
        + '</style>', unsafe_allow_html=True)


def _render_wisselaar(atleet):
    if not store.beschikbaar():
        st.caption('Opslag niet geconfigureerd — atleten kunnen niet bewaard worden.')
        return
    try:
        alle = _atleten()
    except Exception as e:
        st.caption(store.leesbare_fout(e))
        return
    zoek = st.text_input('Zoek atleet', placeholder='Zoek atleet…', key='sw_zoek', label_visibility='collapsed')
    lijst = alle
    if zoek.strip():
        z = zoek.strip().lower()
        lijst = [a for a in alle if z in ' '.join(str(a.get(k) or '') for k in ('naam', 'sport', 'doelen')).lower()]
    if not lijst:
        st.caption('Geen atleet gevonden.')
    for a in lijst[:8]:
        huidig = bool(atleet and atleet['id'] == a['id'])
        extra = ' · '.join(x for x in [a.get('sport')] if x)
        if st.button(f"{'● ' if huidig else ''}{a['naam']}" + (f"  —  {extra}" if extra else ''),
                     key=f"sw_{a['id']}", use_container_width=True):
            _kies_atleet(a)
            goto(PAGE_DASHBOARD)
    if len(lijst) > 8:
        st.caption(f'+ {len(lijst) - 8} meer — verfijn je zoekopdracht.')
    st.markdown('<div class="dm-pop-sep"></div>', unsafe_allow_html=True)
    if st.button('＋ Nieuwe atleet', key='sw_nieuw', type='primary', use_container_width=True):
        st.session_state['nieuwe_atleet_open'] = True
        goto(PAGE_HOME)


def render_roster():
    """Startpagina: alle atleten met hun volgend A-doel en hoe ver hun traject staat."""
    if not store.beschikbaar():
        page_header('De Musculatuur', 'Opslag is nog niet geconfigureerd: kies hieronder een tool. Voeg '
                    '`SUPABASE_URL` en `SUPABASE_KEY` toe aan de secrets om atleten te bewaren.', eyebrow='Overzicht')
        render_tools_grid()
        return
    try:
        alle = _atleten()
        status = _roster_status()
    except Exception as e:
        st.error(store.leesbare_fout(e))
        return

    k1, k2 = st.columns([2, 1.2], vertical_alignment='bottom')
    with k1:
        page_header('Jouw atleten', f'{len(alle)} atleten — kies er een om zijn dashboard en tools te openen.',
                    eyebrow='Atleten')
    with k2:
        zoek = st.text_input('Zoeken', placeholder='Zoek op naam, sport of doel…', key='roster_zoek',
                             label_visibility='collapsed')

    _render_nieuwe_atleet(open_standaard=st.session_state.pop('nieuwe_atleet_open', False) or not alle)
    if not alle:
        st.caption('Nog geen atleten. Maak er hierboven een aan.')
        return
    if zoek.strip():
        z = zoek.strip().lower()
        alle = [a for a in alle if z in ' '.join(str(a.get(k) or '') for k in ('naam', 'sport', 'doelen')).lower()]

    vandaag = pd.Timestamp.now().normalize()
    st.markdown('<div class="dm-roster-head"><div>Atleet</div><div>Sport</div><div>Volgend A-doel</div>'
                '<div>Traject</div><div></div></div>', unsafe_allow_html=True)
    for a in alle:
        info = status.get(a['id'], {})
        soorten = set(info.get('soorten', []))
        goals = []
        for g in info.get('goals') or []:
            d = pd.to_datetime((g or {}).get('date'), errors='coerce')
            if pd.notna(d) and d >= vandaag:
                goals.append({'name': g.get('name') or 'A-doel', 'date': d})
        goals.sort(key=lambda g: g['date'])
        if goals:
            g = goals[0]
            wk = (pd.Timestamp(g['date']) - vandaag).days // 7
            doel = f'{intake._e(g["name"])} · <b>{wk} wk</b>'
        else:
            doel = '<span class="dm-muted">Nog geen A-doel</span>'
        chip = lambda ok, t: f'<span class="dm-chip{" ok" if ok else ""}">{"✓ " if ok else ""}{t}</span>'
        chips = (chip('intake' in soorten, 'Intake') + chip('belastbaarheid' in soorten, 'Belasting')
                 + chip(bool(info.get('goals')), 'Plan') + chip('traject' in soorten, 'Verslag'))
        with st.container(key=f"rij_{a['id']}"):
            c1, c2, c3, c4, c5 = st.columns([2.3, 1, 1.9, 2.6, 0.95], vertical_alignment='center')
            c1.markdown(f'<div class="dm-who"><div class="dm-avatar">{intake._e(_initialen(a["naam"]))}</div>'
                        f'<b>{intake._e(a["naam"])}</b></div>', unsafe_allow_html=True)
            c2.markdown(f'<span class="dm-cell">{intake._e(a.get("sport") or "—")}</span>', unsafe_allow_html=True)
            c3.markdown(f'<span class="dm-cell">{doel}</span>', unsafe_allow_html=True)
            c4.markdown(f'<div class="dm-chips">{chips}</div>', unsafe_allow_html=True)
            if c5.button('Openen', key=f"rij_open_{a['id']}", use_container_width=True):
                _kies_atleet(a)
                goto(PAGE_DASHBOARD)


def belastbaarheid_status(current):
    """Eén regel status + kleurcode bij een A:C ratio — gedeeld door de jaarplanning-readout."""
    if current is None:
        return 'none', 'Geen belastbaarheidsdata'
    if current > 1.5:
        return 'alert', 'Piekbelasting — ruim boven de sweet spot'
    if current > 1.3:
        return 'warn', 'Boven de sweet spot'
    if current < 0.8:
        return 'warn', 'Onder de sweet spot'
    return 'ok', 'In de sweet spot (0,8-1,3)'


def get_app_password():
    try:
        if 'APP_PASSWORD' in st.secrets:
            return st.secrets['APP_PASSWORD']
    except Exception:
        pass
    return os.environ.get('DEMUSCULATUUR_PASSWORD', DEFAULT_PASSWORD)


def check_password():
    """Simpele gedeelde-wachtwoord-gate voor alle coaches (v1 — geen individuele accounts)."""
    if st.session_state.get('authed'):
        return True
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        render_hero('Welkom terug', 'Log in met het gedeelde coachwachtwoord.', eyebrow='Coach login', center=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        pw = st.text_input('Wachtwoord', type='password')
        login_clicked = st.button('Inloggen', type='primary', use_container_width=True)
        if login_clicked:
            if pw == get_app_password():
                st.session_state['authed'] = True
                st.rerun()
            else:
                st.error('Onjuist wachtwoord.')
    return False


def fmt(n, d=0):
    if n is None:
        return '–'
    return f'{n:,.{d}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def make_chart(daily, acwr, today, athlete):
    start = today - pd.Timedelta(days=182)
    d_acwr = acwr[acwr.index >= start]
    weekload = daily.rolling(7).sum()
    w = weekload[weekload.index >= start]

    DM_MAROON, DM_GREEN, DM_PEACH = theme.WINE, theme.GREEN, theme.SAND
    TXT, GRID = theme.MUTED, theme.LINE

    # Bewust Figure() i.p.v. plt.subplots(): pyplot houdt elke aangemaakte figuur bij in een
    # globale registry die pas leegloopt bij plt.close(). In een langdraaiende Streamlit-app
    # stapelen die figuren zich op over alle sessies heen, tot het geheugen vol zit en de app
    # omvalt (opnieuw een lege pagina voor de coach). Een losse Figure komt daar nooit in.
    fig = Figure(figsize=(9, 4.0))
    ax1 = fig.subplots()
    fig.patch.set_facecolor('#FFFFFF')
    ax1.set_facecolor('#FFFFFF')
    ax1.grid(axis='y', color=GRID, linewidth=0.8)
    ax1.set_axisbelow(True)
    ax1.tick_params(colors=TXT, labelsize=9, length=0)
    ax1.bar(w.index, w.values, width=0.9, color=DM_PEACH, linewidth=0,
            label='Wekelijkse trainingslast (7d som)')
    ax1.set_ylabel('Trainingslast (7d som)', color=TXT, fontsize=9)
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
    for spine in ax1.spines.values():
        spine.set_visible(False)

    ax2 = ax1.twinx()
    ax2.plot(d_acwr.index, d_acwr.values, color=DM_MAROON, linewidth=2.2, label='A:C ratio')
    ax2.axhspan(0.8, 1.3, color=DM_GREEN, alpha=0.18)
    ax2.axhline(1.5, color=DM_MAROON, linestyle='--', linewidth=1, alpha=0.5)
    ax2.axhline(0.8, color=TXT, linestyle=':', linewidth=1, alpha=0.6)
    ax2.set_ylabel('A:C ratio', color=DM_MAROON, fontsize=9)
    ax2.tick_params(axis='y', labelcolor=DM_MAROON, labelsize=9, length=0)
    ax2.set_ylim(0, max(1.8, float(np.nanmax(d_acwr.values)) * 1.15 if len(d_acwr) else 1.8))
    for spine in ax2.spines.values():
        spine.set_visible(False)
    ax1.set_title(f'Belastbaarheid laatste 6 maanden — {athlete}', loc='left', fontweight='bold',
                  color=theme.INK, fontsize=11.5, pad=12)
    fig.tight_layout()
    return fig


def kernbevindingen(summary):
    acwr = summary['acwr']
    items = []
    cur = acwr['current']
    if cur is None:
        status = 'geen recente data om een ratio te berekenen'
    elif 0.8 <= cur <= 1.3:
        status = 'binnen de veilige "sweet spot" (0,8-1,3)'
    elif cur > 1.3:
        status = 'boven de sweet spot: mogelijk verhoogd risico bij aanhoudende piekbelasting'
    else:
        status = 'onder de sweet spot: mogelijke onderbelasting/detraining'
    items.append(f"Huidige A:C ratio: **{fmt(cur, 1) if cur is not None else '–'}** — {status}.")
    items.append(f"Van de laatste {acwr['weeks_total']} weken zaten er **{acwr['weeks_green']}** in de sweet spot, "
                 f"{acwr['weeks_high']} met piekbelasting (>1,3) en {acwr['weeks_low']} met onderbelasting (<0,8).")
    p6 = summary['periods']['6m']
    items.append(f"Laatste 6 maanden: {p6['sessies']} sessies, {fmt(p6['uren'], 1)}u, {fmt(p6['km'], 0)}km.")
    if summary['gaps']:
        for g in summary['gaps']:
            items.append(f"Mogelijke blinde vlek: **{g['sport']}** komt historisch {g['totaal_historisch']}x voor "
                         f"maar is afwezig in de laatste 6 maanden (laatste sessie: {g['laatste_sessie']}, {g['dagen_geleden']} dagen geleden).")
    else:
        items.append('Geen disciplines gevonden die historisch actief waren maar recent volledig afwezig zijn.')
    return items


def sport_table(period):
    rows = period['bySport']
    df = pd.DataFrame(rows)
    if len(df) == 0:
        return pd.DataFrame(columns=['Sport', 'Sessies', 'Uren', 'Km', 'Hoogtemeters', 'Gem. HS', 'Trainingslast'])
    df = df.rename(columns={'sport': 'Sport', 'sessies': 'Sessies', 'uren': 'Uren', 'km': 'Km',
                             'hm': 'Hoogtemeters', 'hr': 'Gem. HS', 'load': 'Trainingslast'})
    df = df[['Sport', 'Sessies', 'Uren', 'Km', 'Hoogtemeters', 'Gem. HS', 'Trainingslast']]
    total = pd.DataFrame([{
        'Sport': 'TOTAAL', 'Sessies': period['sessies'], 'Uren': period['uren'], 'Km': period['km'],
        'Hoogtemeters': period['hoogtemeters'], 'Gem. HS': None, 'Trainingslast': period['load'],
    }])
    return pd.concat([df, total], ignore_index=True)


def render_jaarplanning(plan, intake_v=None):
    """Toont de voorgestelde macro/mesocyclus-structuur per A-doel (kaarten, kleurgecodeerd per fase).
    Met een intake erbij komen beschikbaarheid en aandachtspunten bovenaan, zodat de coach ze
    bij het vertalen naar sessies meteen voor ogen heeft."""
    if not plan['goals']:
        st.caption('Nog geen A-doelen ingesteld. Voeg er hierboven toe om een voorgestelde jaarplanning te zien.')
        return

    if intake_v:
        punten = [('Beschikbaarheid', intake_v['ervaring']['beschikbaarheid']),
                  ('Blessures & aandachtspunten', intake_v['ervaring']['blessures'])]
        punten = [(k, str(w).strip()) for k, w in punten if str(w or '').strip()]
        if punten:
            items = ''.join(f'<div class="dm-kv-item"><div class="dm-kv-k">{k}</div>'
                            f'<div class="dm-kv-v">{intake._e(w)}</div></div>' for k, w in punten)
            st.markdown('<div class="dm-card dm-card-note"><div class="dm-card-title">Houd rekening met — uit de intake</div>'
                        f'<div class="dm-kv">{items}</div></div>', unsafe_allow_html=True)

    blocks_by_goal = {}
    for b in plan['blocks']:
        blocks_by_goal.setdefault(b['doel'], []).append(b)

    for g in plan['goals']:
        st.markdown(f"##### {g['name']} · {g['discipline']} — {pd.Timestamp(g['date']).strftime('%d %B %Y')}")
        if g['warning']:
            st.warning(g['warning'])
        st.caption(f"{g['weken_beschikbaar']} weken beschikbaar voor dit blok, terugwerkend gepland vanaf de wedstrijdweek.")

        blokken = blocks_by_goal.get(g['name'], [])
        # De volumebalk is relatief aan het zwaarste blok, zodat de opbouw naar het piekblok
        # en de val erna in één oogopslag zichtbaar zijn.
        max_pct = max([b.get('volume_pct') or 0 for b in blokken] or [100]) or 100

        rows_html = ''
        for b in blokken:
            note_html = f'<div class="dm-plan-note">{b["notitie"]}</div>' if b['notitie'] else ''
            dates_txt = f'{b["start"].strftime("%d %b")} – {b["einde"].strftime("%d %b %Y")}'
            pct = b.get('volume_pct') or 0
            breedte = round(100 * pct / max_pct)

            cycli_html = ''
            for c in b.get('cycli', []):
                acties = ''.join(f'<li>{a}</li>' for a in c['acties'])
                if not acties:
                    continue
                ritme = f'<span class="dm-cyc-ritme">{c["ritme"]}</span>' if c['ritme'] else ''
                kop = (f'Cyclus {c["nr"]} · week {c["week_van"]}-{c["week_tot"]}'
                       if b['weken'] >= 4 else 'Deze week')
                cycli_html += (
                    f'<div class="dm-cyc">'
                    f'<div class="dm-cyc-kop">{kop}'
                    f'<span class="dm-cyc-dates">{c["start"].strftime("%d %b")} – '
                    f'{c["einde"].strftime("%d %b")}</span></div>'
                    f'{ritme}'
                    f'<ul class="dm-cyc-acties">{acties}</ul>'
                    f'</div>'
                )

            rows_html += (
                f'<div class="dm-plan-block dm-plan-{b["fase_key"]}">'
                f'<div class="dm-plan-header">'
                f'<span class="dm-plan-fase">{b["fase"]}</span>'
                f'<span class="dm-plan-dates">{dates_txt} · {b["weken"]} wk</span>'
                f'</div>'
                f'<div class="dm-volbar"><div class="dm-volbar-fill" style="width:{breedte}%"></div>'
                f'<span class="dm-volbar-lbl">{b["volume"]}</span></div>'
                f'<div class="dm-plan-meta">Intensiteit: {b["intensiteit"]}</div>'
                f'<div class="dm-plan-focus">{b["focus"]}</div>'
                f'{note_html}'
                f'{cycli_html}'
                f'</div>'
            )
        st.markdown(f'<div class="dm-card">{rows_html}</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:0.75rem"></div>', unsafe_allow_html=True)


def analyze_and_store(uploaded_file, athlete_name, today):
    try:
        df = core.load_csv_from_fileobj(io.BytesIO(uploaded_file.getvalue()))
    except ValueError as e:
        st.error(f'Fout: {e}')
        return
    except Exception as e:
        st.error(
            f'Kon dit bestand niet verwerken — {type(e).__name__}: {e}\n\n'
            'Controleer of dit het activities.csv-bestand uit de Strava-export is (niet de volledige zip) '
            'en niet beschadigd/leeg is. Stuur deze foutmelding door als het probleem blijft — daarmee '
            'kan het exact gefixt worden.'
        )
        return
    else:
        summary, daily, acute, chronic, acwr = core.build_summary(df, athlete_name, today)
        fig = make_chart(daily, acwr, today, athlete_name)
        st.session_state.setdefault('athletes', {})
        st.session_state['athletes'][athlete_name] = {'summary': summary, 'fig': fig}
        st.session_state['active_athlete'] = athlete_name
        _autosave_analyse(athlete_name, summary, daily, acwr)


def render_dashboard(athlete_name):
    data = st.session_state['athletes'][athlete_name]
    summary, fig = data['summary'], data['fig']

    items_html = ''.join(f'<li>{md_bold_to_html(item)}</li>' for item in kernbevindingen(summary))
    st.markdown(f"""
    <div class="dm-card">
      <div class="dm-card-title">Kernbevindingen — {athlete_name}</div>
      <ul class="dm-bullet-list">{items_html}</ul>
    </div>
    """, unsafe_allow_html=True)

    advies_items = summary.get('advies', [])
    if advies_items:
        advies_html = ''.join(
            f'<div class="dm-advies-item dm-advies-{item["level"]}">'
            f'<div class="dm-advies-title">{item["title"]}</div>'
            f'<div class="dm-advies-text">{item["text"]}</div></div>'
            for item in advies_items
        )
        st.markdown(f"""
        <div class="dm-card">
          <div class="dm-card-title">Trainingsadvies — komende weken</div>
          {advies_html}
        </div>
        """, unsafe_allow_html=True)
        st.caption('AI-gegenereerd advies op basis van trainingsdata (ACWR-stand, -trend en consistentie) — '
                   'geen diagnose en geen automatische inplanning. De coach combineert dit met eigen inzicht '
                   '(klachten, context, doelen) en beslist het uiteindelijke programma.')

    st.divider()
    st.subheader('Activiteitenoverzicht')
    period_tab_labels = ['Laatste 2 jaar', 'Laatste jaar', 'Laatste 6 maanden', 'Laatste 3 maanden',
                          'Laatste 4 weken', 'Laatste week']
    period_tab_keys = ['2j', '1j', '6m', '3m', '4w', '1w']
    tabs = st.tabs(period_tab_labels)
    for tab, key in zip(tabs, period_tab_keys):
        with tab:
            period = summary['periods'].get(key)
            if period is None:
                st.warning('Deze periode ontbreekt in de opgeslagen analyse (waarschijnlijk van vóór een tool-update). '
                           'Klik links opnieuw op "Analyseer" om deze atleet te vernieuwen.')
                continue
            st.caption(period['label'])
            table = sport_table(period)

            def highlight_total(row):
                is_total = row['Sport'] == 'TOTAAL'
                return [f'font-weight:700; background-color:{theme.SURFACE_2}; color:{theme.WINE};' if is_total else '' for _ in row]

            styled = table.style.apply(highlight_total, axis=1).format({
                'Sessies': '{:.0f}',
                'Uren': '{:.1f}',
                'Km': '{:.1f}',
                'Hoogtemeters': '{:.0f}',
                'Gem. HS': '{:.0f}',
                'Trainingslast': '{:.0f}',
            }, na_rep='–')
            st.dataframe(styled, hide_index=True, use_container_width=True)

    st.divider()
    st.subheader('Belastbaarheid · A:C ratio')
    st.caption('Ratio tussen 0,8 en 1,3 geldt doorgaans als "sweet spot." Dit is een signaal, geen geïsoleerde '
               'voorspeller van overbelasting — combineer altijd met herstelindicatoren en coach-inzicht '
               '(zie de literatuurstudie, hoofdstuk 3).')
    st.pyplot(fig, use_container_width=True)

    acwr_df = pd.DataFrame(summary['acwr']['table']).rename(columns={'week_ending': 'Week (t/m)', 'acwr': 'A:C ratio'})
    acwr_df['A:C ratio'] = pd.to_numeric(acwr_df['A:C ratio'], errors='coerce')

    def zone(v):
        if pd.isna(v):
            return '–'
        if v > 1.3:
            return 'Piekbelasting'
        if v < 0.8:
            return 'Onderbelasting'
        return 'Sweet spot'
    acwr_df['Zone'] = acwr_df['A:C ratio'].apply(zone)

    def style_zone(val):
        colors = {
            'Sweet spot': f'background-color:{theme.OK_SOFT}; color:{theme.OK}; font-weight:600;',
            'Piekbelasting': f'background-color:{theme.ALERT_SOFT}; color:{theme.ALERT}; font-weight:600;',
            'Onderbelasting': f'background-color:{theme.WARN_SOFT}; color:{theme.WARN}; font-weight:600;',
        }
        return colors.get(val, '')

    styled_acwr = acwr_df.style.map(style_zone, subset=['Zone']).format({'A:C ratio': '{:.1f}'}, na_rep='–')
    st.dataframe(styled_acwr, hide_index=True, use_container_width=True)

    st.divider()
    st.info(f'Wil je hieruit een jaarplanning opbouwen? Open de **Jaarplanning**-tool — die neemt de '
            f'belastbaarheid van {athlete_name} automatisch mee als startpunt.', icon='🎯')
    if st.button('Verder: jaarplanning →', key='naar_jaarplanning', type='primary', use_container_width=True):
        _naar_jaarplanning(athlete_name)

    with st.expander('Methodologie & datakwaliteit'):
        dq = summary['dataQuality']
        no_calib = dq.get('excluded_no_calibration', 0)
        no_calib_line = (
            f"\n- ⚠️ {no_calib} sessies hebben wél hartslag- en duurdata, maar konden niet geschat worden: "
            "deze atleet heeft nergens een sessie met Strava's eigen 'Trainingsbelasting', waardoor er geen "
            "ijkpunt is om hartslag naar trainingslast om te rekenen. De A:C ratio is hierdoor mogelijk "
            "onvolledig of ontbreekt." if no_calib > 0 else ''
        )
        st.markdown(f"""
- Databron: Strava-export, {summary['totalSessionsAllTime']} activiteiten ({summary['dateRange']['from']} – {summary['dateRange']['to']}).
- Trainingslast: {dq['actual']} sessies met geregistreerde waarde, {dq['estimated']} geschat op basis van hartslag × duur, {dq['excluded_no_hr']} uitgesloten wegens ontbrekende hartslagdata.{no_calib_line}
- A:C ratio: acute last = som trainingslast laatste 7 dagen; chronische last = gemiddelde wekelijkse trainingslast over de laatste 28 dagen.
- Dit is een advies-signaal — de coach beslist. Zie de literatuurstudie "Wetenschappelijke fundamenten voor een AI-analyseplatform bij De Musculatuur" voor de volledige evidence-basis.
        """)

    st.download_button(
        'Download cijfers (JSON)',
        data=json.dumps(summary, ensure_ascii=False, indent=2),
        file_name=f"summary_{athlete_name.replace(' ', '_')}.json",
        mime='application/json',
    )


# ---------------------------------------------------------------------------
# Jaarplanning-tool (staat op zichzelf, met eigen lichte belastbaarheidsbepaling)
# ---------------------------------------------------------------------------

JP_BRON_ANALYSE = 'Uit een eerdere analyse'
JP_BRON_UPLOAD = 'Nieuwe activities.csv uploaden'


def _belastbaarheid_voor(athlete_name, bron):
    """Haalt de belastbaarheid op uit de bron die de coach expliciet koos — er wordt bewust
    niet stilletjes teruggevallen op de andere bron, zodat het cijfer in de readout altijd
    komt van wat er in de keuze hierboven staat."""
    if not athlete_name:
        return None
    if bron == JP_BRON_ANALYSE:
        full = st.session_state.get('athletes', {}).get(athlete_name)
        if not full:
            return None
        summary = full['summary']
        return {
            'current': summary['acwr']['current'],
            'sessies': summary['totalSessionsAllTime'],
            'dateRange': summary['dateRange'],
            'bron': 'eerdere analyse',
            # Het sportprofiel van de laatste 3 maanden voedt de actiepunten per cyclus.
            'profiel': core.sport_profiel(summary['periods']['3m']),
            'gaps': summary.get('gaps', []),
        }
    light = st.session_state.get('jp_belastbaarheid', {}).get(athlete_name)
    return {**light, 'bron': 'activities.csv'} if light else None


def render_belastbaarheid_readout(bel):
    """Compacte weergave van enkel de huidige belastbaarheid — bewust geen volledige analyse."""
    if bel is None:
        st.markdown("""
        <div class="dm-bel-readout none">
          <div>
            <div class="dm-bel-label">Huidige belastbaarheid</div>
            <div class="dm-bel-status">Nog niet bepaald</div>
            <div class="dm-bel-meta">De jaarplanning start zonder aanpassing aan de actuele belasting.</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    level, status = belastbaarheid_status(bel['current'])
    css = {'ok': '', 'warn': ' warn', 'alert': ' alert', 'none': ' none'}[level]
    waarde = fmt(bel['current'], 1) if bel['current'] is not None else '–'
    dr = bel.get('dateRange') or {}
    meta = (f"{bel.get('sessies', '–')} activiteiten ({dr.get('from', '?')} – {dr.get('to', '?')}) "
            f"· bron: {bel.get('bron', '–')}")
    st.markdown(f"""
    <div class="dm-bel-readout{css}">
      <div>
        <div class="dm-bel-label">A:C ratio</div>
        <div class="dm-bel-value">{waarde}</div>
      </div>
      <div>
        <div class="dm-bel-status">{status}</div>
        <div class="dm-bel-meta">{meta}</div>
        <div class="dm-bel-meta">Dit cijfer bepaalt het startpunt van de eerste cyclus hieronder.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Integratieve route: intake → belastbaarheid (optioneel) → jaarplanning → trajectverslag
# De tools blijven elk afzonderlijk bruikbaar; met een actieve atleet tonen ze daarnaast deze
# route, zodat een coach de stappen na elkaar doorloopt en afsluit met één verslag.
# ---------------------------------------------------------------------------
TRAJECT_STAPPEN = [('intake', 'Intake'), ('belastbaarheid', 'Belastbaarheid'),
                   ('jaarplanning', 'Jaarplanning'), ('verslag', 'Trajectverslag')]


def render_traject(huidig):
    """Trajectbalk bovenaan intake, belastbaarheid en jaarplanning (enkel met een actieve atleet)."""
    atleet = st.session_state.get('atleet')
    if not atleet:
        return
    naam = atleet['naam']
    status = {
        'intake': _intake_record(atleet) is not None,
        'belastbaarheid': naam in st.session_state.get('athletes', {}),
        'jaarplanning': bool(st.session_state.get(f'a_goals_{naam}')),
        'verslag': bool(st.session_state.get(f'traject_html_{naam}')),
    }
    items = ''
    for i, (key, label) in enumerate(TRAJECT_STAPPEN, start=1):
        klasse = 'active' if key == huidig else ('done' if status[key] else '')
        teken = '✓' if status[key] and key != huidig else str(i)
        optioneel = '<small>optioneel</small>' if key == 'belastbaarheid' else ''
        items += f'<div class="dm-tstep {klasse}"><span class="n">{teken}</span><span>{label}{optioneel}</span></div>'
    st.markdown(f'<div class="dm-traject"><div class="dm-traject-who">Traject · {intake._e(naam)}</div>'
                f'<div class="dm-tsteps">{items}</div></div>', unsafe_allow_html=True)


def _naar_jaarplanning(naam):
    st.session_state['jp_athlete'] = naam
    if naam in st.session_state.get('athletes', {}):
        # Meteen de juiste bron klaarzetten, anders landt de coach op een upload-scherm
        # terwijl de analyse van deze atleet er al is.
        st.session_state['jp_bron'] = JP_BRON_ANALYSE
        st.session_state['jp_pick'] = naam
    goto(PAGE_JAARPLANNING)


_FASE_KLEUR = {'transitie': '#B4A399', 'basis1': '#D9B48F', 'basis2': '#D9B48F', 'basis3': '#D9B48F',
               'opbouw1': '#63B995', 'opbouw2': '#63B995', 'piek': '#9A4A3A',
               'taper_afbouw': '#4F000B', 'wedstrijdweek': '#4F000B'}


# Atletenversie van de planning: grote blokken i.p.v. alle (sub)fasen en cycli.
_VISIE = [  # (sleutel, naam, kleur, één zin voor de atleet)
    ('herstel', 'Herstel', '#B4A399', 'Actief herstel na je vorige wedstrijd — even ontladen.'),
    ('basis', 'Basis', '#D9B48F', 'Aerobe basis en kracht: veel rustig volume en techniek.'),
    ('opbouw', 'Opbouw', '#63B995', 'Specifieker en intensiever: wedstrijdtempo en drempelwerk.'),
    ('piek', 'Piek', '#9A4A3A', 'Scherp worden: kort en intens, minder volume.'),
    ('taper', 'Taper & wedstrijd', '#4F000B', 'Volume omlaag, frisheid omhoog — klaar voor de start.'),
]
_VISIE_VAN = {'transitie': 'herstel', 'basis1': 'basis', 'basis2': 'basis', 'basis3': 'basis',
              'opbouw1': 'opbouw', 'opbouw2': 'opbouw', 'piek': 'piek',
              'taper_afbouw': 'taper', 'wedstrijdweek': 'taper'}
_MND_KORT = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']


def _visie_html(goal, blokken):
    """Eén A-doel als balk van grote blokken (breedte = aantal weken) met een korte legende."""
    e = intake._e
    groepen = []
    for b in blokken:
        k = _VISIE_VAN.get(b['fase_key'], 'basis')
        if groepen and groepen[-1]['k'] == k:
            groepen[-1]['weken'] += b['weken']
            groepen[-1]['einde'] = b['einde']
        else:
            groepen.append({'k': k, 'weken': b['weken'], 'start': b['start'], 'einde': b['einde']})
    if not groepen:
        return ''
    info = {k: (n, c, z) for k, n, c, z in _VISIE}
    totaal = sum(gr['weken'] for gr in groepen) or 1
    balk = ''.join(
        f'<div class="vz-seg" style="flex:{gr["weken"]};background:{info[gr["k"]][1]}">'
        f'<b>{gr["weken"]} wk</b><span>{e(info[gr["k"]][0])}</span></div>' for gr in groepen)
    maand = lambda d: f'{_MND_KORT[d.month - 1]} {str(d.year)[2:]}'
    legende = ''.join(
        f'<div class="vz-item"><span class="vz-dot" style="background:{info[gr["k"]][1]}"></span>'
        f'<div><div class="vz-t">{gr["weken"]} {"week" if gr["weken"] == 1 else "weken"} {e(info[gr["k"]][0]).lower()}'
        f'<small>{maand(gr["start"])} – {maand(gr["einde"])}</small></div>'
        f'<div class="vz-z">{e(info[gr["k"]][2])}</div></div></div>' for gr in groepen)
    datum = pd.Timestamp(goal['date']).strftime('%d/%m/%Y')
    return (f'<div class="tv-goal">{e(goal["name"])}<small>{datum} · {totaal} weken voorbereiding</small></div>'
            f'<div class="vz-bar">{balk}</div><div class="vz-legend">{legende}</div>')


def traject_html(intake_v, plan, bel=None, summary=None):
    """Eén verslag voor de atleet: de intake, aangevuld met waar hij nu staat (belastbaarheid, als
    die er is) en de jaarplanning — meteen na de doelen, in dezelfde huisstijl."""
    e = intake._e
    extra = ''
    if bel and bel.get('current') is not None:
        level, status = belastbaarheid_status(bel['current'])
        stats = [('A:C ratio', fmt(bel['current'], 1), level)]
        p3 = ((summary or {}).get('periods') or {}).get('3m')
        if p3:
            stats += [('Sessies · 3 mnd', str(p3['sessies']), ''), ('Uren · 3 mnd', fmt(p3['uren'], 0), ''),
                      ('Km · 3 mnd', fmt(p3['km'], 0), '')]
        stat_html = ''.join(f'<div class="tv-stat {t}"><div class="k">{k}</div><div class="v">{v}</div></div>'
                            for k, v, t in stats)
        advies = ''.join(f'<div class="tv-advies"><b>{e(a["title"])}</b><span>{e(a["text"])}</span></div>'
                         for a in [x for x in ((summary or {}).get('advies') or [])
                                   if not x.get('title', '').startswith('Heropstart')][:2])
        # (de 'heropstart'-signalen zijn coach-informatie over blinde vlekken, niet voor de atleet)
        extra += (f'<div class="rsec"><h3 data-n="0">Waar sta je nu</h3>'
                  f'<p>Op basis van je trainingsdata: <b>{e(status)}</b>. Dat is het vertrekpunt van je planning.</p>'
                  f'<div class="tv-stats">{stat_html}</div>{advies}</div>')

    if plan and plan.get('goals'):
        aandacht = ''
        if intake_v:
            for k, w in (('Beschikbaarheid', intake_v['ervaring']['beschikbaarheid']),
                         ('Aandachtspunten', intake_v['ervaring']['blessures'])):
                if str(w or '').strip():
                    aandacht += f'<div class="tv-intake"><b>{k}:</b> {e(w)}</div>'
        per_doel = ''
        for g in plan['goals']:
            blokken = [b for b in plan['blocks'] if b['doel'] == g['name']]
            per_doel += _visie_html(g, blokken)
        extra += (f'<div class="rsec pagebreak"><h3 data-n="0">Jouw jaarplanning</h3>'
                  f'<p>Zo ziet je voorbereiding eruit, in grote blokken: eerst een brede basis, dan specifieker '
                  f'opbouwen, en tot slot scherp en fris naar de start. De concrete trainingen per week krijg je '
                  f'van je coach.</p>{aandacht}{per_doel}</div>')

    v = intake_v or intake.leeg_intake()
    return intake.verslag_html(v, extra_html=extra, titel='Jouw traject',
                               eyebrow='Intake · Belastbaarheid · Jaarplanning' if extra.count('Waar sta je nu')
                               else 'Intake · Jaarplanning')


def _traject_bewaar(atleet_naam, html, nieuw=False):
    """Bewaart het trajectverslag bij de atleet. Aanpassingen werken hetzelfde document bij;
    'opnieuw maken' (nieuw=True) maakt een nieuwe versie aan."""
    atleet = st.session_state.get('atleet')
    if not (atleet and atleet['naam'] == atleet_naam and store.beschikbaar()):
        return
    rid_key = f'traject_rid_{atleet_naam}'
    try:
        rec = store.bewaar_record(atleet['id'], 'document', f'Trajectverslag {date.today().strftime("%d/%m/%Y")}',
                                  {'type': 'traject', 'html': html},
                                  record_id=None if nieuw else st.session_state.get(rid_key))
        st.session_state[rid_key] = rec.get('id') or st.session_state.get(rid_key)
        return True
    except Exception as ex:
        st.warning(f'Verslag niet bewaard. {store.leesbare_fout(ex)}')
        return False


def _laatste_traject(atleet):
    try:
        for r in store.lijst_records(atleet['id'], soort='document', met_data=True):
            if (r.get('data') or {}).get('type') == 'traject' and r['data'].get('html'):
                return r
    except Exception:
        pass
    return None


def render_trajectverslag(atleet_naam, intake_v, plan, bel, titel='Trajectverslag voor de atleet', sleutel='jp'):
    """Eén klik: intake + belastbaarheid + jaarplanning samen in één verslag voor de atleet."""
    st.divider()
    st.markdown(f'##### {titel}')
    if not intake_v:
        st.markdown('<div class="dm-card dm-card-note"><div class="dm-card-title">Eerst een intake nodig</div>'
                    '<p style="margin:0;color:var(--muted)">Het trajectverslag bouwt verder op het intakeverslag. '
                    'Maak eerst een intake voor deze atleet — daarna komen doelen, belastbaarheid en jaarplanning '
                    'hier samen in één verslag.</p></div>', unsafe_allow_html=True)
        return
    inhoud = ['intake & doelen', 'belastbaarheid' if bel else None, 'jaarplanning']
    st.markdown('<div class="dm-card dm-cta"><div><div class="dm-card-title" style="margin-bottom:.3rem">'
                'Alles in één verslag</div><p style="margin:0;color:var(--muted)">'
                + ' · '.join(x for x in inhoud if x)
                + (' — zonder Strava-analyse valt het belastbaarheidsdeel gewoon weg.' if not bel else '')
                + '</p></div></div>', unsafe_allow_html=True)
    key = f'traject_html_{atleet_naam}'
    atleet = st.session_state.get('atleet')
    eigen = bool(atleet and atleet['naam'] == atleet_naam)
    # Na een herstart: de laatst bewaarde versie terug tonen
    if key not in st.session_state and eigen and store.beschikbaar():
        rec = _laatste_traject(atleet)
        if rec:
            st.session_state[key] = rec['data']['html']
            st.session_state[f'traject_rid_{atleet_naam}'] = rec['id']
    label = 'Trajectverslag opnieuw maken' if st.session_state.get(key) else 'Trajectverslag maken'
    if st.button(label, type='primary', key=f'traject_maak_{sleutel}', use_container_width=True):
        summary = (st.session_state.get('athletes', {}).get(atleet_naam) or {}).get('summary')
        html = traject_html(intake_v, plan, bel=bel, summary=summary)
        st.session_state[key] = html
        st.session_state[f'{key}_nonce'] = st.session_state.get(f'{key}_nonce', 0) + 1
        # Soort 'document' + type-label: de records-tabel in Supabase laat enkel een vaste
        # lijst soorten toe, zo hoeft daar niets aan aangepast te worden.
        if _traject_bewaar(atleet_naam, html, nieuw=True):
            st.toast(f'Trajectverslag bewaard bij {atleet_naam}.')
    html = st.session_state.get(key)
    if html:
        flash = st.session_state.pop(f'{key}_flash', None)
        if flash:
            st.success(flash)
        c1, c2 = st.columns([1, 2])
        c1.download_button('Download trajectverslag (.html)', data=html, use_container_width=True,
                           file_name=f"Trajectverslag_{atleet_naam.replace(' ', '_')}.html", mime='text/html',
                           key=f'traject_dl_{sleutel}')
        c2.caption('Aanpassen kan op twee manieren: geef hieronder een opmerking aan de AI, of klik in het '
                   'verslag op **Bewerken** en typ rechtstreeks. Let op: "opnieuw maken" bouwt het verslag '
                   'opnieuw op uit intake, analyse en doelen — je aanpassingen gaan dan verloren.')

        # 1) Opmerking → de AI past het verslag aan
        with st.form(f'traject_opm_{sleutel}', clear_on_submit=True):
            opm = st.text_area('Opmerking voor de AI', height=90,
                               placeholder='bv. "Maak het waarom persoonlijker en noem zijn dochter Lien bij naam." '
                                           'of "Voeg bij Basis 1 toe dat hij op zondag lang fietst."')
            verwerk = st.form_submit_button('Opmerking verwerken', type='primary')
        if verwerk and opm.strip():
            ai_sleutel = intake.openai_sleutel()
            if not ai_sleutel:
                st.warning('Er is nog geen OpenAI-sleutel ingesteld (OPENAI_API_KEY in de secrets). '
                           'Rechtstreeks bewerken werkt wel.')
            else:
                with st.spinner('Het verslag wordt aangepast…'):
                    try:
                        nieuw, uitleg = intake.bewerk_verslag(html, opm, ai_sleutel)
                    except Exception as ex:
                        nieuw, uitleg = None, None
                        st.error(intake.leesbare_fout(ex))
                if nieuw is not None:
                    if nieuw != html:
                        st.session_state[key] = nieuw
                        st.session_state[f'{key}_nonce'] = st.session_state.get(f'{key}_nonce', 0) + 1
                        _traject_bewaar(atleet_naam, nieuw)
                    st.session_state[f'{key}_flash'] = uitleg
                    st.rerun()

        # 2) Rechtstreeks in het verslag typen
        waarde = _verslag_component(html=html, nonce=f"{atleet_naam}-{st.session_state.get(f'{key}_nonce', 0)}",
                                    key=f'verslag_ed_{sleutel}', default=None)
        if isinstance(waarde, dict) and waarde.get('action') == 'save' \
                and waarde.get('id') != st.session_state.get(f'{key}_laatst'):
            st.session_state[f'{key}_laatst'] = waarde.get('id')
            st.session_state[key] = waarde.get('html') or html
            if _traject_bewaar(atleet_naam, st.session_state[key]):
                st.toast('Wijzigingen bewaard bij ' + atleet_naam + '.')


def render_jaarplanning_page():
    page_header('Jaarplanning', eyebrow='Planning')
    render_traject('jaarplanning')
    st.caption('Macro/mesocyclus-voorstel per A-doel volgens Friel en Olbrecht, terugwerkend gepland '
               'vanaf elke wedstrijddatum. De coach vertaalt dit naar concrete sessies.')

    # --- Stap 1: belastbaarheid als cijfermatige basis -----------------------
    st.markdown('##### ① Belastbaarheid als basis')
    st.caption('Enkel de A:C ratio wordt hier gebruikt, als startpunt voor de eerste cyclus — voor de '
               'volledige analyse (blinde vlekken, trend, advies) gebruik je de Belastbaarheidsanalyse-tool. '
               'Zonder belastbaarheidscijfer werkt de planning ook, maar dan zonder aanpassing aan de '
               'actuele belasting.')

    # De actieve atleet (sidebar/dashboard) is standaard ook de atleet van de planning.
    actief = st.session_state.get('atleet')
    if actief and not st.session_state.get('jp_athlete'):
        st.session_state['jp_athlete'] = actief['naam']

    known = list(st.session_state.get('athletes', {}).keys())
    opties = [JP_BRON_ANALYSE, JP_BRON_UPLOAD] if known else [JP_BRON_UPLOAD]
    # Een eerder gekozen bron die nu niet meer bestaat (bv. na uitloggen zijn er geen analyses
    # meer) zou Streamlit doen struikelen op een ongeldige radio-waarde.
    if st.session_state.get('jp_bron') not in opties:
        st.session_state.pop('jp_bron', None)
    bron = st.radio('Bron van de belastbaarheid', opties, horizontal=True, key='jp_bron')
    if not known:
        st.caption('Nog geen analyses in deze sessie. Analyseer een atleet in de '
                   'Belastbaarheidsanalyse-tool en je kunt die hier rechtstreeks kiezen.')

    if bron == JP_BRON_ANALYSE:
        vorige = st.session_state.get('jp_athlete')
        a1, a2 = st.columns([2, 1])
        with a1:
            athlete_name = st.selectbox('Geanalyseerde atleet', known,
                                         index=known.index(vorige) if vorige in known else 0,
                                         key='jp_pick')
        with a2:
            ref_date = st.date_input('Referentiedatum', value=pd.Timestamp.now().normalize().date(),
                                      key='jp_refdate')
        st.caption('De referentiedatum is hier enkel het startpunt van de planning — de A:C ratio komt '
                   'uit de eerder uitgevoerde analyse.')
    else:
        c1, c2 = st.columns([2, 1])
        with c1:
            athlete_name = st.text_input('Naam atleet', value=st.session_state.get('jp_athlete', ''),
                                          placeholder='bv. Jan Peeters', key='jp_athlete_input')
        with c2:
            ref_date = st.date_input('Referentiedatum', value=pd.Timestamp.now().normalize().date(),
                                      key='jp_refdate')
        st.caption('De referentiedatum is zowel de peildatum voor de A:C ratio als het startpunt van de planning.')

        up_col, btn_col = st.columns([3, 1])
        with up_col:
            jp_file = st.file_uploader('activities.csv', type=['csv'], key='jp_upload',
                                        label_visibility='collapsed')
        with btn_col:
            bereken = st.button('Berekenen', type='primary', key='jp_bereken',
                                 disabled=not (athlete_name and jp_file), use_container_width=True)
        if bereken:
            try:
                df = core.load_csv_from_fileobj(io.BytesIO(jp_file.getvalue()))
                bel = core.compute_belastbaarheid(df, pd.Timestamp(ref_date))
            except ValueError as e:
                st.error(f'Fout: {e}')
            except Exception as e:
                st.error(f'Kon dit bestand niet verwerken — {type(e).__name__}: {e}\n\n'
                         'Controleer of dit het activities.csv-bestand uit de Strava-export is.')
            else:
                st.session_state.setdefault('jp_belastbaarheid', {})[athlete_name] = bel
                st.rerun()

    st.session_state['jp_athlete'] = athlete_name
    bel = _belastbaarheid_voor(athlete_name, bron)
    render_belastbaarheid_readout(bel)

    if not athlete_name:
        st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)
        st.caption('Vul hierboven een naam in om A-doelen toe te voegen.')
        return

    # --- Intake van deze atleet: doelen, beschikbaarheid en aandachtspunten ---
    actief = st.session_state.get('atleet')
    if actief and actief['naam'].strip().lower() == athlete_name.strip().lower():
        jp_atleet = actief
    else:
        try:
            jp_atleet = store.zoek_atleet_op_naam(athlete_name) if store.beschikbaar() else None
        except Exception:
            jp_atleet = None
    intake_v = _intake_velden(_intake_record(jp_atleet))
    st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)
    if not render_intake_context(intake_v, titel='Uit de intake', compact=True):
        st.caption('Geen intakeverslag gevonden voor deze atleet — doelen, beschikbaarheid en '
                   'aandachtspunten uit de intake verschijnen hier zodra er een bewaard is.')

    # --- Stap 2: A-doelen ---------------------------------------------------
    st.divider()
    st.markdown('##### ② A-doelen')
    st.caption('Max. 3 A-doelen per jaar.')

    goals_key = f'a_goals_{athlete_name}'
    if goals_key not in st.session_state:
        st.session_state[goals_key] = []
    goals = st.session_state[goals_key]

    # Integratieve route: zijn er nog geen A-doelen, dan worden de wedstrijden uit de intake
    # automatisch overgenomen (één keer per atleet — verwijdert de coach ze, dan blijven ze weg).
    auto_key = f'jp_auto_{athlete_name}'
    if not goals and intake_v and not st.session_state.get(auto_key):
        st.session_state[auto_key] = True
        nieuw = doel_suggesties(intake_v)
        if nieuw:
            goals.extend(nieuw)
            st.session_state[goals_key] = goals
            _autosave_doelen(athlete_name, goals)
            st.session_state['jp_flash'] = ('Overgenomen uit de intake: '
                                            + ', '.join(g['name'] for g in nieuw) + '.')
    flash = st.session_state.pop('jp_flash', None)
    if flash:
        st.success(flash)

    # Hoofddoel uit de intake zonder datum: meteen de datum laten invullen
    hoofd_open = hoofddoel_zonder_datum(intake_v, goals)
    if hoofd_open and len(goals) < 3:
        with st.form(f'hoofd_datum_{athlete_name}'):
            st.markdown(f'**Hoofddoel uit de intake: {hoofd_open}** — vul de datum in om het als A-doel '
                        f'op te nemen.')
            h1, h2, h3 = st.columns([1.2, 1, 1])
            h_datum = h1.date_input('Datum', value=None, min_value=pd.Timestamp.now().date(),
                                    key=f'hoofd_datum_in_{athlete_name}')
            h_disc = h2.selectbox('Discipline', SPORTEN, key=f'hoofd_disc_{athlete_name}',
                                  index=SPORTEN.index(_sport_uit_tekst(intake_v['algemeen']['sport']))
                                  if _sport_uit_tekst(intake_v['algemeen']['sport']) in SPORTEN else 0)
            h3.markdown('<div style="height:1.7rem"></div>', unsafe_allow_html=True)
            if h3.form_submit_button('Toevoegen', type='primary', use_container_width=True) and h_datum:
                goals.append({'name': hoofd_open, 'date': pd.Timestamp(h_datum), 'discipline': h_disc})
                st.session_state[goals_key] = goals
                _autosave_doelen(athlete_name, goals)
                st.rerun()

    if goals:
        chips = ''.join(
            f'<span class="dm-goal-chip">{g["name"]} — {pd.Timestamp(g["date"]).strftime("%d %b %Y")}</span>'
            for g in goals
        )
        st.markdown(chips, unsafe_allow_html=True)

    with st.expander(f'Doelen beheren ({len(goals)}/3)', expanded=len(goals) == 0):
        if len(goals) < 3:
            with st.form(f'add_goal_form_{athlete_name}', clear_on_submit=True):
                g1, g2, g3 = st.columns([2, 1, 1])
                with g1:
                    new_name = st.text_input('Naam wedstrijd/doel', placeholder='bv. Ironman Nice')
                with g2:
                    new_date = st.date_input('Datum', value=None, min_value=pd.Timestamp.now().date())
                with g3:
                    new_disc = st.selectbox('Discipline', ['Triatlon', 'Lopen', 'Fietsen', 'Zwemmen', 'Andere'])
                if st.form_submit_button('A-doel toevoegen', use_container_width=True):
                    if not new_name or not new_date:
                        st.error('Vul een naam én datum in.')
                    else:
                        goals.append({'name': new_name, 'date': pd.Timestamp(new_date), 'discipline': new_disc})
                        st.session_state[goals_key] = goals
                        _autosave_doelen(athlete_name, goals)
                        st.rerun()
        else:
            st.caption('Maximum van 3 A-doelen bereikt. Verwijder een doel om een ander toe te voegen.')

        # Wedstrijden met een datum uit de intake: met één klik als A-doel overnemen.
        bestaand = {(g['name'].lower(), pd.Timestamp(g['date']).date()) for g in goals}
        sugg = [x for x in doel_suggesties(intake_v)
                if (x['name'].lower(), x['date'].date()) not in bestaand]
        if sugg and len(goals) < 3:
            st.caption('Uit de intake — klik om over te nemen:')
            for j, x in enumerate(sugg):
                if st.button(f"＋ {x['name']} · {x['date'].strftime('%d %b %Y')}",
                             key=f'sugg_{athlete_name}_{j}'):
                    goals.append(x)
                    st.session_state[goals_key] = goals
                    _autosave_doelen(athlete_name, goals)
                    st.rerun()

        for i, g in enumerate(goals):
            gc1, gc2 = st.columns([4, 1])
            with gc1:
                st.markdown(f"**{g['name']}** — {g['discipline']} — {pd.Timestamp(g['date']).strftime('%d %B %Y')}")
            with gc2:
                if st.button('Verwijder', key=f'del_goal_{athlete_name}_{i}', use_container_width=True):
                    goals.pop(i)
                    st.session_state[goals_key] = goals
                    _autosave_doelen(athlete_name, goals)
                    st.rerun()

    # --- Stap 3: het plan ---------------------------------------------------
    if goals:
        today_ref = pd.Timestamp(ref_date)
        acwr_current = bel['current'] if bel else None
        plan = core.generate_jaarplanning(today_ref, goals, acwr_current,
                                           profiel=(bel or {}).get('profiel'),
                                           gaps=(bel or {}).get('gaps'))
        # Eerst het eindproduct voor de atleet (één klik), daarna de planning in detail voor de coach.
        render_trajectverslag(athlete_name, intake_v, plan, bel, titel='③ Trajectverslag voor de atleet')
        st.divider()
        st.markdown('##### ④ Planning in detail')
        if not (bel or {}).get('profiel'):
            st.caption('Zonder belastbaarheidsdata blijven de actiepunten algemeen. Kies hierboven een '
                       'analyse of upload een activities.csv om ze op de trainingshistoriek per sport '
                       'te baseren.')
        render_jaarplanning(plan, intake_v=intake_v)
    else:
        st.caption('Nog geen A-doelen ingesteld. Voeg er hierboven toe om een voorgestelde jaarplanning te zien.')


# ---------------------------------------------------------------------------
# Atleetprofielen: alles wat een coach invoert wordt automatisch bewaard (zie store.py).
# ---------------------------------------------------------------------------

SPORTEN = ['Triatlon', 'Lopen', 'Fietsen', 'Zwemmen', 'Andere']
SUITE_NAMEN = {'lactate': 'Lactaattest', 'cp': 'Critical Power', 'css': 'Critical Swim Speed',
               'cv': '3/5 km looptest', 'voeding': 'Wedstrijdvoedingsplan'}


@st.cache_data(ttl=120, show_spinner=False)
def _atleten():
    return store.lijst_atleten()


def _herstel_analyse(atleet, record):
    """Zet een bewaarde belastbaarheidsanalyse terug in de sessie, inclusief de grafiek, zodat
    het dashboard meteen weer beschikbaar is zonder de export opnieuw te uploaden."""
    data = record['data']
    summary = data['summary']
    naam = atleet['naam']
    daily = pd.Series(data['daily']['values'], index=pd.to_datetime(data['daily']['dates']), dtype=float)
    acwr = pd.Series([np.nan if v is None else v for v in data['acwr']['values']],
                     index=pd.to_datetime(data['acwr']['dates']), dtype=float)
    today = pd.Timestamp(summary.get('todayIso') or daily.index.max())
    fig = make_chart(daily, acwr, today, naam)
    st.session_state.setdefault('athletes', {})[naam] = {'summary': summary, 'fig': fig}
    st.session_state['active_athlete'] = naam


def _laad_atleet_in_sessie(atleet):
    """Bij het kiezen van een atleet: laatste analyse en A-doelen uit de opslag halen, tenzij
    ze deze sessie al in het geheugen staan (dan is die versie de nieuwste)."""
    naam = atleet['naam']
    st.session_state['jp_athlete'] = naam
    if naam not in st.session_state.get('athletes', {}):
        rec = store.laatste_record(atleet['id'], 'belastbaarheid')
        if rec:
            _herstel_analyse(atleet, rec)
    goals_key = f'a_goals_{naam}'
    if goals_key not in st.session_state:
        rec = store.laatste_record(atleet['id'], 'jaarplanning')
        doelen = (rec or {}).get('data', {}).get('goals', [])
        st.session_state[goals_key] = [
            {'name': g['name'], 'date': pd.Timestamp(g['date']), 'discipline': g.get('discipline', '')}
            for g in doelen
        ]


def _autosave_analyse(athlete_name, summary, daily, acwr):
    """Na elke analyse: bewaren bij de geselecteerde atleet. De laatste 200 dagen van de
    dag- en A:C-reeks gaan mee, zodat de grafiek (6 maanden) later exact herbouwd kan worden."""
    atleet = st.session_state.get('atleet')
    if not (store.beschikbaar() and atleet and atleet['naam'] == athlete_name):
        return
    vanaf = daily.index.max() - pd.Timedelta(days=200)
    d = daily[daily.index >= vanaf]
    a = acwr[acwr.index >= vanaf]
    data = {
        'summary': summary,
        'daily': {'dates': [x.strftime('%Y-%m-%d') for x in d.index], 'values': d.tolist()},
        'acwr': {'dates': [x.strftime('%Y-%m-%d') for x in a.index],
                 'values': [None if pd.isna(v) else float(v) for v in a.values]},
    }
    try:
        store.bewaar_record(atleet['id'], 'belastbaarheid', f"Analyse t/m {summary['reportDate']}", data)
        st.toast(f'Analyse bewaard bij {athlete_name}.', icon='💾')
    except Exception as e:
        st.warning(f'De analyse is klaar maar kon niet bewaard worden: {e}')


def _autosave_doelen(athlete_name, goals):
    """A-doelen: één record per atleet dat telkens overschreven wordt."""
    atleet = st.session_state.get('atleet')
    if not (store.beschikbaar() and atleet and atleet['naam'] == athlete_name):
        return
    data = {'goals': [{'name': g['name'], 'date': pd.Timestamp(g['date']).strftime('%Y-%m-%d'),
                       'discipline': g.get('discipline', '')} for g in goals]}
    try:
        bestaand = store.laatste_record(atleet['id'], 'jaarplanning')
        store.bewaar_record(atleet['id'], 'jaarplanning', 'A-doelen', data,
                            record_id=bestaand['id'] if bestaand else None)
    except Exception as e:
        st.warning(f'A-doelen konden niet bewaard worden: {e}')


GEEN_ATLEET = '— geen —'


def _kies_atleet(rij):
    st.session_state['atleet'] = store.haal_atleet(rij['id'])
    _laad_atleet_in_sessie(st.session_state['atleet'])
    # De sidebar-selectbox is op dit moment al getekend, dus zijn waarde kan hier niet meer
    # gezet worden. De selector pikt deze vlag op vóór hij zichzelf tekent, in de volgende run.
    st.session_state['atleet_pending'] = rij['naam']


def render_atleet_selector():
    """Sidebar: de actieve atleet. Geldt voor alle tools."""
    st.markdown('<div class="dm-sidebar-section">Atleet</div>', unsafe_allow_html=True)
    if not store.beschikbaar():
        st.caption('Opslag niet geconfigureerd — alles werkt, maar niets wordt bewaard na een '
                   'herstart. Zie de tegel "Atleten".')
        return
    try:
        rijen = _atleten()
    except Exception as e:
        st.caption(store.leesbare_fout(e))
        return
    namen = [GEEN_ATLEET] + [a['naam'] for a in rijen]
    # Een keuze die elders gemaakt is (Atleten-pagina, nieuw profiel) hier in de widget zetten,
    # anders wint de oude widget-waarde van de index en zou de keuze meteen weer wegvallen.
    pending = st.session_state.pop('atleet_pending', None)
    if pending is not None:
        st.session_state['atleet_select'] = pending if pending in namen else GEEN_ATLEET
    huidig = (st.session_state.get('atleet') or {}).get('naam')
    # Zodra de widget een sessiewaarde heeft, bepaalt die de keuze; dan ook nog een index
    # meegeven levert enkel een waarschuwing op in de logs.
    extra = {} if 'atleet_select' in st.session_state else {'index': namen.index(huidig) if huidig in namen else 0}
    keuze = st.selectbox('Actieve atleet', namen, key='atleet_select',
                          label_visibility='collapsed', **extra)
    if keuze != GEEN_ATLEET and keuze != huidig:
        _kies_atleet(next(a for a in rijen if a['naam'] == keuze))
        st.rerun()
    elif keuze == GEEN_ATLEET and huidig:
        st.session_state['atleet'] = None
        st.rerun()
    if st.button('Dashboard openen' if huidig else 'Alle atleten', key='naar_atleten',
                 type='primary' if huidig else 'secondary', use_container_width=True):
        goto(PAGE_DASHBOARD if huidig else PAGE_ATLETEN)


def _leeftijd(geboortedatum):
    if not geboortedatum:
        return None
    try:
        g = pd.to_datetime(geboortedatum).date()
    except Exception:
        return None
    t = date.today()
    return t.year - g.year - ((t.month, t.day) < (g.month, g.day))


def _intake_record(atleet):
    """Laatste intakeverslag van deze atleet (of None). Bewust bij elke weergave opgehaald:
    één query, en zo is een net bewaard verslag meteen overal zichtbaar."""
    if not (atleet and store.beschikbaar()):
        return None
    try:
        return store.laatste_record(atleet['id'], 'intake')
    except Exception:
        return None


def _intake_velden(record):
    if not record:
        return None
    return intake.normaliseer((record.get('data') or {}).get('velden') or {})


def _tekst(s):
    return str(s or '').strip()


def render_intake_context(v, titel='Uit de intake', compact=False):
    """De intake-elementen die er voor planning en analyse toe doen, als één rustige kaart.
    Lege velden worden weggelaten, zodat de kaart nooit vol streepjes staat."""
    if not v:
        return False
    rijen = [
        ('Hoofddoel', intake._hoofddoel(v)),
        ('Doel op het event', _tekst(v['doelen'].get('prestatiedoel'))),
        ('Waarom', _tekst(v['doelen'].get('motivatie'))),
        ('Korte termijn', _tekst(v['doelen']['korte_termijn'])),
        ('Wedstrijden', _tekst(v['doelen']['wedstrijden'])),
        ('Beschikbaarheid', _tekst(v['ervaring']['beschikbaarheid'])),
        ('Blessures & aandachtspunten', _tekst(v['ervaring']['blessures'])),
        ('Trainingservaring', _tekst(v['ervaring']['trainingservaring'])),
    ]
    if not compact:
        rijen += [('Materiaal & data', _tekst(v['ervaring']['materiaal'])),
                  ('Advies coach', _tekst(v.get('advies')))]
    rijen = [(k, w) for k, w in rijen if w]
    if not rijen:
        return False
    items = ''.join(f'<div class="dm-kv-item"><div class="dm-kv-k">{k}</div>'
                    f'<div class="dm-kv-v">{intake._e(w)}</div></div>' for k, w in rijen)
    datum = _tekst(v['algemeen'].get('datum'))
    sub = f'<span class="dm-card-sub">intake van {intake._e(datum)}</span>' if datum else ''
    st.markdown(f'<div class="dm-card"><div class="dm-card-title">{titel}{sub}</div>'
                f'<div class="dm-kv">{items}</div></div>', unsafe_allow_html=True)
    return True


_MAANDEN = {'jan': 1, 'feb': 2, 'mrt': 3, 'maa': 3, 'apr': 4, 'mei': 5, 'jun': 6, 'jul': 7,
            'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'dec': 12}


def doel_suggesties(v):
    """Wedstrijden met een toekomstige datum uit de intake, als A-doelen (max. 3). De wedstrijd van
    het hoofddoel komt altijd mee; daarna de overige, chronologisch."""
    if not v:
        return []
    sport = _sport_uit_tekst(v['algemeen']['sport']) or 'Andere'
    vandaag = date.today()
    races = [r for r in intake._wedstrijden(v['doelen'].get('wedstrijden')) if r[1] and r[1] >= vandaag]
    hoofd = intake._hoofd_race(v)
    if hoofd and hoofd[1] >= vandaag:
        races = [hoofd] + [r for r in races if r != hoofd]
    uit = [{'name': n[:60], 'date': pd.Timestamp(d), 'discipline': _sport_uit_tekst(n) or sport}
           for n, d in races[:3]]
    return sorted(uit, key=lambda g: g['date'])


def hoofddoel_zonder_datum(v, goals):
    """Het hoofddoel uit de intake als het nog geen datum heeft en nog niet bij de A-doelen staat."""
    if not v:
        return None
    hoofd = intake._hoofddoel(v)
    if not hoofd or intake._hoofd_race(v):
        return None
    if any(hoofd.lower() in g['name'].lower() or g['name'].lower() in hoofd.lower() for g in goals):
        return None
    return hoofd


def _stat(label, waarde, meta='', toon=''):
    return (f'<div class="dm-stat {toon}"><div class="dm-stat-label">{label}</div>'
            f'<div class="dm-stat-value">{waarde}</div><div class="dm-stat-meta">{meta}</div></div>')


def _render_nieuwe_atleet(open_standaard=False):
    with st.expander('＋ Nieuwe atleet', expanded=open_standaard):
        with st.form('nieuwe_atleet', clear_on_submit=True):
            c1, c2 = st.columns([2, 1])
            naam = c1.text_input('Naam')
            geb = c2.date_input('Geboortedatum', value=None, min_value=date(1940, 1, 1))
            c3, c4 = st.columns(2)
            sport = c3.selectbox('Hoofdsport', SPORTEN)
            contact = c4.text_input('Contact (e-mail / telefoon)')
            doelen = st.text_input('Doelen (kort)', placeholder='bv. Ironman Nice 2027')
            if st.form_submit_button('Atleet aanmaken', type='primary', use_container_width=True):
                if not naam.strip():
                    st.error('Een naam is het minimum.')
                else:
                    rij = store.bewaar_atleet({'naam': naam.strip(), 'geboortedatum': geb, 'sport': sport,
                                               'contact': contact, 'doelen': doelen})
                    _atleten.clear()
                    _kies_atleet(rij)
                    goto(PAGE_DASHBOARD)


def _opslag_ok():
    if not store.beschikbaar():
        st.warning('Opslag is nog niet geconfigureerd. Voeg `SUPABASE_URL` en `SUPABASE_KEY` toe '
                   'aan de secrets van de app (Streamlit Cloud → app → Settings → Secrets). '
                   'Tot dan werkt alles gewoon, maar blijft er niets bewaard na een herstart.')
        return False
    return True


def render_atleten_page():
    """Overzicht van alle atleten; een klik opent het dashboard van die atleet."""
    page_header('Atleten', 'Kies een atleet om het volledige dashboard te openen: intake, belastbaarheid, '
                'jaarplanning en testen op één plek.', eyebrow='Profielen')
    if not _opslag_ok():
        return
    try:
        alle = _atleten()
    except Exception as e:
        st.error(store.leesbare_fout(e))
        return

    _render_nieuwe_atleet(open_standaard=not alle)
    if not alle:
        st.caption('Nog geen atleten. Maak er hierboven een aan.')
        return

    zoek = st.text_input('Zoeken', placeholder='Zoek op naam, sport of doel…', label_visibility='collapsed')
    if zoek.strip():
        z = zoek.strip().lower()
        alle = [a for a in alle if z in ' '.join(str(a.get(k) or '') for k in ('naam', 'sport', 'doelen')).lower()]

    st.markdown('<div style="height:.6rem"></div>', unsafe_allow_html=True)
    for start in range(0, len(alle), 3):
        cols = st.columns(3, gap='medium')
        for col, a in zip(cols, alle[start:start + 3]):
            with col:
                lft = _leeftijd(a.get('geboortedatum'))
                meta = ' · '.join(x for x in [a.get('sport'), f'{lft} jaar' if lft else None] if x)
                initialen = ''.join(w[0] for w in a['naam'].split()[:2]).upper()
                st.markdown(
                    f'<div class="dm-athlete-card"><div class="dm-avatar">{intake._e(initialen)}</div>'
                    f'<div class="dm-athlete-name">{intake._e(a["naam"])}</div>'
                    f'<div class="dm-athlete-meta">{intake._e(meta) or "&nbsp;"}</div>'
                    f'<div class="dm-athlete-goal">{intake._e(a.get("doelen") or "Nog geen doel ingesteld")}</div></div>',
                    unsafe_allow_html=True)
                if st.button('Dashboard openen', key=f"open_atleet_{a['id']}", use_container_width=True):
                    _kies_atleet(a)
                    goto(PAGE_DASHBOARD)
        st.markdown('<div style="height:.9rem"></div>', unsafe_allow_html=True)


def render_dashboard_page():
    """Eén atleet, alle tools: het startpunt voor elke beslissing over die atleet."""
    atleet = st.session_state.get('atleet')
    if not atleet:
        page_header('Atleetdashboard', 'Kies eerst een atleet.', eyebrow='Dashboard')
        if store.beschikbaar():
            if st.button('Naar het atletenoverzicht', type='primary'):
                goto(PAGE_ATLETEN)
        else:
            _opslag_ok()
        return

    naam = atleet['naam']
    intake_rec = _intake_record(atleet)
    v = _intake_velden(intake_rec)
    analyse = st.session_state.get('athletes', {}).get(naam)
    goals = st.session_state.get(f'a_goals_{naam}', [])
    try:
        docs = store.lijst_records(atleet['id'])
    except Exception:
        docs = []
    testen = [d for d in docs if d['soort'] in ('prestatietest', 'voeding')]

    # --- Kop ----------------------------------------------------------------
    lft = _leeftijd(atleet.get('geboortedatum'))
    meta = ' · '.join(x for x in [atleet.get('sport'), f'{lft} jaar' if lft else None, atleet.get('contact')] if x)
    initialen = ''.join(w[0] for w in naam.split()[:2]).upper()
    st.markdown(
        f'<div class="dm-profile-head"><div class="dm-avatar lg">{intake._e(initialen)}</div><div>'
        f'<div class="dm-eyebrow">Atleetdashboard</div><div class="dm-page-title">{intake._e(naam)}</div>'
        f'<div class="dm-profile-meta">{intake._e(meta)}</div></div></div>', unsafe_allow_html=True)

    # --- Kerncijfers --------------------------------------------------------
    if analyse:
        cur = analyse['summary']['acwr']['current']
        level, status = belastbaarheid_status(cur)
        bel = _stat('Belastbaarheid', fmt(cur, 1) if cur is not None else '–', status,
                    {'ok': 'ok', 'warn': 'warn', 'alert': 'alert'}.get(level, ''))
    else:
        bel = _stat('Belastbaarheid', '–', 'Nog geen analyse')
    toekomst = sorted([g for g in goals if pd.Timestamp(g['date']) >= pd.Timestamp.now().normalize()],
                      key=lambda g: pd.Timestamp(g['date']))
    if toekomst:
        g = toekomst[0]
        weken = max(0, (pd.Timestamp(g['date']) - pd.Timestamp.now().normalize()).days // 7)
        doel = _stat('Volgend A-doel', f'{weken} wk', f"{intake._e(g['name'])} · {pd.Timestamp(g['date']).strftime('%d %b %Y')}")
    else:
        doel = _stat('Volgend A-doel', '–', 'Geen A-doelen ingesteld')
    ik = _stat('Intake', 'Klaar' if v else '–',
               intake._e(v['algemeen']['datum']) if v else 'Nog geen intakeverslag', 'ok' if v else '')
    tst = _stat('Testen & plannen', str(len(testen)), 'Uit de prestatietest-suite')
    st.markdown(f'<div class="dm-stats">{bel}{doel}{ik}{tst}</div>', unsafe_allow_html=True)

    # --- Snelle acties: elke tool opent meteen voor deze atleet ---------------
    a1, a2, a3, a4 = st.columns(4)
    if a1.button('Intake' if not v else 'Intake bewerken', key='dash_intake', use_container_width=True):
        if intake_rec:
            _open_intake_record(intake_rec)
        else:
            _intake_wissen()
            _intake_naar_widgets(intake.leeg_intake())
            st.session_state[f'{IK}algemeen__naam'] = naam
        goto(PAGE_INTAKE)
    if a2.button('Belastbaarheid analyseren', key='dash_bel', use_container_width=True):
        goto(PAGE_BELASTBAARHEID)
    if a3.button('Jaarplanning', key='dash_jp', type='primary', use_container_width=True):
        goto(PAGE_JAARPLANNING)
    if a4.button('Prestatietest', key='dash_test', use_container_width=True):
        _suite_laad(None)
        goto(PAGE_TESTEN)

    st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)
    t_over, t_traj, t_intake, t_bel, t_jp, t_test, t_docs, t_prof = st.tabs(
        ['Overzicht', 'Trajectverslag', 'Intake', 'Belastbaarheid', 'Jaarplanning', 'Testen', 'Documenten', 'Profiel'])

    with t_over:
        links, rechts = st.columns([1.15, 1], gap='large')
        with links:
            if not render_intake_context(v, compact=True):
                st.markdown('<div class="dm-card"><div class="dm-card-title">Uit de intake</div>'
                            '<p style="color:var(--muted);margin:0">Nog geen intakeverslag. Start een intake '
                            'via de knop hierboven — doelen, beschikbaarheid en aandachtspunten verschijnen '
                            'dan hier en in de jaarplanning.</p></div>', unsafe_allow_html=True)
        with rechts:
            if analyse and analyse['summary'].get('advies'):
                html = ''.join(
                    f'<div class="dm-advies-item dm-advies-{i["level"]}"><div class="dm-advies-title">{i["title"]}</div>'
                    f'<div class="dm-advies-text">{i["text"]}</div></div>' for i in analyse['summary']['advies'][:3])
                st.markdown(f'<div class="dm-card"><div class="dm-card-title">Trainingsadvies</div>{html}</div>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<div class="dm-card"><div class="dm-card-title">Trainingsadvies</div>'
                            '<p style="color:var(--muted);margin:0">Verschijnt na een belastbaarheidsanalyse.</p>'
                            '</div>', unsafe_allow_html=True)
            if goals:
                chips = ''.join(f'<span class="dm-goal-chip">{intake._e(g["name"])} — '
                                f'{pd.Timestamp(g["date"]).strftime("%d %b %Y")}</span>' for g in goals)
                st.markdown(f'<div class="dm-card"><div class="dm-card-title">A-doelen</div>{chips}</div>',
                            unsafe_allow_html=True)

    with t_traj:
        if goals:
            bel_t = _belastbaarheid_voor(naam, JP_BRON_ANALYSE)
            plan_t = core.generate_jaarplanning(pd.Timestamp.now().normalize(), goals,
                                                bel_t['current'] if bel_t else None,
                                                profiel=(bel_t or {}).get('profiel'), gaps=(bel_t or {}).get('gaps'))
            render_trajectverslag(naam, v, plan_t, bel_t, titel='Trajectverslag', sleutel='dash')
        else:
            st.caption('Het trajectverslag vraagt minstens één A-doel. Open de jaarplanning: wedstrijden uit '
                       'de intake worden daar automatisch overgenomen.')

    with t_intake:
        if intake_rec and (intake_rec.get('data') or {}).get('html'):
            html = intake_rec['data']['html']
            c1, c2 = st.columns([1, 3])
            c1.download_button('Download verslag', data=html, file_name=f"Intakeverslag_{naam.replace(' ', '_')}.html",
                               mime='text/html', use_container_width=True, key='dash_intake_dl')
            c2.caption('Aanpassen? Klik bovenaan op "Intake bewerken".')
            components.html(html, height=1250, scrolling=True)
        else:
            st.caption('Nog geen intakeverslag voor deze atleet.')

    with t_bel:
        if analyse:
            render_dashboard(naam)
        else:
            st.caption('Nog geen belastbaarheidsanalyse. Klik bovenaan op "Belastbaarheid analyseren" en '
                       'upload het activities.csv-bestand — de analyse wordt automatisch hier bewaard.')

    with t_jp:
        if goals:
            bel_data = _belastbaarheid_voor(naam, JP_BRON_ANALYSE)
            render_belastbaarheid_readout(bel_data)
            st.markdown('<div style="height:.8rem"></div>', unsafe_allow_html=True)
            plan = core.generate_jaarplanning(pd.Timestamp.now().normalize(), goals,
                                              bel_data['current'] if bel_data else None,
                                              profiel=(bel_data or {}).get('profiel'),
                                              gaps=(bel_data or {}).get('gaps'))
            render_jaarplanning(plan, intake_v=v)
        else:
            st.caption('Nog geen A-doelen. Open de jaarplanning hierboven — wedstrijden uit de intake '
                       'worden daar als voorstel klaargezet.')

    with t_test:
        _render_testresultaten(atleet)

    with t_docs:
        _render_documenten(atleet)

    with t_prof:
        _render_profiel(atleet)


def _render_profiel(atleet):
    with st.form('profiel'):
        c1, c2 = st.columns([2, 1])
        naam = c1.text_input('Naam', value=atleet.get('naam') or '')
        geb_val = pd.to_datetime(atleet['geboortedatum']).date() if atleet.get('geboortedatum') else None
        geb = c2.date_input('Geboortedatum', value=geb_val, min_value=date(1940, 1, 1))
        c3, c4 = st.columns(2)
        sport = c3.selectbox('Hoofdsport', SPORTEN,
                             index=SPORTEN.index(atleet['sport']) if atleet.get('sport') in SPORTEN else 0)
        contact = c4.text_input('Contact', value=atleet.get('contact') or '')
        doelen = st.text_input('Doelen', value=atleet.get('doelen') or '')
        notities = st.text_area('Notities', value=atleet.get('intake') or '', height=160,
                                placeholder='Klachten, context, afspraken… (de volledige intake staat in het tabblad Intake)')
        if st.form_submit_button('Profiel bewaren', type='primary', use_container_width=True):
            rij = store.bewaar_atleet({'naam': naam.strip(), 'geboortedatum': geb, 'sport': sport,
                                       'contact': contact, 'doelen': doelen, 'intake': notities},
                                      atleet_id=atleet['id'])
            _atleten.clear()
            st.session_state['atleet'] = rij
            st.success('Profiel bewaard.')

    with st.expander('Atleet verwijderen'):
        st.caption('Verwijdert het profiel én alle documenten. Dit kan niet ongedaan gemaakt worden.')
        if st.checkbox(f'Ja, verwijder {atleet["naam"]} definitief', key='del_atleet_ok'):
            if st.button('Definitief verwijderen', key='del_atleet_btn'):
                store.verwijder_atleet(atleet['id'])
                _atleten.clear()
                st.session_state['atleet'] = None
                st.session_state['atleet_pending'] = GEEN_ATLEET
                st.session_state.get('athletes', {}).pop(atleet['naam'], None)
                st.session_state.pop(f"a_goals_{atleet['naam']}", None)
                goto(PAGE_ATLETEN)


def _render_documenten(atleet):
    st.caption('Alles wat je voor deze atleet maakt komt hier vanzelf bij: intakes, analyses, A-doelen en '
               'prestatietesten (via "Bewaren bij atleet" in de test). Een oudere test als JSON-bestand '
               '("Project opslaan") kan je hieronder nog toevoegen.')

    nr = st.session_state.get('doc_upload_nr', 0)
    up = st.file_uploader('Export uit de prestatietest-suite (.json)', type=['json'], key=f'doc_upload_{nr}')
    if up is not None:
        try:
            doc = json.loads(up.getvalue().decode('utf-8'))
            tt = doc.get('testType', '')
        except Exception:
            st.error('Dit is geen geldig JSON-bestand uit de suite.')
        else:
            soort = 'voeding' if tt == 'voeding' else 'prestatietest'
            adat = (doc.get('athlete') or {}).get('date') or ''
            anaam = (doc.get('athlete') or {}).get('name') or ''
            titel = f"{SUITE_NAMEN.get(tt, 'Test')} {adat}".strip()
            if anaam and anaam.strip().lower() != atleet['naam'].strip().lower():
                st.warning(f'Dit document is gemaakt voor "{anaam}", maar wordt bij **{atleet["naam"]}** bewaard.')
            if st.button(f'"{titel}" toevoegen aan {atleet["naam"]}', key='doc_add', type='primary'):
                store.bewaar_record(atleet['id'], soort, titel, doc)
                st.session_state['doc_upload_nr'] = nr + 1
                st.rerun()

    records = store.lijst_records(atleet['id'], met_data=True)
    if not records:
        st.caption('Nog geen documenten voor deze atleet.')
    for r in records:
        c1, c2, c3 = st.columns([5, 1.2, 1])
        datum = pd.to_datetime(r['aangemaakt_op']).strftime('%d %b %Y')
        soortnaam = 'Trajectverslag' if (r.get('data') or {}).get('type') == 'traject' else store.SOORTEN.get(r['soort'], r['soort'])
        c1.markdown(f"**{soortnaam}** — {r.get('titel') or ''}  \n"
                    f"<span style='color:{DM_MUTED};font-size:0.8rem'>{datum}</span>", unsafe_allow_html=True)
        if r['soort'] == 'belastbaarheid':
            if c2.button('Openen', key=f"rec_open_{r['id']}", use_container_width=True):
                _herstel_analyse(atleet, r)
                goto(PAGE_BELASTBAARHEID)
        elif r['soort'] == 'intake':
            if c2.button('Openen', key=f"rec_open_{r['id']}", use_container_width=True):
                _open_intake_record(r)
                goto(PAGE_INTAKE)
        elif r['soort'] in ('prestatietest', 'voeding'):
            if c2.button('Openen', key=f"rec_open_{r['id']}", use_container_width=True):
                _suite_laad(r)
                goto(PAGE_VOEDING if r['soort'] == 'voeding' else PAGE_TESTEN)
        elif r['soort'] == 'traject' or (r.get('data') or {}).get('type') == 'traject':
            c2.download_button('Download', data=(r.get('data') or {}).get('html', ''),
                               file_name=f"Trajectverslag_{atleet['naam'].replace(' ', '_')}_{datum.replace(' ', '')}.html",
                               mime='text/html', key=f"rec_dl_{r['id']}", use_container_width=True)
        elif r['soort'] == 'document':
            bestandsnaam = f"{atleet['naam'].replace(' ', '_')}_{r['soort']}_{datum.replace(' ', '')}.json"
            c2.download_button('Download', data=json.dumps(r['data'], ensure_ascii=False, indent=2),
                               file_name=bestandsnaam, mime='application/json',
                               key=f"rec_dl_{r['id']}", use_container_width=True)
        if c3.button('Verwijder', key=f"rec_del_{r['id']}", use_container_width=True,
                     help='Verwijdert dit document definitief'):
            store.verwijder_record(r['id'])
            st.rerun()


# ---------------------------------------------------------------------------
# Intake: opname van het gesprek → verslag in de huisstijl, bewaard bij de atleet.
# De formulierwaarden leven in session_state onder het prefix IK; de AI-output wordt
# daarin gezet vóór het formulier getekend wordt, zodat de coach ze meteen kan nalezen.
# ---------------------------------------------------------------------------
IK = 'ik__'


def _intake_naar_widgets(v):
    v = intake.normaliseer(v)
    for s, _, velden in intake.SECTIES:
        for veld, _, _ in velden:
            st.session_state[f'{IK}{s}__{veld}'] = v[s][veld]
    st.session_state[f'{IK}samenvatting'] = v['samenvatting']
    st.session_state[f'{IK}pakket'] = v['pakket']
    st.session_state[f'{IK}advies'] = v['advies']
    st.session_state[f'{IK}stappen'] = '\n'.join(v['volgende_stappen'])
    st.session_state['intake_open_vragen'] = v['open_vragen']


def _intake_uit_widgets():
    v = {s: {veld: st.session_state.get(f'{IK}{s}__{veld}', '') for veld, _, _ in velden}
         for s, _, velden in intake.SECTIES}
    v['samenvatting'] = st.session_state.get(f'{IK}samenvatting', '')
    v['pakket'] = st.session_state.get(f'{IK}pakket', '')
    v['advies'] = st.session_state.get(f'{IK}advies', '')
    v['volgende_stappen'] = st.session_state.get(f'{IK}stappen', '')
    v['open_vragen'] = st.session_state.get('intake_open_vragen') or []
    return intake.normaliseer(v)


def _intake_wissen():
    for k in [k for k in st.session_state if k.startswith(IK)]:
        del st.session_state[k]
    for k in ('intake_html', 'intake_record_id', 'intake_open_vragen', 'intake_flash', 'intake_tekst'):
        st.session_state.pop(k, None)
    st.session_state['intake_audio_nr'] = st.session_state.get('intake_audio_nr', 0) + 1


def _open_intake_record(record):
    data = record.get('data') or {}
    _intake_naar_widgets(data.get('velden') or {})
    st.session_state['intake_html'] = data.get('html')
    st.session_state['intake_record_id'] = record['id']


def _sport_uit_tekst(tekst):
    """Vrije sportomschrijving uit het gesprek → een van de profielkeuzes."""
    t = (tekst or '').lower()
    if not t.strip():
        return ''
    for sport, woorden in (('Triatlon', ('triat', 'triath')),
                           ('Lopen', ('lop', 'loop', 'run', 'marathon', 'trail')),
                           ('Fietsen', ('fiets', 'wieler', 'cycl', 'gravel', 'mtb', 'mountainbike')),
                           ('Zwemmen', ('zwem', 'swim'))):
        if any(w in t for w in woorden):
            return sport
    return 'Andere'


def _datum_uit_tekst(tekst):
    """Enkel een volledige datum wordt een geboortedatum; een los jaartal verzinnen we niet aan."""
    t = (tekst or '').strip()
    m = re.search(r'\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b', t)
    if m:
        d, mo, y = map(int, m.groups())
    else:
        m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', t)
        if not m:
            return None
        y, mo, d = map(int, m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _bewaar_intake(v, html):
    """Verslag bij de atleet zetten (profiel aanvullen + record) — geeft (atleet, fout) terug."""
    if not store.beschikbaar():
        return None, 'Opslag niet geconfigureerd — het verslag is gemaakt, maar niet bewaard.'
    naam = v['algemeen']['naam'].strip()
    if not naam:
        return None, 'Vul de naam van de atleet in om het verslag te bewaren.'
    huidig = st.session_state.get('atleet')
    atleet = huidig if huidig and huidig['naam'].strip().lower() == naam.lower() else store.zoek_atleet_op_naam(naam)

    # Het profiel krijgt wat de intake opleverde; lege velden overschrijven niets.
    profiel = {'naam': naam}
    sport = _sport_uit_tekst(v['algemeen']['sport'])
    doel = intake._hoofddoel(v) or v['doelen']['lange_termijn'] or v['doelen']['wedstrijden']
    geb = _datum_uit_tekst(v['algemeen']['geboortejaar'])
    samenvatting = '\n\n'.join(x for x in [v['samenvatting'], v['ervaring']['blessures']] if x.strip())
    for k, w in (('sport', sport), ('doelen', intake._kort(doel, 90)), ('contact', v['algemeen']['contact']),
                 ('geboortedatum', geb), ('intake', samenvatting)):
        if w:
            profiel[k] = w
    rij = store.bewaar_atleet(profiel, atleet_id=atleet['id'] if atleet else None)
    record = store.bewaar_record(rij['id'], 'intake', f"Intake {v['algemeen']['datum']}",
                                 {'velden': v, 'html': html},
                                 record_id=st.session_state.get('intake_record_id'))
    st.session_state['intake_record_id'] = record.get('id')
    _atleten.clear()
    _kies_atleet(rij)
    return rij, None


def _verwerk_intake(audio=None, tekst=''):
    """Opname of tekst → ingevulde formuliervelden. Geeft True bij succes."""
    sleutel = intake.openai_sleutel()
    atleet_naam = (st.session_state.get('atleet') or {}).get('naam', '')
    coach_naam = st.session_state.get(f'{IK}coach__naam', '')
    with st.status('Gesprek verwerken…', expanded=True) as status:
        try:
            if audio is not None:
                st.write('Opname voorbereiden…')
                transcript = intake.transcribeer(audio.getvalue(), audio.name, sleutel,
                                                 hint=intake.transcriptie_hint(atleet_naam, coach_naam),
                                                 voortgang=st.write)
            else:
                transcript = tekst
            if len(transcript.strip()) < 40:
                raise ValueError('Er kwam vrijwel geen tekst uit de opname. Is dit de juiste opname, '
                                 'en staat er gesproken Nederlands op?')
            st.write('Verslag invullen…')
            v = intake.extraheer(transcript, sleutel, atleet_naam=atleet_naam)
        except Exception as e:
            status.update(label='Verwerken mislukt', state='error')
            st.error(intake.leesbare_fout(e))
            return False
        status.update(label='Klaar — lees het verslag hieronder na en corrigeer waar nodig.',
                      state='complete', expanded=False)
    # De coachgegevens komen uit het formulier, niet uit het gesprek.
    for veld in ('naam', 'email', 'gsm'):
        v['coach'][veld] = st.session_state.get(f'{IK}coach__{veld}') or v['coach'][veld]
    _intake_naar_widgets(v)
    st.session_state['intake_html'] = None
    st.session_state['intake_record_id'] = None
    return True


def _intake_sectie(s, velden):
    inputs = [f for f in velden if f[2] == 'input']
    for i in range(0, len(inputs), 2):
        cols = st.columns(2)
        for col, (veld, label, _) in zip(cols, inputs[i:i + 2]):
            col.text_input(label, key=f'{IK}{s}__{veld}')
    for veld, label, _ in velden:
        if _ == 'area':
            st.text_area(label, key=f'{IK}{s}__{veld}', height=80)


def render_intake_page():
    kop1, kop2 = st.columns([5, 1.2])
    kop1.markdown('<div class="dm-eyebrow">Intake</div><div class="dm-page-title">Intakegesprek</div>', unsafe_allow_html=True)
    if kop2.button('Nieuwe intake', key='intake_nieuw', use_container_width=True):
        _intake_wissen()
        st.rerun()
    render_traject('intake')
    st.caption('Upload de opname van het intakegesprek: de tool schrijft ze uit en vult het verslag in. '
               'Jij leest na en corrigeert; daarna verschijnt het verslag in de huisstijl en wordt het '
               'bij de atleet bewaard.')
    if f'{IK}coach__naam' not in st.session_state:
        _intake_naar_widgets(intake.leeg_intake())
    flash = st.session_state.pop('intake_flash', None)
    if flash:
        st.success(flash)

    # --- 1 · Gesprek ---------------------------------------------------------
    st.markdown('##### 1 · Gesprek')
    if not intake.openai_sleutel():
        st.warning('Nog geen OpenAI-sleutel: voeg `OPENAI_API_KEY` toe aan de secrets van de app '
                   '(Streamlit Cloud → Settings → Secrets). Tot dan vul je het verslag hieronder handmatig in.')
    else:
        tab_audio, tab_tekst = st.tabs(['Opname uploaden', 'Tekst plakken'])
        with tab_audio:
            nr = st.session_state.get('intake_audio_nr', 0)
            up = st.file_uploader('Opname van het gesprek', type=intake.AUDIO_TYPES, key=f'intake_audio_{nr}',
                                  help='m4a (iPhone Dictafoon), mp3, wav, mp4, … — tot 400 MB. '
                                       'Een gesprek van een uur is in enkele minuten verwerkt.')
            if up is not None and st.button('Gesprek verwerken', key='intake_verwerk_audio', type='primary'):
                if _verwerk_intake(audio=up):
                    st.session_state['intake_audio_nr'] = nr + 1
        with tab_tekst:
            tekst = st.text_area('Transcript of notities', key='intake_tekst', height=140,
                                 placeholder='Bv. het transcript van een Teams-opname, of je eigen notities.')
            if tekst.strip() and st.button('Tekst verwerken', key='intake_verwerk_tekst', type='primary'):
                _verwerk_intake(tekst=tekst)
        st.caption('De opname dient enkel om het transcript te maken en wordt daarna weggegooid; ook het '
                   'transcript blijft niet bewaard — alleen het verslag. Laat de atleet vooraf weten dat het '
                   'gesprek opgenomen en door OpenAI verwerkt wordt.')

    # --- 2 · Nalezen ---------------------------------------------------------
    st.markdown('##### 2 · Verslag nalezen')
    open_vragen = st.session_state.get('intake_open_vragen') or []
    if open_vragen:
        st.info('**Nog na te vragen** (komt niet in het verslag):\n' + '\n'.join(f'- {q}' for q in open_vragen))
    with st.form('intake_form'):
        st.text_area('Samenvatting', key=f'{IK}samenvatting', height=100)
        for s, titel, velden in intake.SECTIES:
            if s == 'afspraken':
                st.radio('Coachingpakket', [''] + list(intake.PAKKET_LABELS), key=f'{IK}pakket',
                         format_func=lambda k: intake.PAKKET_LABELS.get(k, 'Nog te bepalen'), horizontal=True)
            with st.expander(titel, expanded=s not in ('coach', 'facturatie', 'afspraken')):
                _intake_sectie(s, velden)
        st.text_area('Advies van de coach', key=f'{IK}advies', height=160,
                     help='Voorstel van de tool op basis van het gesprek — pas aan in je eigen woorden.')
        st.text_area('Volgende stappen (één per regel)', key=f'{IK}stappen', height=110)
        if st.form_submit_button('Verslag maken & bewaren', type='primary', use_container_width=True):
            v = _intake_uit_widgets()
            html = intake.verslag_html(v)
            st.session_state['intake_html'] = html
            try:
                rij, fout = _bewaar_intake(v, html)
            except Exception as e:
                rij, fout = None, f'Het verslag is gemaakt, maar bewaren lukte niet: {e}'
            if fout:
                st.warning(fout)
            else:
                st.session_state['intake_flash'] = f'Verslag bewaard bij {rij["naam"]} — zie ook de tegel Atleten.'
                st.rerun()

    # --- 3 · Verslag ---------------------------------------------------------
    html = st.session_state.get('intake_html')
    if html:
        st.markdown('##### 3 · Verslag')
        naam = (st.session_state.get(f'{IK}algemeen__naam') or 'atleet').strip().replace(' ', '_')
        c1, c2 = st.columns([1, 3])
        c1.download_button('Download (.html)', data=html, file_name=f'Intakeverslag_{naam}.html',
                           mime='text/html', use_container_width=True, key='intake_dl')
        c2.caption('PDF: klik "Bewaar als PDF" in het verslag, of open het in een nieuw tabblad en '
                   'kies ⌘P → Bewaar als PDF. Aanpassen? Wijzig hierboven en klik opnieuw op '
                   '"Verslag maken & bewaren".')
        components.html(html, height=1250, scrolling=True)

        atleet = st.session_state.get('atleet')
        if atleet and st.session_state.get('intake_record_id'):
            st.markdown('##### Volgende stap')
            n1, n2 = st.columns(2)
            if n1.button('Verder: belastbaarheidsanalyse →', key='ik_naar_bel', type='primary', use_container_width=True):
                goto(PAGE_BELASTBAARHEID)
            if n2.button('Geen Strava-data? Meteen naar de jaarplanning →', key='ik_naar_jp', use_container_width=True):
                _naar_jaarplanning(atleet['naam'])


# ---------------------------------------------------------------------------
# Prestatietesten & voeding: de suite als component in de app
# ---------------------------------------------------------------------------

def _suite_laad(record):
    """Zet een bewaarde test klaar om te openen (of None = nieuwe, lege test). De nonce zegt de
    suite dat ze opnieuw moet laden; zonder nieuwe nonce blijft het werk van de coach staan."""
    st.session_state['suite_project'] = (record or {}).get('data')
    st.session_state['suite_record_id'] = (record or {}).get('id')
    st.session_state['suite_titel'] = (record or {}).get('titel')
    st.session_state['suite_nonce'] = st.session_state.get('suite_nonce', 0) + 1


def _suite_bewaar(atleet, waarde):
    project = waarde.get('project') or {}
    samenvatting = waarde.get('summary') or {}
    tt = project.get('testType', 'lactate')
    soort = 'voeding' if tt == 'voeding' else 'prestatietest'
    datum = (project.get('athlete') or {}).get('date') or date.today().isoformat()
    titel = f"{SUITE_NAMEN.get(tt, 'Test')} {datum}".strip()
    data = dict(project)
    data['summary'] = samenvatting
    # Een geopende test wordt bijgewerkt; een nieuwe test wordt een nieuw document.
    rid = st.session_state.get('suite_record_id')
    rec = store.bewaar_record(atleet['id'], soort, titel, data, record_id=rid)
    st.session_state['suite_record_id'] = rec.get('id', rid)
    st.session_state['suite_titel'] = titel
    return titel


def render_testen_page(voeding=False):
    if voeding:
        page_header('Wedstrijdvoeding', 'Voeding per minuut uitgeschreven: gels, vocht en zout, afgestemd op '
                    'afstand, niveau en weer (ACSM-richtwaarden).', eyebrow='Voedingsplan')
    else:
        page_header('Prestatietesten', 'Lactaattest (LT1/LT2 en zones), Critical Power, Critical Swim Speed en '
                    'de 3/5 km looptest — met printbaar verslag.', eyebrow='Testen')

    atleet = st.session_state.get('atleet')
    kan_bewaren = bool(atleet and store.beschikbaar())
    soort = 'voeding' if voeding else 'prestatietest'

    # Eerdere testen van deze atleet openen, of een nieuwe beginnen
    if kan_bewaren:
        try:
            eerder = store.lijst_records(atleet['id'], soort=soort)
        except Exception:
            eerder = []
        c1, c2, c3 = st.columns([3, 1.1, 1.1])
        labels = {r['id']: f"{r.get('titel') or 'Test'} · {pd.to_datetime(r['aangemaakt_op']).strftime('%d %b %Y')}"
                  for r in eerder}
        keuze = c1.selectbox('Eerdere testen', [''] + list(labels), format_func=lambda k: labels.get(k, '— kies een eerdere test —'),
                             label_visibility='collapsed', key=f'suite_keuze_{soort}')
        if c2.button('Openen', key=f'suite_open_{soort}', disabled=not keuze, use_container_width=True):
            _suite_laad(store.haal_record(keuze))
            st.rerun()
        if c3.button('Nieuwe test', key=f'suite_nieuw_{soort}', use_container_width=True):
            _suite_laad(None)
            st.rerun()
        if st.session_state.get('suite_record_id'):
            st.caption(f"Geopend: **{st.session_state.get('suite_titel') or 'bewaarde test'}** — "
                       f"\"Bewaren bij atleet\" werkt deze test bij.")
    elif not atleet:
        st.caption('Kies een atleet in de zijbalk: dan staan zijn gegevens meteen ingevuld en bewaar je de '
                   'test met één klik in zijn dashboard. Zonder atleet werkt de suite ook, dan bewaar je via '
                   '"Project opslaan".')

    project = st.session_state.get('suite_project')
    if project and (project.get('testType') == 'voeding') != voeding:
        project = None      # een voedingsplan opent niet in de testen-pagina en omgekeerd
    args = {
        'nonce': f"{soort}-{st.session_state.get('suite_nonce', 0)}-{(atleet or {}).get('id', '')}",
        'project': project,
        'testType': 'voeding' if voeding else None,
        'canSave': kan_bewaren,
        'athlete': {'name': atleet.get('naam', ''), 'sport': atleet.get('sport') or '',
                    'goal': atleet.get('doelen') or ''} if atleet else None,
    }
    waarde = _suite_component(**args, key=f'suite_{soort}', default=None)

    if isinstance(waarde, dict) and waarde.get('action') == 'save' \
            and waarde.get('id') != st.session_state.get('suite_laatst_bewaard'):
        st.session_state['suite_laatst_bewaard'] = waarde.get('id')
        if kan_bewaren:
            try:
                titel = _suite_bewaar(atleet, waarde)
                st.toast(f'{titel} bewaard bij {atleet["naam"]}.')
            except Exception as e:
                st.error(f'Bewaren lukte niet. {store.leesbare_fout(e)}')


def _render_testresultaten(atleet):
    """Kerncijfers en zones van de bewaarde testen — de bron voor trainingszones in de planning."""
    try:
        recs = [r for r in store.lijst_records(atleet['id'], met_data=True)
                if r['soort'] in ('prestatietest', 'voeding')]
    except Exception as e:
        st.caption(store.leesbare_fout(e))
        return
    if not recs:
        st.caption('Nog geen testen. Open "Prestatietest" bovenaan, vul de test in en klik op '
                   '"Bewaren bij atleet" — de resultaten verschijnen dan hier.')
        return
    for r in recs:
        som = (r.get('data') or {}).get('summary') or {}
        datum = pd.to_datetime(r['aangemaakt_op']).strftime('%d %b %Y')
        kpis = ''.join(f'<div class="dm-kv-item"><div class="dm-kv-k">{intake._e(k)}</div>'
                       f'<div class="dm-kv-v">{intake._e(v)}</div></div>' for k, v in som.get('kpis', []))
        zones = ''
        if som.get('zones'):
            rijen = ''.join(f'<tr><td><b>{intake._e(z["name"])}</b> {intake._e(z.get("label", ""))}</td>'
                            f'<td>{intake._e(z["hr"])}</td><td>{intake._e(z["tempo"])}</td></tr>' for z in som['zones'])
            zones = (f'<table class="dm-zones"><thead><tr><th>Zone</th><th>Hartslag</th><th>Tempo / vermogen</th>'
                     f'</tr></thead><tbody>{rijen}</tbody></table>')
        inhoud = (f'<div class="dm-kv dm-kv-grid">{kpis}</div>' if kpis else
                  '<p style="color:var(--muted);margin:0">Geen samenvatting — open de test om de resultaten te zien.</p>')
        st.markdown(f'<div class="dm-card"><div class="dm-card-title">{intake._e(r.get("titel") or "Test")}'
                    f'<span class="dm-card-sub">{datum}</span></div>{inhoud}{zones}</div>', unsafe_allow_html=True)
        if st.button('Openen', key=f"testres_open_{r['id']}"):
            _suite_laad(r)
            goto(PAGE_VOEDING if r['soort'] == 'voeding' else PAGE_TESTEN)


def render_analyse_form(open_standaard):
    """Nieuwe analyse: staat nu op de pagina zelf (vroeger in de zijbalk)."""
    with st.expander('Nieuwe analyse — activities.csv uploaden', expanded=open_standaard):
        geselecteerd = (st.session_state.get('atleet') or {}).get('naam', '')
        c1, c2 = st.columns([2, 1])
        athlete_name = c1.text_input('Naam atleet', value=geselecteerd, placeholder='bv. Jan Peeters')
        today_override = c2.date_input('Referentiedatum', value=pd.Timestamp.now().normalize().date())
        uploaded_file = st.file_uploader('activities.csv uit de Strava-export', type=['csv'])
        st.caption('Pak de Strava-export (.zip) uit en upload enkel het bestand **activities.csv** daaruit.')
        if st.button('Analyseer', type='primary', disabled=not (athlete_name and uploaded_file)):
            with st.spinner('Bezig met analyseren...'):
                analyze_and_store(uploaded_file, athlete_name, pd.Timestamp(today_override))
            st.rerun()


def render_belastbaarheid_page():
    page_header('Belastbaarheid', 'Trainingslast en A:C ratio uit een Strava-export.', eyebrow='Analyse')
    render_traject('belastbaarheid')
    athletes = list(st.session_state.get('athletes', {}).keys())
    actief = st.session_state.get('atleet')
    # De actieve atleet heeft voorrang; anders de laatst geanalyseerde.
    if actief and actief['naam'] in athletes:
        st.session_state['active_athlete'] = actief['naam']
    active = st.session_state.get('active_athlete')
    render_analyse_form(open_standaard=not active)
    if len(athletes) > 1 and not actief:
        active = st.selectbox('Geanalyseerde atleet', athletes,
                              index=athletes.index(active) if active in athletes else 0)
        st.session_state['active_athlete'] = active
    if not active:
        st.markdown(f"""
        <div class="dm-empty-state">
          <div class="dm-empty-icon">{ICONS["upload"]}</div>
          <div class="dm-empty-title">Nog geen analyse</div>
          <div class="dm-empty-desc">Vul hierboven de naam van de atleet in en upload het <strong>activities.csv</strong>-bestand
          uit de Strava-export. Klik daarna op <strong>Analyseer</strong> om het dashboard te zien.</div>
        </div>
        """, unsafe_allow_html=True)
        return
    render_dashboard(active)


def main():
    inject_brand_css()
    if not check_password():
        return

    page = current_page()
    render_topbar(page)

    if page in (PAGE_HOME, PAGE_ATLETEN):
        render_roster()
    elif page == PAGE_TESTEN:
        render_testen_page()
    elif page == PAGE_VOEDING:
        render_testen_page(voeding=True)
    elif page == PAGE_DASHBOARD:
        render_dashboard_page()
    elif page == PAGE_INTAKE:
        render_intake_page()
    elif page == PAGE_BELASTBAARHEID:
        render_belastbaarheid_page()
    elif page == PAGE_JAARPLANNING:
        render_jaarplanning_page()
    else:
        render_roster()


if __name__ == '__main__':
    main()
