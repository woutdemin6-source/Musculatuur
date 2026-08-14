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

import numpy as np
import pandas as pd
import streamlit as st
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

st.set_page_config(page_title='De Musculatuur — AI performance assistent', page_icon='💪', layout='wide')

DEFAULT_PASSWORD = 'musculatuur2026'

# ---------------------------------------------------------------------------
# Huisstijl De Musculatuur
# Kleuren/fonts overgenomen van demusculatuur.be (crème/perzik achtergronden,
# bordeaux serif koppen, saliegroen als actiekleur, donkerbruine sidebar zoals
# hun footer). Live CSS kon niet opgehaald worden (geen browsertoegang vanuit
# deze sessie) — dit is gebaseerd op de aangeleverde screenshots. Zet een
# logo.png in deze map en de header gebruikt 'm automatisch i.p.v. de
# tekst-wordmark hieronder.
# ---------------------------------------------------------------------------
DM_MAROON = '#5B1F2C'
DM_GREEN = '#6FA98A'
DM_GREEN_DARK = '#5C9179'
DM_CREAM = '#F2E6DE'
DM_PEACH = '#F0D7B7'
DM_BROWN = '#3B2820'
DM_MUTED = '#6E7B99'
DM_BG = '#FBF6F2'

BRAND_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Poppins:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{ font-family: 'Poppins', sans-serif; }}

.stApp {{ background-color: {DM_BG}; }}

.block-container {{ padding-top: 2rem; max-width: 1100px; }}

h1, h2, h3 {{ font-family: 'Playfair Display', serif !important; color: {DM_MAROON} !important; }}

div[data-testid="stCaptionContainer"], small {{ color: {DM_MUTED} !important; }}

