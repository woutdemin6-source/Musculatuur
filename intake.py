"""
Intake-tool: opname van het intakegesprek → transcript → ingevuld verslag in de huisstijl.

Drie stappen, elk apart bruikbaar:
  1. transcribeer()   audio (m4a/mp3/wav/…) → tekst, via de OpenAI-transcriptie-API.
                      De opname wordt eerst met ffmpeg verkleind en in stukken van tien
                      minuten geknipt (limiet van de API is 25 MB per bestand).
  2. extraheer()      transcript → de velden van het intakeverslag (JSON), via een GPT-model.
  3. verslag_html()   velden → zelfstandig HTML-verslag, zelfde opbouw en stijl als het
                      lactaatrapport uit de prestatietest-suite (voorblad, genummerde
                      secties, kaarten, adviesblok, voettekst) — printbaar als A4-PDF.

Privacy: de audio en het transcript blijven enkel in het geheugen tijdens de verwerking en
worden nergens bewaard; alleen het verslag (de velden + de HTML) gaat naar het atleetprofiel.
"""
import base64
import html as _html
import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import streamlit as st

MODEL_TEKST_STANDAARD = 'gpt-5'
MODEL_AUDIO_STANDAARD = 'gpt-4o-transcribe'
SEGMENT_SECONDEN = 600          # 10 min per stuk: ruim onder de 25 MB én de duurlimiet van de API
AUDIO_TYPES = ['m4a', 'mp3', 'wav', 'mp4', 'aac', 'ogg', 'webm', 'flac', 'mpeg', 'mpga']

COACH_STANDAARD = {'naam': 'Wout Demin', 'email': 'woutdemin6@gmail.com', 'gsm': '0491 50 77 22'}

PAKKETTEN = [
    {'key': 'lopen_fietsen', 'naam': 'Lopen / Fietsen', 'prijs': '€75 / maand',
     'punten': ['Tweewekelijks trainingsschema op maat', 'Gebruik van Coachbox of TrainingPeaks',
                'Toegang tot De Musculatuur-evenementen']},
    {'key': 'multisport', 'naam': 'Multisport', 'prijs': '€100 / maand',
     'punten': ['Wekelijks gepersonaliseerd trainingsschema', 'Individuele opvolging',
                'Gebruik van Coachbox of TrainingPeaks', 'Toegang tot evenementen']},
    {'key': 'system_complete', 'naam': 'System Complete', 'prijs': '€140 / maand',
     'punten': ['Volledige begeleiding met wekelijkse schema\'s', 'Maandelijkse sportmassage',
                '1 sessie per maand in het recovery circuit', 'Gebruik van Coachbox of TrainingPeaks',
                'Toegang tot alle evenementen']},
]
PAKKET_LABELS = {p['key']: f"{p['naam']} — {p['prijs']}" for p in PAKKETTEN}

# Vaste teksten uit het intake-sjabloon van De Musculatuur (staan in elk verslag).
IN_PAKKET = [
    ('Gepersonaliseerd wekelijks trainingsschema', 'via TrainingPeaks, volledig afgestemd op jouw doelen en niveau.'),
    ('Feedback en bijsturing', 'actieve analyse en aanpassing van je schema op basis van uitgevoerde trainingen.'),
    ('Data-analyse', 'diepgaande analyse van trainingsdata zoals hartslag, vermogen, RPE en progressie.'),
    ('Tussentijdse evaluatie', 'regelmatige check-ins om de voortgang te bespreken, op vraag van de atleet (telefonisch).'),
    ('Communicatie', 'directe lijn met je coach via TrainingPeaks, telefoon, Teams of WhatsApp.'),
    ('Community', 'toegang tot community-activiteiten en motiverende groepssessies.'),
]
TRAININGPEAKS_INTRO = ('TrainingPeaks is het platform waarmee De Musculatuur samenwerkt om trainingen efficiënt te '
                       'plannen, op te volgen en te analyseren. Het is de centrale hub voor onze coaching.')
TRAININGPEAKS = [
    ('Week- en maandplanning', 'een helder overzicht van jouw persoonlijke schema.'),
    ('Directe feedback', 'commentaar geven en ontvangen bij elke specifieke training.'),
    ('Analyse van belasting', 'inzicht in je trainingsbelasting, fitheid en vermoeidheid om overtraining te voorkomen.'),
    ('Notificaties', 'automatische meldingen bij updates of nieuwe schema\'s.'),
    ('Evolutie-overzicht', 'volg je progressie per week, maand of trainingsblok.'),
]
ZONES_INTRO = ('Om de effectiviteit van je training te maximaliseren, werken we met zeven gestructureerde '
               'trainingszones, gebaseerd op je maximale hartslag (HFmax) en de Rate of Perceived Exertion (RPE). '
               'Na een prestatietest worden ze verfijnd op basis van je eigen drempels.')
