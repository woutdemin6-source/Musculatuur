"""
De Musculatuur — gedeelde huisstijl (design tokens) voor ALLE tools.

Eén bron van waarheid voor kleuren, typografie en vormtaal, gebruikt door:
  - app.py                  (Streamlit-shell + tools)
  - intake.py               (intakeverslag, HTML)
  - static/prestatietest.html (zelfstandige HTML-suite — die kan geen Python importeren,
                              dus daar staan dezelfde waarden in het :root-blok; pas ze daar
                              mee aan als je hier iets wijzigt)

Basis = demusculatuur.be (live uitgelezen): lettertype Satoshi, crème achtergrond,
warm donkerbruin voor tekst, wijnrood voor koppen, saliegroen als actiekleur, pil-knoppen.
Premium-vertaling: lichter canvas, veel witruimte, haarfijne lijnen i.p.v. zware randen,
zachte warme schaduwen, één lettertype in verschillende gewichten, geen emoji/gradient-blobs.
"""

# --- Kleuren (website-waarden, licht verfijnd) --------------------------------
BG = '#F8F3F0'          # canvas — lichtere versie van de site-crème (#EEE2DF)
SURFACE = '#FFFFFF'     # kaarten
SURFACE_2 = '#F3EBE6'   # subtiele vlakken (tabelkop, invoervelden)
SAND = '#EED7C5'        # perzik/zand van de site — accentvlakken
LINE = '#ECE1DA'        # haarlijn
LINE_STRONG = '#D8BFAF' # zand-rand van de site
INK = '#211408'         # diepste tekst (site: bodytekst)
TEXT = '#3D2E29'        # standaard tekst (site: footer-bruin)
BROWN = '#6B3B2A'       # secundair warm bruin (site: bodykleur)
MUTED = '#8C766A'       # rustige, warme grijstint voor meta-tekst
WINE = '#4F000B'        # koppen / merk-accent (site: nav en h2)
GREEN = '#63B995'       # actiekleur (site: knoppen)
GREEN_DARK = '#4E9F7E'  # hover
GREEN_SOFT = '#E7F4EE'

# Statuskleuren — gedempt, passend bij het warme palet
OK, OK_SOFT = '#2F7A5B', '#E7F4EE'
WARN, WARN_SOFT = '#9A6A14', '#FBF1DD'
ALERT, ALERT_SOFT = '#A3362A', '#FBE9E5'
INFO, INFO_SOFT = '#6B5A52', '#F3EDEA'

# --- Typografie & vorm --------------------------------------------------------
FONT_URL = 'https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700,900&display=swap'
FONT = "'Satoshi', 'Helvetica Neue', Arial, sans-serif"
RADIUS = '18px'
RADIUS_SM = '12px'
SHADOW = '0 1px 2px rgba(33,20,8,.04), 0 10px 30px -14px rgba(33,20,8,.12)'
SHADOW_HOVER = '0 2px 4px rgba(33,20,8,.05), 0 18px 40px -16px rgba(33,20,8,.18)'

# CSS-variabelen, identiek in elke tool
CSS_VARS = f""":root{{
  --bg:{BG}; --surface:{SURFACE}; --surface-2:{SURFACE_2}; --sand:{SAND};
  --line:{LINE}; --line-strong:{LINE_STRONG};
  --ink:{INK}; --text:{TEXT}; --brown:{BROWN}; --muted:{MUTED}; --faint:#B4A399;
  --wine:{WINE}; --accent:{WINE}; --accent-ink:#3A0008; --graphite:{TEXT};
  --green:{GREEN}; --green-dark:{GREEN_DARK}; --green-soft:{GREEN_SOFT};
  --ok:{OK}; --warn:{WARN}; --alert:{ALERT};
  --radius:{RADIUS}; --radius-sm:{RADIUS_SM};
  --shadow:{SHADOW}; --shadow-hover:{SHADOW_HOVER};
  --font:{FONT}; --body:{FONT}; --disp:{FONT};
  --mono:{FONT};
}}"""