/* ---- Premium hero-banner (logo groot, bovenaan) ---- */
.dm-hero {{
    background: linear-gradient(135deg, {DM_CREAM} 0%, {DM_PEACH} 100%);
    border-radius: 28px;
    padding: 3rem 2rem 2.75rem 2rem;
    text-align: center;
    margin-bottom: 2.25rem;
    box-shadow: 0 12px 34px rgba(59,40,32,0.10);
}}
.dm-hero-mark {{
    width: 88px; height: 88px; margin: 0 auto 1.1rem auto;
    background: #1a1a1a; border-radius: 20px;
    display: flex; align-items: center; justify-content: center;
    color: #FFFFFF; font-family: 'Playfair Display', serif; font-weight: 700; font-size: 46px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.18);
}}
.dm-hero-logo-img {{ height: 88px; margin: 0 auto 1.1rem auto; display: block; }}
.dm-hero-name {{ font-family: 'Playfair Display', serif; font-weight: 700; font-size: 2.5rem; color: #1a1a1a; margin-bottom: 0.15rem; }}
.dm-hero-tagline {{ font-family: 'Poppins', sans-serif; font-size: 12px; letter-spacing: 4px;
    color: {DM_GREEN_DARK}; text-transform: uppercase; font-weight: 700; margin-bottom: 1.15rem; }}
.dm-hero-sub {{ font-family: 'Playfair Display', serif; font-size: 1.35rem; color: {DM_MAROON}; font-weight: 700; }}
.dm-hero-desc {{ font-family: 'Poppins', sans-serif; color: {DM_MUTED}; font-size: 0.95rem; margin-top: 0.35rem; }}

/* ---- Lege staat (nog geen atleet geanalyseerd) ---- */
.dm-empty-state {{
    background: #FFFFFF; border: 2px dashed #E3D5C8; border-radius: 24px;
    padding: 4rem 2rem; text-align: center; margin-top: 0.5rem;
}}
.dm-empty-icon {{ font-size: 2.8rem; margin-bottom: 0.75rem; }}
.dm-empty-title {{ font-family: 'Playfair Display', serif; color: {DM_MAROON}; font-size: 1.4rem; font-weight: 700; margin-bottom: 0.5rem; }}
.dm-empty-desc {{ font-family: 'Poppins', sans-serif; color: {DM_MUTED}; font-size: 0.95rem; max-width: 440px; margin: 0 auto; line-height: 1.6; }}
.dm-empty-desc strong {{ color: {DM_MAROON}; }}

/* Sidebar in het donkerbruin van hun footer */
section[data-testid="stSidebar"] {{ background-color: {DM_BROWN}; padding-top: 0.5rem; }}
section[data-testid="stSidebar"] * {{ color: {DM_CREAM} !important; }}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{
    color: #FFFFFF !important;
}}
section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea {{
    color: {DM_BROWN} !important;
}}
section[data-testid="stSidebar"] .dm-sidebar-section {{
    color: #FFFFFF !important; font-family: 'Playfair Display', serif; font-weight: 700;
    font-size: 1.15rem; margin: 0.25rem 0 0.9rem 0;
}}
section[data-testid="stSidebar"] .dm-step {{
    color: {DM_GREEN} !important; font-family: 'Poppins', sans-serif; font-size: 11px;
    letter-spacing: 1.5px; text-transform: uppercase; font-weight: 700; margin: 1rem 0 0.3rem 0;
}}
section[data-testid="stSidebar"] .dm-sidebar-divider {{
    height: 1px; background: rgba(255,255,255,0.14); margin: 1.2rem 0; border: none;
}}

/* Upload-zone: mooie, duidelijke drop-zone i.p.v. het standaard grijze vakje */
[data-testid="stFileUploaderDropzone"] {{
    background: #FFFFFF !important;
    border: 2px dashed {DM_GREEN} !important;
    border-radius: 16px !important;
    padding: 0.5rem !important;
    transition: border-color 0.15s ease, background 0.15s ease;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
    border-color: {DM_GREEN_DARK} !important;
    background: #F6FBF8 !important;
}}
[data-testid="stFileUploaderDropzone"] button {{
    background-color: {DM_GREEN} !important; color: #FFFFFF !important; border-radius: 999px !important;
}}

/* Knoppen: saliegroene pil, zoals "Reserveren"/"Toevoegen" op de site */
.stButton > button, .stDownloadButton > button {{
    background-color: {DM_GREEN};
    color: #FFFFFF;
    border: none;
    border-radius: 999px;
    font-weight: 600;
    padding: 0.5rem 1.5rem;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    background-color: {DM_GREEN_DARK};
    color: #FFFFFF;
}}
.stButton > button:disabled, .stButton > button:disabled:hover {{
    background-color: #FFFFFF !important;
    color: {DM_BROWN} !important;
    opacity: 1 !important;
    border: 1.5px solid #C9BBA8 !important;
}}
.stButton > button:disabled p, .stButton > button:disabled span, .stButton > button:disabled div {{
    color: {DM_BROWN} !important;
    opacity: 1 !important;
}}

/* Tabs in serif, actieve tab in saliegroen */
.stTabs [data-baseweb="tab"] {{ font-family: 'Playfair Display', serif; color: {DM_MAROON}; font-weight: 600; }}
.stTabs [aria-selected="true"] {{ color: {DM_GREEN} !important; border-bottom-color: {DM_GREEN} !important; }}

/* Expander-titel (Methodologie) */
[data-testid="stExpander"] summary {{ font-family: 'Playfair Display', serif; color: {DM_MAROON}; font-weight: 600; }}

/* Alerts iets ronder, past bij de kaartjes-stijl van de site */
div[data-testid="stAlert"] {{ border-radius: 12px; }}

/* Logo-lockup */
.dm-logo-wrap {{ display: flex; align-items: center; gap: 14px; margin-bottom: 0.35rem; }}
.dm-logo-mark {{
    width: 46px; height: 46px; min-width: 46px;
    background: #1a1a1a; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    color: #FFFFFF; font-family: 'Playfair Display', serif; font-weight: 700; font-size: 24px;
}}
.dm-logo-text .name {{ font-family: 'Playfair Display', serif; font-weight: 700; font-size: 21px; color: #1a1a1a; line-height: 1.1; }}
.dm-logo-text .tagline {{ font-family: 'Poppins', sans-serif; font-size: 10px; letter-spacing: 2.5px;
    color: {DM_GREEN}; text-transform: uppercase; font-weight: 600; }}
section[data-testid="stSidebar"] .dm-logo-text .name {{ color: #FFFFFF !important; }}

.dm-page-title {{ font-family: 'Playfair Display', serif; color: {DM_MAROON}; font-size: 1.5rem;
    font-weight: 700; margin: 0.1rem 0 0.1rem 0; }}

/* Kernbevindingen-kaart, zoals de witte cards op de site */
.dm-card {{
    background: #FFFFFF; border-radius: 16px; padding: 1.25rem 1.5rem;
    box-shadow: 0 2px 10px rgba(59,40,32,0.08); border-left: 4px solid {DM_GREEN};
    margin-bottom: 0.5rem;
}}
.dm-card-title {{ font-family: 'Playfair Display', serif; color: {DM_MAROON}; font-size: 1.15rem;
    font-weight: 700; margin-bottom: 0.6rem; }}
.dm-bullet-list {{ margin: 0; padding-left: 1.1rem; }}
.dm-bullet-list li {{ color: #45403c; line-height: 1.55; margin-bottom: 0.35rem; }}
.dm-bullet-list strong {{ color: {DM_MAROON}; }}

/* Trainingsadvies-kaart */
.dm-advies-item {{ border-radius: 12px; padding: 0.85rem 1.1rem; margin-bottom: 0.6rem; border-left: 4px solid; }}
.dm-advies-item:last-child {{ margin-bottom: 0; }}
.dm-advies-title {{ font-family: 'Poppins', sans-serif; font-weight: 700; font-size: 0.95rem; margin-bottom: 0.2rem; }}
.dm-advies-text {{ font-family: 'Poppins', sans-serif; font-size: 0.9rem; line-height: 1.55; color: #45403c; }}
.dm-advies-alert {{ background: #FBE7E2; border-left-color: #a13a2a; }}
.dm-advies-alert .dm-advies-title {{ color: #a13a2a; }}
.dm-advies-warning {{ background: #FDF3E0; border-left-color: #8a6a1f; }}
.dm-advies-warning .dm-advies-title {{ color: #8a6a1f; }}
.dm-advies-positive {{ background: #E3F3EA; border-left-color: #2f6b4f; }}
.dm-advies-positive .dm-advies-title {{ color: #2f6b4f; }}
.dm-advies-info {{ background: #EEF1F6; border-left-color: {DM_MUTED}; }}
.dm-advies-info .dm-advies-title {{ color: {DM_MUTED}; }}

/* Jaarplanning-blokken (macro/mesocycli per A-doel) */
.dm-plan-block {{ border-radius: 12px; padding: 0.85rem 1.1rem; margin-bottom: 0.6rem; border-left: 4px solid; }}
.dm-plan-block:last-child {{ margin-bottom: 0; }}
.dm-plan-header {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.5rem; }}
.dm-plan-fase {{ font-family: 'Playfair Display', serif; font-weight: 700; font-size: 1rem; color: {DM_BROWN}; }}
.dm-plan-dates {{ font-family: 'Poppins', sans-serif; font-size: 0.8rem; color: {DM_MUTED}; white-space: nowrap; }}
.dm-plan-meta {{ font-family: 'Poppins', sans-serif; font-size: 0.8rem; color: {DM_MUTED}; margin-top: 0.15rem; font-weight: 600; }}
.dm-plan-focus {{ font-family: 'Poppins', sans-serif; font-size: 0.9rem; color: #45403c; margin-top: 0.35rem; line-height: 1.5; }}
.dm-plan-note {{ font-family: 'Poppins', sans-serif; font-size: 0.82rem; color: {DM_MAROON}; margin-top: 0.4rem; font-style: italic; }}
.dm-plan-transitie {{ background: #EEF1F6; border-left-color: {DM_MUTED}; }}
.dm-plan-basis1, .dm-plan-basis2, .dm-plan-basis3 {{ background: #FBEFE0; border-left-color: #a8712a; }}
.dm-plan-opbouw1, .dm-plan-opbouw2 {{ background: #FDF3E0; border-left-color: #8a6a1f; }}
.dm-plan-piek {{ background: #F3E3E0; border-left-color: #8a3a2a; }}
.dm-plan-taper_afbouw, .dm-plan-wedstrijdweek {{ background: #FBE7E2; border-left-color: #a13a2a; }}
.dm-goal-chip {{
    display: inline-flex; align-items: center; gap: 0.5rem; background: #FFFFFF;
    border: 1px solid #E3D5C8; border-radius: 999px; padding: 0.4rem 0.9rem; margin: 0 0.4rem 0.4rem 0;
    font-family: 'Poppins', sans-serif; font-size: 0.85rem; color: {DM_MAROON};
}}

/* ---- Tool-tegels op de welkomstpagina ---- */
.dm-tool-card {{
    background: #FFFFFF; border-radius: 20px; padding: 1.6rem 1.4rem 1.3rem 1.4rem;
    box-shadow: 0 3px 14px rgba(59,40,32,0.09); border-top: 5px solid {DM_GREEN};
    height: 100%; display: flex; flex-direction: column;
}}
.dm-tool-card.soon {{ border-top-color: #C9BBA8; background: #FCFAF8; }}
.dm-tool-icon {{ font-size: 2rem; line-height: 1; margin-bottom: 0.7rem; }}
.dm-tool-title {{ font-family: 'Playfair Display', serif; color: {DM_MAROON}; font-size: 1.2rem;
    font-weight: 700; margin-bottom: 0.4rem; }}
.dm-tool-desc {{ font-family: 'Poppins', sans-serif; color: {DM_MUTED}; font-size: 0.88rem;
    line-height: 1.55; flex-grow: 1; }}
.dm-tool-badge {{
    display: inline-block; margin-top: 0.8rem; padding: 0.2rem 0.7rem; border-radius: 999px;
    font-family: 'Poppins', sans-serif; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.5px;
    text-transform: uppercase; background: #F0EAE3; color: #8a7a68;
}}

/* Compacte belastbaarheid-uitkomst (basis onder de jaarplanning) */
.dm-bel-readout {{
    background: #FFFFFF; border-radius: 16px; padding: 1.1rem 1.4rem;
    box-shadow: 0 2px 10px rgba(59,40,32,0.08); border-left: 4px solid {DM_GREEN};
    display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;
}}
.dm-bel-readout.warn {{ border-left-color: #8a6a1f; }}
.dm-bel-readout.alert {{ border-left-color: #a13a2a; }}
.dm-bel-readout.none {{ border-left-color: {DM_MUTED}; }}
.dm-bel-value {{ font-family: 'Playfair Display', serif; font-size: 2.1rem; font-weight: 700;
    color: {DM_MAROON}; line-height: 1; }}
.dm-bel-label {{ font-family: 'Poppins', sans-serif; font-size: 0.7rem; letter-spacing: 1.5px;
    text-transform: uppercase; color: {DM_MUTED}; font-weight: 700; margin-bottom: 0.2rem; }}
.dm-bel-status {{ font-family: 'Poppins', sans-serif; font-size: 0.95rem; font-weight: 600; color: #45403c; }}
.dm-bel-meta {{ font-family: 'Poppins', sans-serif; font-size: 0.8rem; color: {DM_MUTED}; margin-top: 0.15rem; }}

/* ---- Logo in de sidebar = knop terug naar de tool-keuze ----
   De knop wordt volledig ontdaan van z'n knop-uiterlijk en opgebouwd tot de logo-lockup:
   het zwarte "M"-vierkant komt uit ::before, de wordmark is het opschrift zelf. */
section[data-testid="stSidebar"] .st-key-logo_home button,
section[data-testid="stSidebar"] .st-key-logo_home button:hover,
section[data-testid="stSidebar"] .st-key-logo_home button:focus,
section[data-testid="stSidebar"] .st-key-logo_home button:active {{
    background: transparent !important; border: none !important; box-shadow: none !important;
    padding: 0 !important; min-height: 0 !important; justify-content: flex-start !important;
}}
section[data-testid="stSidebar"] .st-key-logo_home button p,
.dm-logo-static {{
    font-family: 'Playfair Display', serif !important; font-weight: 700 !important;
    font-size: 16px !important; color: #FFFFFF !important; line-height: 1.1 !important;
    display: inline-flex !important; align-items: center !important; margin: 0 !important;
}}
section[data-testid="stSidebar"] .st-key-logo_home button p::before,
.dm-logo-static::before {{
    content: 'M'; display: inline-flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; min-width: 36px; margin-right: 12px;
    background: #1a1a1a; color: #FFFFFF; border-radius: 8px;
    font-family: 'Playfair Display', serif; font-weight: 700; font-size: 18px;
}}
section[data-testid="stSidebar"] .st-key-logo_home button:hover p {{ opacity: 0.75; }}
section[data-testid="stSidebar"] .st-key-logo_home {{ margin-bottom: 0.1rem; }}
.dm-logo-tagline {{
    font-family: 'Poppins', sans-serif; font-size: 8px; letter-spacing: 2.5px;
    color: {DM_GREEN} !important; text-transform: uppercase; font-weight: 600;
    margin: 0 0 0.8rem 48px;
}}
</style>
"""


def inject_brand_css():
    st.markdown(BRAND_CSS, unsafe_allow_html=True)


@st.cache_data
def _logo_data_uri():
    """Zet logo.png (indien aanwezig) om naar een data-URI zodat we 'm inline in de HTML-hero kunnen tonen."""
    logo_path = os.path.join(os.path.dirname(__file__), 'logo.png')
    if os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        return f'data:image/png;base64,{b64}'
    return None


def render_logo(tagline='RECOVERY & PERFORMANCE', clickable=True):
    """Compacte logo-lockup bovenaan de sidebar, tevens de weg terug naar de tool-keuze.

    Bewust een Streamlit-knop en géén <a href>: een echte link herlaadt de pagina, waardoor
    Streamlit een nieuwe sessie start. De coach zou dan uitgelogd worden en z'n analyses
    kwijtraken bij een klik op het logo. De knop wordt via CSS (.st-key-logo_home) omgetoverd
    tot de logo-lockup, zodat het er gewoon als het logo uitziet."""
    data_uri = _logo_data_uri()
    if data_uri:
        st.markdown(f'<img src="{data_uri}" style="height:40px;" />', unsafe_allow_html=True)

    if clickable:
        if st.button('De Musculatuur', key='logo_home', help='Terug naar alle tools',
                     use_container_width=True):
            goto(PAGE_HOME)
    else:
        st.markdown('<div class="dm-logo-static">De Musculatuur</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="dm-logo-tagline">{tagline}</div>', unsafe_allow_html=True)


def render_hero(subtitle, desc):
    """Groot, premium hero-blok met logo — bovenaan de login-pagina en het dashboard."""
    data_uri = _logo_data_uri()
    mark_html = f'<img src="{data_uri}" class="dm-hero-logo-img" />' if data_uri else '<div class="dm-hero-mark">M</div>'
    st.markdown(f"""
    <div class="dm-hero">
      {mark_html}
      <div class="dm-hero-name">De Musculatuur</div>
      <div class="dm-hero-tagline">Recovery &amp; Performance</div>
      <div class="dm-hero-sub">{subtitle}</div>
      <div class="dm-hero-desc">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


def md_bold_to_html(text):
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)


# ---------------------------------------------------------------------------
# Navigatie: welkomstpagina met tool-tegels, daarachter de losse tools.
# Bewust eigen routing via session_state i.p.v. Streamlit's multipage-mechanisme:
# dat laatste zet z'n eigen paginanavigatie in de sidebar, wat botst met de
# huisstijl-sidebar hieronder.
# ---------------------------------------------------------------------------
PAGE_HOME = 'home'
PAGE_BELASTBAARHEID = 'belastbaarheid'
PAGE_JAARPLANNING = 'jaarplanning'
PAGE_VOEDING = 'voeding'
PAGE_LACTAAT = 'lactaat'

TOOLS = [
    {'key': PAGE_BELASTBAARHEID, 'icon': '📊', 'titel': 'Belastbaarheidsanalyse atleet',
     'desc': 'Volledige analyse van trainingslast en A:C ratio uit een Strava-export: '
             'kernbevindingen, blinde vlekken, trend en trainingsadvies.', 'klaar': True},
    {'key': PAGE_JAARPLANNING, 'icon': '🎯', 'titel': 'Jaarplanning',
     'desc': 'Macro- en mesocyclus-voorstel per A-doel volgens Friel en Olbrecht, '
             'terugwerkend vanaf de wedstrijddatum en afgestemd op de huidige belastbaarheid.',
     'klaar': True},
    {'key': PAGE_VOEDING, 'icon': '🥗', 'titel': 'Voedingsplan',
     'desc': 'Voedingsadvies afgestemd op trainingsbelasting en wedstrijdplanning.', 'klaar': False},
    {'key': PAGE_LACTAAT, 'icon': '🧪', 'titel': 'Lactaattest',
     'desc': 'Verwerking van lactaatmetingen naar drempels en trainingszones.', 'klaar': False},
]


def goto(page):
    st.session_state['page'] = page
    st.rerun()


def current_page():
    return st.session_state.get('page', PAGE_HOME)


def render_home():
    st.markdown('<div class="dm-page-title">Kies een tool</div>', unsafe_allow_html=True)
    st.caption('Elke tool werkt op zichzelf — je hoeft ze niet in volgorde te gebruiken.')
    st.markdown('<div style="height:0.8rem"></div>', unsafe_allow_html=True)

    for row_start in range(0, len(TOOLS), 2):
        cols = st.columns(2, gap='medium')
        for col, tool in zip(cols, TOOLS[row_start:row_start + 2]):
            with col:
                badge = '' if tool['klaar'] else '<div class="dm-tool-badge">In ontwikkeling</div>'
                st.markdown(f"""
                <div class="dm-tool-card{'' if tool['klaar'] else ' soon'}">
                  <div class="dm-tool-icon">{tool['icon']}</div>
                  <div class="dm-tool-title">{tool['titel']}</div>
                  <div class="dm-tool-desc">{tool['desc']}</div>
                  {badge}
                </div>
                """, unsafe_allow_html=True)
                if st.button('Openen' if tool['klaar'] else 'Binnenkort beschikbaar',
                             key=f"open_{tool['key']}", disabled=not tool['klaar'],
                             use_container_width=True):
                    goto(tool['key'])
        st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)


def render_placeholder_page(icon, titel, desc):
    st.markdown(f'<div class="dm-page-title">{icon} {titel}</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="dm-empty-state">
      <div class="dm-empty-icon">🚧</div>
      <div class="dm-empty-title">Deze tool wordt nog gebouwd</div>
      <div class="dm-empty-desc">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


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
    render_hero('Coach login', 'Interne tool voor coaches — voer het gedeelde wachtwoord in om verder te gaan.')
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

    DM_MAROON, DM_GREEN, DM_PEACH = '#5B1F2C', '#6FA98A', '#F0D7B7'

    # Bewust Figure() i.p.v. plt.subplots(): pyplot houdt elke aangemaakte figuur bij in een
    # globale registry die pas leegloopt bij plt.close(). In een langdraaiende Streamlit-app
    # stapelen die figuren zich op over alle sessies heen, tot het geheugen vol zit en de app
    # omvalt (opnieuw een lege pagina voor de coach). Een losse Figure komt daar nooit in.
    fig = Figure(figsize=(9, 4.0))
    ax1 = fig.subplots()
    fig.patch.set_facecolor('#FBF6F2')
    ax1.set_facecolor('#FBF6F2')
    ax1.bar(w.index, w.values, width=0.9, color=DM_PEACH, edgecolor=DM_MAROON, linewidth=0.3,
            label='Wekelijkse trainingslast (7d som)')
    ax1.set_ylabel('Trainingslast (7d som)', color=DM_MAROON)
    ax1.tick_params(axis='y', labelcolor=DM_MAROON)
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
    for spine in ax1.spines.values():
        spine.set_visible(False)

    ax2 = ax1.twinx()
    ax2.plot(d_acwr.index, d_acwr.values, color=DM_MAROON, linewidth=2.2, label='A:C ratio')
    ax2.axhspan(0.8, 1.3, color=DM_GREEN, alpha=0.18)
    ax2.axhline(1.5, color=DM_MAROON, linestyle='--', linewidth=1, alpha=0.5)
    ax2.axhline(0.8, color='#9c8b7f', linestyle=':', linewidth=1, alpha=0.6)
    ax2.set_ylabel('A:C ratio', color=DM_MAROON)
    ax2.tick_params(axis='y', labelcolor=DM_MAROON)
    ax2.set_ylim(0, max(1.8, float(np.nanmax(d_acwr.values)) * 1.15 if len(d_acwr) else 1.8))
    for spine in ax2.spines.values():
        spine.set_visible(False)
    fig.suptitle(f'Belastbaarheid laatste 6 maanden — {athlete}', fontweight='bold', color=DM_MAROON,
                 fontfamily='serif', fontsize=13)
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


def render_jaarplanning(plan):
    """Toont de voorgestelde macro/mesocyclus-structuur per A-doel (kaarten, kleurgecodeerd per fase)."""
    if not plan['goals']:
        st.caption('Nog geen A-doelen ingesteld. Voeg er hierboven toe om een voorgestelde jaarplanning te zien.')
        return

    blocks_by_goal = {}
    for b in plan['blocks']:
        blocks_by_goal.setdefault(b['doel'], []).append(b)

    for g in plan['goals']:
        st.markdown(f"##### {g['name']} · {g['discipline']} — {pd.Timestamp(g['date']).strftime('%d %B %Y')}")
        if g['warning']:
            st.warning(g['warning'])
        st.caption(f"{g['weken_beschikbaar']} weken beschikbaar voor dit blok, terugwerkend gepland vanaf de wedstrijdweek.")

        rows_html = ''
        for b in blocks_by_goal.get(g['name'], []):
            note_html = f'<div class="dm-plan-note">💡 {b["notitie"]}</div>' if b['notitie'] else ''
            dates_txt = f'{b["start"].strftime("%d %b")} – {b["einde"].strftime("%d %b %Y")} ({b["weken"]} w.)'
            rows_html += (
                f'<div class="dm-plan-block dm-plan-{b["fase_key"]}">'
                f'<div class="dm-plan-header">'
                f'<span class="dm-plan-fase">{b["fase"]}</span>'
                f'<span class="dm-plan-dates">{dates_txt}</span>'
                f'</div>'
                f'<div class="dm-plan-meta">Volume: {b["volume"]} &nbsp;·&nbsp; Intensiteit: {b["intensiteit"]}</div>'
                f'<div class="dm-plan-focus">{b["focus"]}</div>'
                f'{note_html}'
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


def render_dashboard(athlete_name):
    data = st.session_state['athletes'][athlete_name]
    summary, fig = data['summary'], data['fig']

    items_html = ''.join(f'<li>{md_bold_to_html(item)}</li>' for item in kernbevindingen(summary))
    st.markdown(f"""
    <div class="dm-card">
      <div class="dm-card-title">📋 Kernbevindingen — {athlete_name}</div>
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
          <div class="dm-card-title">🎯 Trainingsadvies — komende weken</div>
          {advies_html}
        </div>
        """, unsafe_allow_html=True)
        st.caption('AI-gegenereerd advies op basis van trainingsdata (ACWR-stand, -trend en consistentie) — '
                   'geen diagnose en geen automatische inplanning. De coach combineert dit met eigen inzicht '
                   '(klachten, context, doelen) en beslist het uiteindelijke programma.')

    st.divider()
    st.subheader('📊 Activiteitenoverzicht')
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
                return ['font-weight:700; background-color:#F2E6DE; color:#5B1F2C;' if is_total else '' for _ in row]

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
    st.subheader('⚖️ Belastbaarheid: A:C ratio')
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
            'Sweet spot': 'background-color:#E3F3EA; color:#2f6b4f; font-weight:600;',
            'Piekbelasting': 'background-color:#FBE7E2; color:#a13a2a; font-weight:600;',
            'Onderbelasting': 'background-color:#FDF3E0; color:#8a6a1f; font-weight:600;',
        }
        return colors.get(val, '')

    styled_acwr = acwr_df.style.map(style_zone, subset=['Zone']).format({'A:C ratio': '{:.1f}'}, na_rep='–')
    st.dataframe(styled_acwr, hide_index=True, use_container_width=True)

    st.divider()
    st.info(f'Wil je hieruit een jaarplanning opbouwen? Open de **Jaarplanning**-tool — die neemt de '
            f'belastbaarheid van {athlete_name} automatisch mee als startpunt.', icon='🎯')
    if st.button('Naar Jaarplanning', key='naar_jaarplanning', use_container_width=True):
        st.session_state['jp_athlete'] = athlete_name
        # Zet meteen de juiste bron klaar, anders landt de coach op een upload-scherm
        # terwijl de analyse van deze atleet er al is.
        st.session_state['jp_bron'] = JP_BRON_ANALYSE
        st.session_state['jp_pick'] = athlete_name
        goto(PAGE_JAARPLANNING)

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
        return {
            'current': full['summary']['acwr']['current'],
            'sessies': full['summary']['totalSessionsAllTime'],
            'dateRange': full['summary']['dateRange'],
            'bron': 'eerdere analyse',
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


def render_jaarplanning_page():
    st.markdown('<div class="dm-page-title">🎯 Jaarplanning</div>', unsafe_allow_html=True)
    st.caption('Macro/mesocyclus-voorstel per A-doel volgens Friel en Olbrecht, terugwerkend gepland '
               'vanaf elke wedstrijddatum. De coach vertaalt dit naar concrete sessies.')

    # --- Stap 1: belastbaarheid als cijfermatige basis -----------------------
    st.markdown('##### ① Belastbaarheid als basis')
    st.caption('Enkel de A:C ratio wordt hier gebruikt, als startpunt voor de eerste cyclus — voor de '
               'volledige analyse (blinde vlekken, trend, advies) gebruik je de Belastbaarheidsanalyse-tool. '
               'Zonder belastbaarheidscijfer werkt de planning ook, maar dan zonder aanpassing aan de '
               'actuele belasting.')

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

    # --- Stap 2: A-doelen ---------------------------------------------------
    st.divider()
    st.markdown('##### ② A-doelen')
    st.caption('Max. 3 A-doelen per jaar.')

    goals_key = f'a_goals_{athlete_name}'
    if goals_key not in st.session_state:
        st.session_state[goals_key] = []
    goals = st.session_state[goals_key]

    if goals:
        chips = ''.join(
            f'<span class="dm-goal-chip">🏁 {g["name"]} — {pd.Timestamp(g["date"]).strftime("%d %b %Y")}</span>'
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
                        st.rerun()
        else:
            st.caption('Maximum van 3 A-doelen bereikt. Verwijder een doel om een ander toe te voegen.')

        for i, g in enumerate(goals):
            gc1, gc2 = st.columns([4, 1])
            with gc1:
                st.markdown(f"**{g['name']}** — {g['discipline']} — {pd.Timestamp(g['date']).strftime('%d %B %Y')}")
            with gc2:
                if st.button('Verwijder', key=f'del_goal_{athlete_name}_{i}', use_container_width=True):
                    goals.pop(i)
                    st.session_state[goals_key] = goals
                    st.rerun()

    # --- Stap 3: het plan ---------------------------------------------------
    if goals:
        st.divider()
        st.markdown('##### ③ Voorgestelde planning')
        today_ref = pd.Timestamp(ref_date)
        acwr_current = bel['current'] if bel else None
        plan = core.generate_jaarplanning(today_ref, goals, acwr_current)
        render_jaarplanning(plan)
    else:
        st.caption('Nog geen A-doelen ingesteld. Voeg er hierboven toe om een voorgestelde jaarplanning te zien.')


def render_analyse_sidebar():
    """Upload-flow: hoort enkel bij de Belastbaarheidsanalyse-tool."""
    st.markdown('<div class="dm-sidebar-section">Nieuwe analyse</div>', unsafe_allow_html=True)

    st.markdown('<div class="dm-step">① Naam atleet</div>', unsafe_allow_html=True)
    athlete_name = st.text_input('Naam atleet', placeholder='bv. Jan Peeters', label_visibility='collapsed')

    st.markdown('<div class="dm-step">② Upload activities.csv</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader('activities.csv', type=['csv'], label_visibility='collapsed')
    st.caption('Pak de Strava-export (.zip) uit en upload enkel het bestand **activities.csv** '
               'daaruit — niet de volledige zip. Dat is het enige bestand dat deze tool nodig heeft.')

    st.markdown('<div class="dm-step">③ Referentiedatum</div>', unsafe_allow_html=True)
    today_override = st.date_input('Referentiedatum', value=pd.Timestamp.now().normalize().date(),
                                    label_visibility='collapsed')

    st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)
    if st.button('Analyseer', type='primary', disabled=not (athlete_name and uploaded_file), use_container_width=True):
        with st.spinner('Bezig met analyseren...'):
            analyze_and_store(uploaded_file, athlete_name, pd.Timestamp(today_override))
        st.success(f'Analyse van {athlete_name} klaar.')

    athletes = list(st.session_state.get('athletes', {}).keys())
    if athletes:
        st.markdown('<hr class="dm-sidebar-divider" />', unsafe_allow_html=True)
        st.markdown('<div class="dm-sidebar-section">Geanalyseerde atleten</div>', unsafe_allow_html=True)
        active = st.radio('Bekijk:', athletes, index=athletes.index(st.session_state.get('active_athlete', athletes[0])),
                           label_visibility='collapsed')
        st.session_state['active_athlete'] = active


def render_belastbaarheid_page():
    active = st.session_state.get('active_athlete')
    if not active:
        st.markdown("""
        <div class="dm-empty-state">
          <div class="dm-empty-icon">📤</div>
          <div class="dm-empty-title">Nog geen analyse</div>
          <div class="dm-empty-desc">Vul links de naam van de atleet in en upload het <strong>activities.csv</strong>-bestand
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

    if page == PAGE_HOME:
        render_hero('AI Performance Assistent',
                    'De tools van De Musculatuur, op één plek — per atleet, in seconden.')

    with st.sidebar:
        # Op de startpagina hoeft het logo nergens heen te leiden; elders is het de weg terug.
        render_logo(clickable=page != PAGE_HOME)
        # Enkel de Belastbaarheidsanalyse heeft eigen sidebar-bediening; op de andere
        # pagina's zou een extra scheidingslijn een leeg blok afbakenen.
        heeft_eigen_sidebar = page == PAGE_BELASTBAARHEID
        if page != PAGE_HOME:
            if st.button('← Alle tools', key='terug_home', use_container_width=True):
                goto(PAGE_HOME)
            if heeft_eigen_sidebar:
                st.markdown('<hr class="dm-sidebar-divider" />', unsafe_allow_html=True)

        if heeft_eigen_sidebar:
            render_analyse_sidebar()
        elif page == PAGE_HOME:
            st.caption('Kies rechts een tool om te starten.')

        st.markdown('<hr class="dm-sidebar-divider" />', unsafe_allow_html=True)
        if st.button('Uitloggen', use_container_width=True):
            st.session_state['authed'] = False
            st.rerun()

    if page == PAGE_BELASTBAARHEID:
        render_belastbaarheid_page()
    elif page == PAGE_JAARPLANNING:
        render_jaarplanning_page()
    elif page == PAGE_VOEDING:
        render_placeholder_page('🥗', 'Voedingsplan',
                                 'Voedingsadvies afgestemd op trainingsbelasting en wedstrijdplanning. '
                                 'Deze tool bouwen we in een volgende stap.')
    elif page == PAGE_LACTAAT:
        render_placeholder_page('🧪', 'Lactaattest',
                                 'Verwerking van lactaatmetingen naar drempels en trainingszones. '
                                 'Deze tool bouwen we in een volgende stap.')
    else:
        render_home()


if __name__ == '__main__':
    main()