ZONES = [
    ('Z1', 'Herstel', 'Zeer rustig tempo, bevordert actief herstel.', '<65% HFmax · RPE 2', '#3B82F6'),
    ('Z2', 'Duur', 'Comfortabel tempo, bouwt de basisuithouding op.', '65–75% HFmax · RPE 3–4', '#22B8CF'),
    ('Z3', 'Tempo', 'Matig intensief, een gecontroleerde en aanhoudende inspanning.', '75–82% HFmax · RPE 5', '#22C55E'),
    ('Z4', 'Drempel', 'Rond het omslagpunt, praten wordt moeilijk.', '83–90% HFmax · RPE 6–7', '#EAB308'),
    ('Z5a', 'VO₂max', 'Zware intervallen, slechts kort vol te houden.', '90–96% HFmax · RPE 8', '#F97316'),
    ('Z5b', 'Anaëroob', 'Maximale inspanning voor zeer korte duur.', '>96% HFmax · RPE 9', '#EF4444'),
    ('Z5c', 'Sprint', 'Maximale sprint.', '100% HFmax · RPE 10', '#B91C1C'),
]
AFSPRAKEN_STANDAARD = {
    'feedback': 'De frequentie van feedback gebeurt op vraag van de atleet; bij vragen contacteer je de coach.',
    'communicatie': 'De primaire communicatie verloopt via de TrainingPeaks-commentaren. Voor dringende zaken is de telefoon beschikbaar.',
    'aanpassingen': 'Aanpassingen aan het trainingsschema worden doorgaans binnen 48 uur na een feedbackmoment doorgevoerd.',
    'verwachtingen': 'Voor een optimale begeleiding verwachten we regelmatige en eerlijke trainingsfeedback, en consistent gebruik van notities om de planning te optimaliseren.',
}

# (sectie, titel, [(veld, label, soort)]) — de volgorde is ook de volgorde in formulier en verslag.
SECTIES = [
    ('algemeen', 'Algemene gegevens', [
        ('naam', 'Naam atleet', 'input'),
        ('geboortejaar', 'Geboortejaar / -datum', 'input'),
        ('sport', 'Sportdiscipline', 'input'),
        ('datum', 'Datum intake', 'input'),
        ('contact', 'Contact atleet (gsm / e-mail)', 'input'),
    ]),
    ('coach', 'Coach', [
        ('naam', 'Coach', 'input'),
        ('email', 'E-mail coach', 'input'),
        ('gsm', 'Gsm coach', 'input'),
    ]),
    ('facturatie', 'Facturatiegegevens', [
        ('naam_bedrijf', 'Naam / bedrijf', 'input'),
        ('adres', 'Adres', 'input'),
        ('postcode_gemeente', 'Postcode / gemeente', 'input'),
        ('email', 'E-mailadres voor facturen', 'input'),
        ('btw', 'BTW-nummer (indien van toepassing)', 'input'),
        ('betaling', 'Voorkeur betalingsmethode', 'input'),
        ('op_naam_van', 'Facturatie op naam van (atleet / ouder / bedrijf)', 'input'),
    ]),
    ('doelen', 'Doelen', [
        ('korte_termijn', 'Korte-termijndoelen', 'area'),
        ('lange_termijn', 'Lange-termijndoelen', 'area'),
        ('wedstrijden', 'Belangrijke wedstrijden / events', 'area'),
    ]),
    ('ervaring', 'Ervaring & aandachtspunten', [
        ('trainingservaring', 'Trainingservaring', 'area'),
        ('testing', 'Testing inplannen', 'area'),
        ('blessures', 'Blessuregeschiedenis / aandachtspunten', 'area'),
        ('beschikbaarheid', 'Beschikbaarheid & context (uren, werk, gezin)', 'area'),
        ('materiaal', 'Materiaal & data (fiets, vermogensmeter, horloge, platformen)', 'area'),
    ]),
    ('afspraken', 'Praktische afspraken', [
        ('feedback', 'Feedbackmomenten', 'area'),
        ('communicatie', 'Communicatie', 'area'),
        ('aanpassingen', 'Aanpassingen schema', 'area'),
        ('verwachtingen', 'Verwachtingen atleet', 'area'),
    ]),
]
LOSSE_VELDEN = ['samenvatting', 'pakket', 'advies', 'volgende_stappen', 'open_vragen']


# ---------------------------------------------------------------------------
# Instellingen
# ---------------------------------------------------------------------------
def _secret(naam, standaard=None):
    try:
        w = st.secrets.get(naam)
    except Exception:
        w = None
    w = (str(w).strip() if w else '') or os.environ.get(naam, '').strip()
    return w or standaard


def openai_sleutel():
    return _secret('OPENAI_API_KEY')


def model_tekst():
    return _secret('OPENAI_MODEL_TEKST', MODEL_TEKST_STANDAARD)


def model_audio():
    return _secret('OPENAI_MODEL_AUDIO', MODEL_AUDIO_STANDAARD)


def _client(api_key):
    from openai import OpenAI
    return OpenAI(api_key=api_key)


def leesbare_fout(e):
    """Vertaal de meest voorkomende API-fouten naar iets waar een coach mee verder kan."""
    naam = type(e).__name__
    tekst = str(e)
    if naam == 'AuthenticationError' or 'Incorrect API key' in tekst:
        return 'De OpenAI-sleutel wordt geweigerd. Controleer OPENAI_API_KEY in de secrets van de app.'
    if 'insufficient_quota' in tekst or naam == 'RateLimitError' and 'quota' in tekst:
        return 'Het OpenAI-account heeft geen tegoed meer. Laad het op via platform.openai.com → Billing.'
    if naam == 'NotFoundError' or 'does not exist' in tekst or 'model_not_found' in tekst:
        return (f'Het gekozen model is niet beschikbaar voor dit account ({tekst}). Zet een ander model in de '
                f'secrets via OPENAI_MODEL_TEKST of OPENAI_MODEL_AUDIO.')
    if naam in ('APIConnectionError', 'APITimeoutError'):
        return 'Geen verbinding met OpenAI. Probeer het zo meteen opnieuw.'
    return f'{naam}: {tekst}'


