# Workload & A:C ratio tool — v1

Automatiseert de handmatige trainingsanalyse (zoals eerder voor Wout gedaan) voor **eender welke atleet** met een Strava-export. Twee manieren om de tool te gebruiken — zelfde reken-logica (`core.py`), ander jasje:

## Installatie op een nieuwe pc

1. Pak deze map (`tool/`) volledig uit ergens op de nieuwe pc (Bureaublad, Documenten, ...) — alle bestanden moeten samen in dezelfde map blijven staan.
2. Zorg dat **Python 3** geïnstalleerd is. Niet aanwezig? Download via [python.org/downloads](https://www.python.org/downloads/) — vink bij installatie **"Add python.exe to PATH"** aan.
3. Dubbelklik op **`DMT.bat`**. De eerste keer installeert die automatisch alle benodigdheden (`requirements.txt`) — dat duurt even, daarna opent de tool in de browser.
4. (Optioneel) Sleep `DMT.bat` naar het Bureaublad met rechtermuisknop → **"Verzenden naar" → "Bureaublad (snelkoppeling maken)"** voor een vast icoon.

Geen internetverbinding nodig om de tool te gebruiken, wel om de eerste keer de Python-packages te installeren (stap 3).

## Optie A — Website (app.py, aanbevolen voor coaches)

```bash
pip install streamlit pandas numpy matplotlib --break-system-packages   # eenmalig
streamlit run app.py
```

Opent een lokale website (standaard op http://localhost:8501) met:
- Gedeeld wachtwoord voor alle coaches (standaard `musculatuur2026` — **wijzig dit** via omgevingsvariabele `DEMUSCULATUUR_PASSWORD` of `.streamlit/secrets.toml`, key `APP_PASSWORD`)
- Upload-knop voor **enkel `activities.csv`** (bewust geen volledige .zip — die is bij jarenlange geschiedenis al snel 500MB-1GB+ door foto's/video's/losse bestanden die de tool toch niet gebruikt; `activities.csv` alleen blijft meestal een paar honderd KB) + naam atleet → automatisch dashboard (kernbevindingen, tabellen, A:C-grafiek)
- Pak de Strava-export dus eerst even uit en stuur enkel `activities.csv` door/upload die
- Meerdere atleten per sessie, wisselen via het zijmenu
- Download-knop voor de ruwe cijfers (JSON)

Na de login kom je op een **welkomstpagina met vier tegels**:

| Tegel | Wat het is | Waar de code zit |
|---|---|---|
| 📊 Belastbaarheidsanalyse atleet | Trainingslast + A:C ratio uit een Strava-export | `app.py` + `core.py` |
| 🎯 Jaarplanning | Macro/mesocyclus per A-doel (Friel/Olbrecht) | `app.py` + `core.py` |
| 🧪 Prestatietesten | Lactaattest, Critical Power, Critical Swim Speed, 3/5 km looptest | `static/prestatietest.html` |
| 🥗 Voedingsplan | Wedstrijdvoeding per minuut (ACSM-richtwaarden) | `static/prestatietest.html#voeding` |

De laatste twee zijn **één zelfstandig HTML-bestand** (geen Python, geen dependencies) dat Streamlit
enkel uitlevert via `enableStaticServing`. Ze openen in een nieuw tabblad, zodat je Streamlit-sessie
(login en gemaakte analyses) blijft staan. Bewust géén iframe: alleen in een volwaardig venster
werken de printbare atleet-verslagen (A4) en de deep-links naar een specifiek onderdeel.

Formules en codestructuur van die suite staan in `docs/FORMULES.md` en
`docs/ARCHITECTUUR-prestatietest.md`.

> **Let op bij de prestatietest-suite:** static-bestanden vallen **buiten** het wachtwoordscherm —
> wie de directe URL kent, kan de suite openen. Dat is een bewuste afweging: de suite bewaart zelf
> geen atleetdata (projecten gaan via JSON-export naar je eigen schijf). Zet er ook **nooit** een
> Anthropic API-sleutel in de code: de foto-analyse vraagt die bij gebruik aan de coach zelf en
> houdt ze enkel in het browsergeheugen.

**Dit draait vandaag alleen lokaal** (op jouw computer of een server die jij aanzet) — zie "Hosting" onderaan voor hoe dit een echt gedeelde link wordt.

**Huisstijl:** de tool gebruikt de kleuren en fonts van demusculatuur.be (crème/perzik, bordeaux serif koppen, saliegroene knoppen, donkerbruine sidebar). Het logo is een benaderde tekst-versie ("M" + wordmark) omdat ik het echte logobestand niet kon ophalen. Zet een `logo.png` (transparante achtergrond, bv. 300-400px breed) in deze map — de header pikt 'm automatisch op in plaats van de tekstversie, geen codewijziging nodig.

## Optie B — Command line + Word-rapport (voor een archiveerbaar document)

```bash
pip install pandas numpy matplotlib --break-system-packages   # eenmalig
npm install -g docx                                            # eenmalig

python3 analyze_athlete.py --export /pad/naar/export.zip --athlete "Naam Atleet" --output ./out
node build_report.js --dir ./out
```

Resultaat in `./out/`:
- `summary.json` — alle cijfers
- `acwr_chart.png` — grafiek
- `Trainingsanalyse_<Naam>.docx` — het rapport, klaar om te delen (bv. met een atleet)

## Hosting — van lokaal naar een echte gedeelde link

`app.py` is een volwaardige webapp, maar draait nu alleen waar jij hem start. Om alle coaches via 1 link toegang te geven, moet hij ergens 24/7 blijven draaien. Snelste opties, geen eigen server nodig:
1. **Streamlit Community Cloud** (gratis) — code op GitHub zetten, koppelen op share.streamlit.io, klaar. Eenvoudigste pad.
2. **Render.com / Railway** (gratis tot goedkope tier) — iets meer controle, ook GitHub-gekoppeld.
3. **Eigen server bij De Musculatuur** — als die er is/komt, kan de app daar ook gewoon draaien.

Dit vraagt een account (GitHub + hostingdienst) langs jullie kant — dat kan ik niet voor jullie aanmaken, maar ik help je er wel stap voor stap doorheen zodra je een keuze maakt.

## Hoe kom je aan een Strava-export?

Atleet vraagt via Strava: Instellingen → Mijn account → "Download of verwijder je account" → "Download aanvraag" (Bulk Export). Ze krijgen een e-mail met een .zip-bestand — dat is het bestand voor `--export`.

## Wat het rapport bevat

- Automatisch gedetecteerde kernbevindingen (A:C ratio-status, sweet spot-weken, en "blinde vlekken": sporten die historisch actief waren maar recent volledig afwezig zijn)
- **Trainingsadvies voor de komende weken**: regelgebaseerd advies afgeleid uit de ACWR-stand, de trend van de laatste weken en de consistentie (te veel pieken/dalen) — bv. "bouw af", "stabiliseer" of "ruimte om op te bouwen (+5-10%/week)", plus advies bij het heropstarten van een sport na een blinde vlek.
- **A-doelen & jaarplanning**: voeg tot 3 A-doelen per atleet toe (naam, datum, discipline). De tool bouwt daaruit een voorgestelde macro/mesocyclus-structuur, terugwerkend vanaf elke wedstrijddatum, volgens de periodiseringsprincipes van Joe Friel (Basis → Opbouw → Piek → Taper, 3:1-belastingsritme) en Jan Olbrecht (aerobe capaciteit eerst en langst opgebouwd, drempel-/anaerobe prikkels pas laat en gericht). De taper is vast: 2 weken, week -2 op 60% volume, wedstrijdweek op 40% volume met behoud van intensiteit. Het startpunt van de eerste cyclus wordt aangepast aan de huidige belastbaarheid (bv. een stabilisatieweek bij een te hoge ACWR, of extra basisopbouw bij onderbelasting). Doelen worden per sessie bijgehouden (niet opgeslagen na herstart) — dit is een voorstel op macro/mesocyclus-niveau, geen dag-per-dag schema; de coach vertaalt dit naar concrete sessies.

  **Bewuste afwijking van Friel — de volumepiek.** Bij Friel is *Peak* een blok met láág volume
  en hoge intensiteit; het volume piekt daar al in de late basisperiode. Op vraag van de coach
  ligt de volumepiek in deze tool in het **Piekblok** zelf: het volume loopt op tot ~100-110%
  vlak vóór de taper, waarna de taper die belasting omzet in vorm. De volledige volumeladder
  staat in `FASE_INFO` (`core.py`), met een numeriek `volume_pct` per fase dat de balk in de UI
  voedt.

  **Actiepunten per cyclus van 4 weken.** Elk blok wordt opgesplitst in cycli van 3 opbouwweken
  + 1 hersteldweek, en elke cyclus krijgt concrete actiepunten die uit de trainingsanalyse
  volgen. De planning krijgt daarvoor het **sportprofiel van de laatste 3 maanden** mee
  (sessies/week en aandeel in de trainingslast per sport) plus de blinde vlekken. Een triatleet
  die 0,5x per week zwemt krijgt in de basis een techniek- en frequentiefocus op zwemmen die
  over de blokken heen oploopt (1x → 2x → 3x); disciplines die op niveau staan krijgen expliciet
  "aanhouden, hier geen extra volume". Alle drempels en sportvereisten staan bij elkaar in
  `DISCIPLINE_SPORTEN`, `TECHNIEKSPORTEN` en `FOCUS_DREMPELS` (`core.py`), zodat een coach ze
  kan bijstellen zonder de planningslogica aan te raken.
- Activiteitenoverzicht per sport voor 2 jaar / 1 jaar / 6 maanden / 3 maanden / 4 weken / 1 week
- A:C ratio-grafiek en 16-weken trendtabel
- Methodologie & datakwaliteit (transparant over geschatte vs. geregistreerde trainingslast)

## Wat het (bewust) NIET doet — zie PRD

- Geen automatische jaarplanning/periodisering — het trainingsadvies is een richtlijn voor de komende 1-2 weken, geen volledig trainingsschema. De coach vertaalt dit naar concrete sessies.
- Geen live Strava-koppeling — nog steeds een export nodig per atleet.
- Geen personalisatie per coach-filosofie — volgende fase (zie literatuurstudie, hoofdstuk 8).

## Bekende beperkingen

- Trainingslast is exact voor sessies waar Strava's "Trainingsbelasting" beschikbaar is; voor andere sessies (bv. veel krachttraining) wordt geschat op basis van hartslag × duur. Bij weinig hartslagdata is de schatting minder betrouwbaar.
- Indoor en outdoor fietsen worden als 1 sport ("Fietsen") gerapporteerd — bewuste keuze, geen onderscheid nodig voor performance-coaching.
- "Blinde vlekken" zijn een automatisch signaal, geen diagnose — niet elke gedetecteerde gap is relevant (bv. een sport die de atleet gewoon bewust liet vallen). Coach-interpretatie blijft nodig — precies de filosofie uit de literatuurstudie: AI ondersteunt, coach beslist.
- Het trainingsadvies is regelgebaseerd (geen machine learning) en steunt puur op trainingslast/ACWR — het houdt geen rekening met klachten, HRV, slaap, levensfase of wedstrijdplanning. Zie het als een startpunt voor het coach-gesprek, niet als eindoordeel.

## Volgende stappen (P1/P2 — zie PRD)

1. Testen op 2-3 andere atleten-exports.
2. Overwegen: automatische flag wanneer A:C ratio 2+ weken buiten 0,8–1,3 valt.
3. Fase 2: coach-kennis-eliciëring (ACTA-interviews) om trainingsfilosofie te vangen — zie literatuurstudie hoofdstuk 8.