# ---------------------------------------------------------------------------
# Stap 1 — audio → transcript
# ---------------------------------------------------------------------------
def _ffmpeg():
    """Pad naar ffmpeg: de meegeleverde binary van imageio-ffmpeg (werkt op de Mac én op
    Streamlit Cloud zonder extra installatie), anders een ffmpeg op het systeem."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which('ffmpeg')
        if exe:
            return exe
        raise RuntimeError('ffmpeg ontbreekt: installeer het pakket imageio-ffmpeg (pip) of ffmpeg zelf.')


def _duur_seconden(ffmpeg, pad):
    r = subprocess.run([ffmpeg, '-i', pad], capture_output=True, text=True)
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', r.stderr)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def segmenteer_audio(data, bestandsnaam, werkmap):
    """Schrijft de opname weg, zet ze om naar compacte mono-mp3 en knipt ze in stukken.
    Geeft (duur in seconden, [paden van de stukken]) terug."""
    ffmpeg = _ffmpeg()
    ext = os.path.splitext(bestandsnaam)[1].lower() or '.bin'
    bron = os.path.join(werkmap, f'opname{ext}')
    with open(bron, 'wb') as f:
        f.write(data)
    duur = _duur_seconden(ffmpeg, bron)
    patroon = os.path.join(werkmap, 'deel_%03d.mp3')
    r = subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-i', bron, '-vn', '-ac', '1', '-ar', '16000',
                        '-b:a', '32k', '-f', 'segment', '-segment_time', str(SEGMENT_SECONDEN),
                        '-reset_timestamps', '1', patroon], capture_output=True, text=True)
    delen = sorted(os.path.join(werkmap, n) for n in os.listdir(werkmap) if n.startswith('deel_'))
    if r.returncode != 0 or not delen:
        raise RuntimeError('De opname kon niet gelezen worden — is het een audiobestand (m4a, mp3, wav, …)? '
                           + (r.stderr.strip().splitlines() or [''])[-1])
    return duur, delen


def transcribeer(data, bestandsnaam, api_key, model=None, hint='', voortgang=None):
    """Volledige opname → tekst. `voortgang(bericht)` krijgt tussentijdse statusregels."""
    model = model or model_audio()
    client = _client(api_key)
    melden = voortgang or (lambda s: None)
    with tempfile.TemporaryDirectory() as werkmap:
        duur, delen = segmenteer_audio(data, bestandsnaam, werkmap)
        minuten = f'{duur / 60:.0f} min' if duur else 'onbekende duur'
        melden(f'Opname van {minuten}, verwerkt in {len(delen)} {"deel" if len(delen) == 1 else "delen"}.')

        def een_deel(pad):
            with open(pad, 'rb') as f:
                r = client.audio.transcriptions.create(model=model, file=f, language='nl',
                                                       prompt=hint or None, response_format='json')
            return (r.text or '').strip()

        # Drie delen tegelijk: een uur gesprek is zo in een paar minuten klaar. De voortgang
        # wordt vanuit de hoofdthread gemeld — Streamlit negeert schrijfacties uit werkthreads.
        stukken = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            taken = [pool.submit(een_deel, pad) for pad in delen]
            for i, taak in enumerate(taken):
                stukken.append(taak.result())
                melden(f'Deel {i + 1}/{len(delen)} uitgeschreven.')
    return '\n'.join(stukken).strip()


def transcriptie_hint(atleet_naam='', coach_naam=''):
    """Woordenlijst voor de transcriptie: eigennamen en vakjargon komen zo correct in het transcript."""
    namen = ', '.join(n for n in [atleet_naam, coach_naam] if n)
    return ('Intakegesprek bij De Musculatuur (coaching voor triatlon, lopen, fietsen en zwemmen). '
            f'{"Namen: " + namen + ". " if namen else ""}'
            'Termen: TrainingPeaks, Coachbox, Ironman, halve triatlon, lactaattest, critical power, FTP, '
            'VO2max, zone 2, drempel, Lievegem, Zwift, Garmin, Strava.')


# ---------------------------------------------------------------------------
# Stap 2 — transcript → velden
# ---------------------------------------------------------------------------
def leeg_intake():
    v = {s: {veld: '' for veld, _, _ in velden} for s, _, velden in SECTIES}
    v['algemeen']['datum'] = date.today().strftime('%d/%m/%Y')
    v['coach'] = dict(COACH_STANDAARD)
    v['afspraken'] = dict(AFSPRAKEN_STANDAARD)
    v.update({'samenvatting': '', 'pakket': '', 'advies': '', 'volgende_stappen': [], 'open_vragen': []})
    return v


def _lijst(x):
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    if isinstance(x, str):
        return [r.strip(' -•\t') for r in x.splitlines() if r.strip(' -•\t')]
    return []


def _pakket_key(waarde):
    """'multisport', 'System Complete', '€75' … → de sleutel van het pakket, of ''."""
    s = str(waarde or '').strip().lower()
    if not s:
        return ''
    if s in PAKKET_LABELS:
        return s
    for key, woorden in (('system_complete', ('system', 'complete', '140')),
                         ('multisport', ('multi', '100')),
                         ('lopen_fietsen', ('lopen', 'fiets', '75'))):
        if any(w in s for w in woorden):
            return key
    return ''


def normaliseer(ruw):
    """Maakt van de AI-output (of een oud record) een volledig, veilig velden-dict.
    Onbekende sleutels vallen weg, ontbrekende worden leeg; de vaste afspraken en
    coachgegevens vallen terug op de standaard als de AI ze leeg laat."""
    v = leeg_intake()
    ruw = ruw if isinstance(ruw, dict) else {}
    for s, _, velden in SECTIES:
        blok = ruw.get(s) if isinstance(ruw.get(s), dict) else {}
        for veld, _, _ in velden:
            w = blok.get(veld)
            if w is None or (isinstance(w, str) and not w.strip()):
                continue
            v[s][veld] = str(w).strip() if not isinstance(w, list) else '\n'.join(map(str, w))
    v['samenvatting'] = str(ruw.get('samenvatting') or '').strip()
    v['advies'] = str(ruw.get('advies') or '').strip()
    v['pakket'] = _pakket_key(ruw.get('pakket'))
    v['volgende_stappen'] = _lijst(ruw.get('volgende_stappen'))
    v['open_vragen'] = _lijst(ruw.get('open_vragen'))
    return v


def _schema_voorbeeld():
    v = leeg_intake()
    v['algemeen'].update({'naam': 'Voornaam Achternaam', 'geboortejaar': '1998', 'sport': 'Triatlon',
                          'contact': '04xx xx xx xx, naam@mail.be'})
    v['coach'] = {'naam': '', 'email': '', 'gsm': ''}
    v['facturatie'] = {k: '' for k in v['facturatie']}
    v['doelen'] = {'korte_termijn': '…', 'lange_termijn': '…', 'wedstrijden': '…'}
    v['ervaring'] = {k: '…' for k in v['ervaring']}
    v['afspraken'] = {k: '' for k in v['afspraken']}
    v.update({'samenvatting': '…', 'pakket': 'multisport', 'advies': '…',
              'volgende_stappen': ['…'], 'open_vragen': ['…']})
    return json.dumps(v, ensure_ascii=False, indent=1)


SYSTEEM_PROMPT = """Je bent de assistent van een sportcoach van De Musculatuur (Recovery & Performance): coaching voor triatlon, lopen, fietsen en zwemmen. Je krijgt het transcript van een intakegesprek tussen de coach en een (kandidaat-)atleet. Vul op basis daarvan het intakeverslag in.

Antwoord uitsluitend met één JSON-object met exact deze structuur (zelfde sleutels; waarden zijn strings, behalve de twee lijsten):
%s

Regels:
- Schrijf in het Nederlands (Vlaams), helder en zakelijk maar warm. Over de atleet in de derde persoon of met de voornaam; het veld "advies" richt zich rechtstreeks tot de atleet in de ik/we-vorm van de coach.
- Gebruik enkel wat in het gesprek gezegd is. Verzin niets. Wat niet besproken is, laat je leeg ("").
- "algemeen.datum": enkel invullen als de datum van het gesprek expliciet genoemd wordt, anders leeg laten.
- "algemeen.geboortejaar": geboortejaar of volledige geboortedatum zoals genoemd; een leeftijd mag je omrekenen naar een geboortejaar (vermeld dan "ca.").
- "coach": laat leeg; die gegevens vult de app zelf in.
- "facturatie": enkel wat letterlijk werd doorgegeven.
- "ervaring": trainingservaring (achtergrond, huidige trainingsomvang, niveau, cijfers zoals FTP of tijden), welke testen ingepland worden, blessures en medische aandachtspunten, beschikbaarheid (uren per week, werk, gezin, verlof), materiaal en data (fiets, vermogensmeter, horloge, zwembad, Strava/TrainingPeaks).
- "pakket": een van "lopen_fietsen" (€75), "multisport" (€100), "system_complete" (€140) als er een pakket gekozen of duidelijk besproken werd, anders "".
- "afspraken": enkel invullen als er in het gesprek concrete afspraken gemaakt zijn die afwijken van de standaard (bv. wekelijks telefonisch overleg op maandag); anders leeg laten.
- "samenvatting": 2 tot 4 zinnen: wie de atleet is, waar hij/zij staat, wat het doel is en wat de essentie van de samenwerking wordt.
- "advies": 4 tot 8 zinnen als voorstel voor het "Advies van de coach": de belangrijkste aandachtspunten, de aanpak van de eerste weken/maanden, welke testen eerst en waarom. Concreet en gebaseerd op wat de atleet vertelde.
- "volgende_stappen": 3 tot 7 concrete, afgesproken of logische acties (voor coach én atleet), elk één korte zin.
- "open_vragen": wat de coach nog moet navragen of opvolgen omdat het niet (volledig) aan bod kwam, bv. ontbrekende facturatiegegevens, beschikbaarheid, medische opvolging. Enkel voor de coach, komt niet in het verslag.
"""


def extraheer(transcript, api_key, model=None, atleet_naam='', vandaag=None):
    """Transcript → velden-dict (genormaliseerd). Gooit bij API-fouten de oorspronkelijke fout."""
    model = model or model_tekst()
    client = _client(api_key)
    vandaag = vandaag or date.today().strftime('%d/%m/%Y')
    context = f'Vandaag is {vandaag}. '
    if atleet_naam:
        context += (f'De coach heeft in de app "{atleet_naam}" als actieve atleet geselecteerd — gebruik die '
                    f'naam als het gesprek dat bevestigt, anders de naam uit het gesprek. ')
    bericht = f'{context}\n\nTRANSCRIPT VAN HET INTAKEGESPREK:\n\n{transcript.strip()}'
    r = client.chat.completions.create(
        model=model,
        response_format={'type': 'json_object'},
        messages=[{'role': 'system', 'content': SYSTEEM_PROMPT % _schema_voorbeeld()},
                  {'role': 'user', 'content': bericht}],
    )
    tekst = (r.choices[0].message.content or '').strip()
    try:
        ruw = json.loads(tekst)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', tekst, flags=re.S)
        ruw = json.loads(m.group(0)) if m else {}
    v = normaliseer(ruw)
    if not v['algemeen']['datum']:
        v['algemeen']['datum'] = vandaag
    return v


# ---------------------------------------------------------------------------
# Stap 3 — velden → verslag (HTML, huisstijl van het lactaatrapport)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _logo_uri():
    pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'logo.png')
    if not os.path.exists(pad):
        return ''
    with open(pad, 'rb') as f:
        return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')


def _e(s):
    return _html.escape(str(s or '')).replace('\n', '<br>')


def _of_streep(s):
    return _e(s) if str(s or '').strip() else '—'


VERSLAG_CSS = """
:root{--bg:#FBF6F2;--surface:#fff;--surface-2:#F7F0EA;--ink:#3B2820;--muted:#6E7B99;--faint:#A99A8C;
--line:#EDE2D8;--line-strong:#DCCCBE;--graphite:#3B2820;--accent:#5B1F2C;--accent-ink:#45161F;--green:#6FA98A;
--green-dark:#5C9179;--radius:14px;--shadow:0 2px 10px rgba(59,40,32,.08),0 8px 28px -12px rgba(59,40,32,.14);
--mono:'Space Mono',ui-monospace,monospace;--disp:'Playfair Display',Georgia,serif;--body:'Poppins',system-ui,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);font-size:14px;line-height:1.55;-webkit-font-smoothing:antialiased}
.report{max-width:820px;margin:0 auto;padding:22px 16px 40px}
.toolbar{max-width:820px;margin:0 auto;padding:14px 16px 0;display:flex;gap:10px;justify-content:flex-end}
.toolbar button{border:1.5px solid var(--line-strong);background:#fff;color:var(--ink);font-family:var(--body);font-weight:600;font-size:13px;padding:9px 16px;border-radius:10px;cursor:pointer}
.toolbar button.primary{background:var(--green);border-color:var(--green);color:#fff}
.toolbar button:hover{filter:brightness(.97)}
.rpage{background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);padding:44px 48px;margin-bottom:20px}
.rhead{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid var(--graphite);padding-bottom:16px;margin-bottom:26px}
.rhead .rt{font-family:var(--disp);font-weight:700;font-size:26px;letter-spacing:-.02em}
.rhead .rt small{display:block;font-size:12px;font-weight:500;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);margin-bottom:3px}
.rhead img{height:52px}
.rhead .rr{display:flex;flex-direction:column;align-items:flex-end;gap:8px}
.rdisc{display:inline-block;font-family:var(--disp);font-weight:600;font-size:13px;letter-spacing:.02em;color:#fff;background:var(--graphite);border-radius:999px;padding:5px 13px;white-space:nowrap}
.rcover{display:flex;flex-direction:column;justify-content:space-between;text-align:center;min-height:250mm}
.rcover .cvtop{padding-top:24mm}
.rcover .cvlogo{height:74px;margin:0 auto 34px;display:block}
.rcover .cvrule{width:66px;height:3px;margin:0 auto 26px;background:linear-gradient(90deg,var(--accent),var(--graphite));border-radius:2px}
.rcover .cveyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.30em;text-transform:uppercase;color:var(--accent);margin-bottom:20px}
.rcover .cvtitle{font-family:var(--disp);font-weight:700;font-size:46px;line-height:1.04;letter-spacing:-.02em;color:var(--ink);margin:0 0 12px}
.rcover .cvdisc{font-family:var(--disp);font-weight:500;font-size:19px;color:var(--muted);margin-bottom:46px}
.rcover .cvname{font-family:var(--disp);font-weight:600;font-size:25px;color:var(--ink)}
.rcover .cvdate{font-size:14px;color:var(--muted);margin-top:5px}
.rcover .cvfoot{border-top:1px solid var(--line);padding:18px 0 4px;font-size:12.5px;color:var(--muted);line-height:1.5}
.rcover .cvfoot .cvbrand{font-family:var(--disp);font-weight:600;color:var(--ink);font-size:14.5px}
.rsec{margin-bottom:30px}
.rsec:last-child{margin-bottom:0}
.rsec h3{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:600;margin:0 0 12px;display:flex;align-items:center;gap:10px}
.rsec h3::before{content:attr(data-n);font-family:var(--mono);background:var(--graphite);color:#fff;width:22px;height:22px;border-radius:6px;display:grid;place-items:center;font-size:11px;flex:none}
.rsec p{font-size:13.5px;line-height:1.62;color:#33404F;margin:0 0 10px}
.rsec p:last-child{margin-bottom:0}
.basics{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.basics .b{background:#fff;padding:13px 15px}
.basics .b .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:600}
.basics .b .v{font-family:var(--disp);font-weight:600;font-size:15px;margin-top:3px}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.kv .b{background:#fff;padding:11px 15px}
.kv .b.wide{grid-column:1/-1}
.kv .b .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);font-weight:600}
.kv .b .v{font-size:13.5px;margin-top:2px;color:var(--ink)}
.kv .b .v.leeg{color:var(--faint)}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.cards .t{border:1px solid var(--line);border-radius:12px;padding:16px;position:relative;overflow:hidden;background:#fff}
.cards .t::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--bar,var(--green))}
.cards .t .tl{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.cards .t .tv{font-size:13.5px;line-height:1.55;margin-top:6px;color:#33404F}
.cards .t .tv.leeg{color:var(--faint)}
.lead{margin:0 0 10px}
.lead b{color:var(--ink)}
.pk{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.pk .p{border:1.5px solid var(--line);border-radius:12px;padding:16px;background:#fff;position:relative}
.pk .p.gekozen{border-color:var(--accent);box-shadow:0 0 0 3px rgba(91,31,44,.10);background:linear-gradient(0deg,rgba(91,31,44,.03),rgba(91,31,44,.03)),#fff}
.pk .p .badge{position:absolute;top:12px;right:12px;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#fff;background:var(--accent);border-radius:999px;padding:3px 9px}
.pk .p .pn{font-family:var(--disp);font-weight:700;font-size:16px}
.pk .p .pp{font-family:var(--mono);font-size:12.5px;color:var(--accent);margin:2px 0 10px}
.pk .p ul{margin:0;padding-left:16px;font-size:12.5px;line-height:1.5;color:#33404F}
.pk .p li{margin-bottom:3px}
ul.bul{margin:0;padding-left:18px;font-size:13.5px;line-height:1.6;color:#33404F}
ul.bul li{margin-bottom:6px}
ul.bul b{color:var(--ink)}
.rzones{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:4px}
.rzones th{text-align:left;padding:8px 8px;border-bottom:2px solid var(--graphite);font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.rzones td{padding:8px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
.rzones .zc{width:7px;height:24px;border-radius:3px;display:inline-block;vertical-align:middle;margin-right:8px}
.rzones .zn{font-family:var(--disp);font-weight:600}
.rzones .mono{font-family:var(--mono);font-size:12px;white-space:nowrap}
.rzones .zd{font-size:11.5px;color:var(--muted);line-height:1.4}
.advice-note{border-left:3px solid var(--accent);background:var(--surface-2);border-radius:0 10px 10px 0;padding:12px 16px}
.advice-note .an-lbl{font-family:var(--disp);font-weight:600;font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);margin-bottom:5px}
.advice-note p{margin:0;font-size:13.5px;line-height:1.6}
.steps{list-style:none;margin:14px 0 0;padding:0}
.steps li{display:flex;gap:10px;align-items:flex-start;font-size:13.5px;line-height:1.55;padding:7px 0;border-bottom:1px dotted var(--line)}
.steps li:last-child{border-bottom:none}
.steps .box{flex:none;width:15px;height:15px;border:1.5px solid var(--green-dark);border-radius:4px;margin-top:3px}
.rfoot{border-top:1px solid var(--line);margin-top:34px;padding-top:16px;display:flex;justify-content:space-between;align-items:flex-end;font-size:12px;color:var(--muted)}
.rfoot .sig{font-family:var(--disp);color:var(--ink);font-weight:600}
.rnote{font-size:11.5px;color:var(--faint);margin-top:14px}
@media(max-width:640px){.basics,.cards,.pk{grid-template-columns:1fr 1fr}.kv{grid-template-columns:1fr}.rpage{padding:26px 20px}}
@media print{
  @page{size:A4;margin:14mm}
  body{background:#fff}
  .toolbar{display:none!important}
  .report{max-width:none;margin:0;padding:0}
  .rpage{border:none;box-shadow:none;border-radius:0;padding:0 0 6mm;margin:0}
  .rcover{min-height:auto;height:247mm;padding:0;page-break-after:always}
  .rsec,.cards .t,.pk .p,.kv,.basics{page-break-inside:avoid;break-inside:avoid}
  .pagebreak{page-break-before:always;break-before:page}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""

VERSLAG_JS = """
function dmPrint(){window.print();}
function dmOpen(){
  var b=new Blob(['<!doctype html>'+document.documentElement.outerHTML],{type:'text/html'});
  window.open(URL.createObjectURL(b),'_blank');
}
"""


def _kv(items, wide_laatste=False):
    cellen = []
    for i, (k, v) in enumerate(items):
        leeg = not str(v or '').strip()
        klas = 'b wide' if (wide_laatste and i == len(items) - 1) else 'b'
        cellen.append(f'<div class="{klas}"><div class="k">{_e(k)}</div>'
                      f'<div class="v{" leeg" if leeg else ""}">{_of_streep(v)}</div></div>')
    return '<div class="kv">' + ''.join(cellen) + '</div>'


def _kort(s, n=46):
    s = ' '.join(str(s or '').split())
    return s if len(s) <= n else s[:n - 1].rstrip() + '…'


def verslag_html(v):
    """Zelfstandig HTML-verslag (fonts via Google Fonts, logo ingebed) — te bekijken in de app,
    te openen in een nieuw tabblad en via de browser te bewaren als PDF."""
    v = normaliseer(v)
    a, c, f, d, e, af = v['algemeen'], v['coach'], v['facturatie'], v['doelen'], v['ervaring'], v['afspraken']
    logo = _logo_uri()
    sport = a['sport'] or 'Coaching'
    naam = a['naam'] or '—'
    contact_coach = '  ·  '.join(x for x in [c['email'], c['gsm']] if x)
    doel = d['lange_termijn'] or d['korte_termijn'] or d['wedstrijden']

    logo_img = f'<img class="cvlogo" src="{logo}" alt="De Musculatuur">' if logo else ''
    logo_head = f'<img src="{logo}" alt="De Musculatuur">' if logo else ''

    cover = f"""
<div class="rpage rcover">
  <div class="cvtop">
    {logo_img}
    <div class="cvrule"></div>
    <div class="cveyebrow">Intake · Verslag</div>
    <h1 class="cvtitle">Intakeverslag</h1>
    <div class="cvdisc">Coachingsoverzicht · {_e(sport)}</div>
    <div class="cvwho"><div class="cvname">{_e(naam)}</div><div class="cvdate">{_e(a['datum'])}</div></div>
  </div>
  <div class="cvfoot">
    <div class="cvbrand">De Musculatuur</div>
    <div>{_e(c['naam'])}</div>
    <div>{_e(contact_coach)}</div>
  </div>
</div>"""

    # 1 · Samenvatting
    intro = v['samenvatting'] or (f'Dit verslag bundelt wat we tijdens het intakegesprek op {a["datum"]} '
                                  f'besproken hebben: je uitgangspunt, je doelen en hoe we de samenwerking aanpakken.')
    s1 = f"""
<div class="rsec"><h3 data-n="1">Samenvatting</h3>
  <p>{_e(intro)}</p>
  <div class="basics">
    <div class="b"><div class="k">Naam</div><div class="v">{_e(naam)}</div></div>
    <div class="b"><div class="k">Intakedatum</div><div class="v">{_of_streep(a['datum'])}</div></div>
    <div class="b"><div class="k">Sport</div><div class="v">{_of_streep(a['sport'])}</div></div>
    <div class="b"><div class="k">Doel</div><div class="v">{_of_streep(_kort(doel, 34))}</div></div>
  </div>
</div>"""

    # 2 · Algemene gegevens
    coach_regel = ' · '.join(x for x in [c['naam'], c['gsm'], c['email']] if x)
    s2 = f"""
<div class="rsec"><h3 data-n="2">Algemene gegevens</h3>
  {_kv([('Naam atleet', a['naam']), ('Geboortejaar', a['geboortejaar']), ('Sportdiscipline', a['sport']),
        ('Datum intake', a['datum']), ('Contact atleet', a['contact']), ('Coach', coach_regel)])}
</div>"""

    # 3 · Facturatie
    fact_items = [('Naam / bedrijf', f['naam_bedrijf']), ('Adres', f['adres']),
                  ('Postcode / gemeente', f['postcode_gemeente']), ('E-mailadres voor facturen', f['email']),
                  ('BTW-nummer', f['btw']), ('Voorkeur betalingsmethode', f['betaling']),
                  ('Facturatie op naam van', f['op_naam_van'])]
    ontbreekt = any(not str(w or '').strip() for _, w in fact_items)
    s3 = f"""
<div class="rsec"><h3 data-n="3">Facturatiegegevens</h3>
  {_kv(fact_items, wide_laatste=True)}
  {'<p class="rnote">De nog ontbrekende gegevens mag je me gewoon bezorgen; dan vul ik ze aan.</p>' if ontbreekt else ''}
</div>"""

    # 4 · Doelen
    def kaart(lbl, tekst, kleur):
        leeg = not str(tekst or '').strip()
        return (f'<div class="t" style="--bar:{kleur}"><div class="tl">{lbl}</div>'
                f'<div class="tv{" leeg" if leeg else ""}">{_e(tekst) if not leeg else "Nog te bepalen"}</div></div>')
    s4 = f"""
<div class="rsec"><h3 data-n="4">Doelen</h3>
  <div class="cards">
    {kaart('Korte termijn', d['korte_termijn'], '#22B8CF')}
    {kaart('Lange termijn', d['lange_termijn'], '#5B1F2C')}
    {kaart('Wedstrijden & events', d['wedstrijden'], '#F97316')}
  </div>
</div>"""

    # 5 · Ervaring & aandachtspunten
    erv = [('Trainingservaring', e['trainingservaring']), ('Testing', e['testing']),
           ('Blessures & aandachtspunten', e['blessures']), ('Beschikbaarheid & context', e['beschikbaarheid']),
           ('Materiaal & data', e['materiaal'])]
    erv_html = ''.join(f'<p class="lead"><b>{lbl}</b> — {_e(t)}</p>' for lbl, t in erv if str(t or '').strip())
    s5 = f"""
<div class="rsec"><h3 data-n="5">Eerdere prestaties &amp; ervaring</h3>
  {erv_html or '<p class="rnote">Niet besproken tijdens de intake.</p>'}
</div>"""

    # 6 · Pakket
    def pakket_kaart(p):
        gekozen = p['key'] == v['pakket']
        return (f'<div class="p{" gekozen" if gekozen else ""}">{"<span class=\"badge\">Gekozen</span>" if gekozen else ""}'
                f'<div class="pn">{_e(p["naam"])}</div><div class="pp">{_e(p["prijs"])}</div>'
                f'<ul>{"".join(f"<li>{_e(x)}</li>" for x in p["punten"])}</ul></div>')
    pakket_tekst = (f'We gaan verder met het pakket <b>{_e(next(p["naam"] for p in PAKKETTEN if p["key"] == v["pakket"]))}</b>.'
                    if v['pakket'] else 'Het pakket leggen we nog samen vast; hieronder de drie mogelijkheden.')
    s6 = f"""
<div class="rsec pagebreak"><h3 data-n="6">Coachingpakket</h3>
  <p>{pakket_tekst}</p>
  <div class="pk">{''.join(pakket_kaart(p) for p in PAKKETTEN)}</div>
</div>"""

    # 7 · In je pakket, 8 · TrainingPeaks, 9 · Zones
    s7 = f"""
<div class="rsec"><h3 data-n="7">Wat zit er in je pakket?</h3>
  <p>Afhankelijk van het gekozen pakket omvat onze coaching standaard deze elementen om jouw prestaties te optimaliseren:</p>
  <ul class="bul">{''.join(f'<li><b>{_e(k)}:</b> {_e(t)}</li>' for k, t in IN_PAKKET)}</ul>
</div>"""
    s8 = f"""
<div class="rsec"><h3 data-n="8">TrainingPeaks</h3>
  <p>{_e(TRAININGPEAKS_INTRO)}</p>
  <ul class="bul">{''.join(f'<li><b>{_e(k)}:</b> {_e(t)}</li>' for k, t in TRAININGPEAKS)}</ul>
</div>"""
    rijen = ''.join(
        f'<tr><td><span class="zc" style="background:{kleur}"></span><span class="zn">{z}</span> · {_e(n)}</td>'
        f'<td class="zd">{_e(doel_)}</td><td class="mono">{_e(ind)}</td></tr>'
        for z, n, doel_, ind, kleur in ZONES)
    s9 = f"""
<div class="rsec"><h3 data-n="9">Trainingszones</h3>
  <p>{_e(ZONES_INTRO)}</p>
  <table class="rzones"><thead><tr><th style="width:30%">Zone</th><th>Intensiteit &amp; doel</th><th style="width:28%">Indicatie</th></tr></thead>
  <tbody>{rijen}</tbody></table>
</div>"""

    # 10 · Afspraken
    afspr = [('Feedbackmomenten', af['feedback']), ('Communicatie', af['communicatie']),
             ('Aanpassingen schema', af['aanpassingen']), ('Verwachtingen atleet', af['verwachtingen'])]
    s10 = f"""
<div class="rsec"><h3 data-n="10">Praktische afspraken</h3>
  <ul class="bul">{''.join(f'<li><b>{_e(k)}:</b> {_e(t)}</li>' for k, t in afspr if str(t or '').strip())}</ul>
</div>"""

    # 11 · Advies & volgende stappen
    stappen = ''.join(f'<li><span class="box"></span><span>{_e(s)}</span></li>' for s in v['volgende_stappen'])
    advies_blok = (f'<div class="advice-note"><div class="an-lbl">Advies van de coach</div><p>{_e(v["advies"])}</p></div>'
                   if v['advies'] else '')
    s11 = ''
    if advies_blok or stappen:
        s11 = f"""
<div class="rsec"><h3 data-n="11">Advies &amp; volgende stappen</h3>
  {advies_blok}
  {f'<ul class="steps">{stappen}</ul>' if stappen else ''}
</div>"""

    voet = f"""
<div class="rfoot">
  <div>Aarzel niet mij te contacteren bij verdere vragen.<br><span class="sig">{_e(c['naam'])}</span></div>
  <div style="text-align:right"><div class="sig">De Musculatuur</div>
    {f'<div>{_e(c["email"])}</div>' if c['email'] else ''}{f'<div>{_e(c["gsm"])}</div>' if c['gsm'] else ''}</div>
</div>
<p class="rnote" style="margin-top:8px">Opgesteld op basis van ons intakegesprek van {_e(a['datum'])}, nagelezen en aangevuld door je coach.</p>"""

    body = f"""
<div class="rpage">
  <div class="rhead">
    <div class="rt"><small>{_e(sport)} · Rapport</small>Intakeverslag</div>
    <div class="rr">{logo_head}<span class="rdisc">{_e(sport)}</span></div>
  </div>
  {s1}{s2}{s3}{s4}{s5}{s6}{s7}{s8}{s9}{s10}{s11}
  {voet}
</div>"""

    return f"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Intakeverslag — {_e(naam)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Poppins:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>{VERSLAG_CSS}</style><script>{VERSLAG_JS}</script></head>
<body>
<div class="toolbar"><button onclick="dmOpen()">Open in nieuw tabblad</button><button class="primary" onclick="dmPrint()">Bewaar als PDF</button></div>
<div class="report">{cover}{body}</div>
</body></html>"""
