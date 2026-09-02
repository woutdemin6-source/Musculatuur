"""
De Musculatuur — gedeelde analyse-kern (v1)

Deze module bevat de eigenlijke reken-/parsing-logica, gedeeld door:
  - analyze_athlete.py (command-line tool)
  - app.py             (web-app / Streamlit)

Zo blijft er precies 1 plek waar de A:C ratio- en trainingslast-berekening
gebeurt — geen risico dat CLI en website ooit uit sync raken.
"""
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

DUTCH_MONTHS = {'jan': 'Jan', 'feb': 'Feb', 'mrt': 'Mar', 'apr': 'Apr', 'mei': 'May', 'jun': 'Jun',
                'jul': 'Jul', 'aug': 'Aug', 'sep': 'Sep', 'okt': 'Oct', 'nov': 'Nov', 'dec': 'Dec'}

# Strava exporteert kolomnamen in de taal die op het account van de atleet staat ingesteld —
# niet elke atleet heeft dat op Nederlands staan. Deze aliassen zorgen dat de tool ook werkt met
# een Engelstalige export (het meest voorkomende alternatief), door de kolom te hernoemen naar de
# Nederlandse naam die de rest van deze module gebruikt.
COLUMN_ALIASES = {
    'Datum van activiteit': ['Activity Date'],
    'Activiteitstype': ['Activity Type'],
    'Beweegtijd': ['Moving Time'],
    'Verstreken tijd.1': ['Elapsed Time.1', 'Elapsed Time'],
    'Afstand.1': ['Distance.1', 'Distance'],
    'Totale stijging': ['Elevation Gain'],
    'Gemiddelde hartslag': ['Average Heart Rate'],
    'Trainingsbelasting': ['Relative Effort', 'Perceived Exertion', 'Training Load'],
}

SPORT_LABELS = {
    'Hardloopsessie': 'Hardlopen', 'Fietsrit': 'Fietsen', 'Virtuele fietsrit': 'Fietsen',
    'Zwemmen': 'Zwemmen', 'Krachttraining': 'Krachttraining', 'Wandeling': 'Wandelen',
    'Hiken': 'Hiken', 'Stepapparaat': 'Stepapparaat', 'Training': 'Training', 'Kayakken': 'Kayakken',
}
# Groepering voor rapportage/gap-detectie: indoor en outdoor fietsen tellen als 1 sport.
# (Voor de trainingslast-kalibratie wordt wel nog het originele Strava-type gebruikt,
# want de hartslag/last-verhouding kan licht verschillen tussen trainer en weg.)
SPORT_GROUP = {'Fietsrit': 'Fietsen', 'Virtuele fietsrit': 'Fietsen'}


def sport_group(activiteitstype: str) -> str:
    return SPORT_GROUP.get(activiteitstype, activiteitstype)


def parse_dutch_date(s):
    if pd.isna(s):
        return pd.NaT
    s2 = s
    for nl, en in DUTCH_MONTHS.items():
        s2 = re.sub(nl, en, s2, flags=re.IGNORECASE)
    try:
        return pd.to_datetime(s2, format='%d %b %Y, %H:%M:%S')
    except Exception:
        try:
            return pd.to_datetime(s2, errors='coerce')
        except Exception:
            return pd.NaT


def load_export_from_path(export_path: Path, workdir: Path) -> pd.DataFrame:
    """Laad een Strava-export vanaf een bestandspad op disk (.zip of .csv)."""
    if str(export_path).lower().endswith('.csv'):
        return _process_activities_df(_read_csv_robust(export_path))
    with zipfile.ZipFile(export_path) as z:
        return _load_export_from_zip(z, workdir)


def load_export_from_fileobj(file_obj, workdir: Path) -> pd.DataFrame:
    """Laad een Strava-export vanaf een in-memory file object (bv. Streamlit file_uploader), .zip formaat."""
    with zipfile.ZipFile(file_obj) as z:
        return _load_export_from_zip(z, workdir)


def load_csv_from_fileobj(file_obj) -> pd.DataFrame:
    """Laad activities.csv rechtstreeks (zonder zip) — veel lichter en sneller dan de volledige export.
    Dit is het enige bestand uit een Strava-export dat deze tool effectief gebruikt; de rest van de
    zip (losse .fit/.gpx-bestanden per activiteit, foto's, video's) is overbodige data voor dit doel."""
    return _process_activities_df(_read_csv_robust(file_obj))


def _load_export_from_zip(z: zipfile.ZipFile, workdir: Path) -> pd.DataFrame:
    names = z.namelist()
    if 'activities.csv' not in names:
        raise ValueError('Geen activities.csv gevonden in het exportbestand. Is dit een geldige Strava-export?')
    z.extract('activities.csv', workdir)
    return _process_activities_df(_read_csv_robust(workdir / 'activities.csv'))


def _read_csv_robust(source) -> pd.DataFrame:
    """Leest een CSV in met een aantal encoding-fallbacks. Strava-exports zijn meestal UTF-8, maar
    kunnen afhankelijk van hoe/waar ze gedownload/geopend werden ook UTF-8-met-BOM of Latin-1 zijn -
    zonder fallback geeft een verkeerde encoding een cryptische crash i.p.v. gewoon in te lezen."""
    last_err = None
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            if hasattr(source, 'seek'):
                source.seek(0)
            return pd.read_csv(source, encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError) as e:
            last_err = e
            continue
    if hasattr(source, 'seek'):
        source.seek(0)
    try:
        return pd.read_csv(source)
    except Exception:
        raise last_err or Exception('Kon het CSV-bestand niet inlezen (onbekende encoding).')


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Hernoemt bekende Engelse kolomnamen naar hun Nederlandse equivalent (zie COLUMN_ALIASES),
    zodat de rest van deze module met 1 vaste set kolomnamen kan werken ongeacht de taalinstelling
    van het Strava-account waarmee de export gemaakt is."""
    rename_map = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical in df.columns:
            continue
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = canonical
                break
    return df.rename(columns=rename_map) if rename_map else df


def _process_activities_df(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_columns(df)
    if 'Datum van activiteit' not in df.columns:
        kolommen = ', '.join(str(c) for c in df.columns[:15]) + ('...' if len(df.columns) > 15 else '')
        raise ValueError(
            "Geen datumkolom gevonden (verwacht 'Datum van activiteit' of 'Activity Date'). "
            f"Gevonden kolommen: {kolommen}. Is dit zeker het activities.csv-bestand uit een Strava-export?"
        )
    if 'Activiteitstype' not in df.columns:
        kolommen = ', '.join(str(c) for c in df.columns[:15]) + ('...' if len(df.columns) > 15 else '')
        raise ValueError(
            "Geen sporttype-kolom gevonden (verwacht 'Activiteitstype' of 'Activity Type'). "
            f"Gevonden kolommen: {kolommen}. Is dit zeker het activities.csv-bestand uit een Strava-export?"
        )
    df['date'] = df['Datum van activiteit'].apply(parse_dutch_date)
    df = df.dropna(subset=['date'])
    for c in ['Beweegtijd', 'Verstreken tijd.1', 'Afstand.1', 'Totale stijging', 'Gemiddelde hartslag', 'Trainingsbelasting']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        else:
            df[c] = np.nan
    df['day'] = df['date'].dt.date
    if len(df) == 0:
        raise ValueError('Geen bruikbare activiteiten gevonden in export (kolommen wel herkend, maar geen enkele '
                          'rij had een leesbare datum). Controleer het datumformaat in het bestand.')
    return df


def estimate_load(df: pd.DataFrame) -> pd.DataFrame:
    """Trainingslast = Strava 'Trainingsbelasting' waar aanwezig; anders geschat
    via een per-sporttype ratio (last / (gem. hartslag * duur_min)), gekalibreerd
    op de eigen data van de atleet zelf (dus generiek, niet hardcoded)."""
    df = df.copy()
    sub = df.dropna(subset=['Trainingsbelasting', 'Gemiddelde hartslag', 'Beweegtijd'])
    sub = sub[sub['Beweegtijd'] > 0].copy()
    ratios = {}
    blended = None
    if len(sub) > 0:
        sub['ratio'] = sub['Trainingsbelasting'] / (sub['Gemiddelde hartslag'] * sub['Beweegtijd'] / 60.0)
        ratios = sub.groupby('Activiteitstype')['ratio'].median().to_dict()
        blended = sub['ratio'].median()

    def _est(row):
        if pd.notna(row['Trainingsbelasting']):
            return row['Trainingsbelasting'], 'actual'
        has_hr_duration = pd.notna(row['Gemiddelde hartslag']) and pd.notna(row['Beweegtijd']) and row['Beweegtijd'] > 0
        if has_hr_duration and blended is not None:
            r = ratios.get(row['Activiteitstype'], blended)
            return r * row['Gemiddelde hartslag'] * row['Beweegtijd'] / 60.0, 'estimated'
        # Onderscheid: ontbrekende hartslag/duur (nooit te schatten) versus wél hartslag/duur maar
        # geen enkele sessie met Trainingsbelasting om een ijkpunt uit af te leiden (deze atleet
        # heeft dan nergens een kalibratie-ratio) — anders wordt dit laatste ten onrechte als
        # "hartslagdata ontbreekt" gerapporteerd terwijl de echte oorzaak elders ligt.
        if has_hr_duration:
            return 0.0, 'no_calibration'
        return 0.0, 'missing'

    res = df.apply(_est, axis=1)
    df['load'] = res.apply(lambda x: x[0])
    df['load_source'] = res.apply(lambda x: x[1])
    return df


def compute_acwr(df: pd.DataFrame, today: pd.Timestamp):
    daily = df.groupby('day')['load'].sum()
    daily.index = pd.to_datetime(daily.index)
    full_range = pd.date_range(df['date'].min().normalize(), today, freq='D')
    daily = daily.reindex(full_range, fill_value=0.0)
    acute = daily.rolling(7, min_periods=1).sum()
    chronic = daily.rolling(28, min_periods=1).sum() / 4.0
    # De ratio zelf wordt berekend via twee dag-gemiddeldes (i.p.v. rechtstreeks acute/chronic),
    # zodat ze ook correct is zolang het 7- of 28-dagen venster nog niet volledig gevuld is (bv. de
    # eerste weken van een nieuwe atleet) — anders wordt een gedeeltelijke som toch afgezet tegen
    # een volledig 4-weken-gemiddelde, wat de ratio kunstmatig laat afwijken van 1,0 bij een
    # gelijkmatige belasting. Zodra beide vensters vol zijn is dit wiskundig identiek aan de
    # klassieke acute/(chronic/4)-formule (de 'acute' en 'chronic' hierboven blijven ongewijzigd
    # voor rapportage, bv. acute7d/chronic28d_weekly_avg in de JSON-export).
    acute_avg = daily.rolling(7, min_periods=1).mean()
    chronic_avg = daily.rolling(28, min_periods=1).mean()
    acwr = acute_avg / chronic_avg.replace(0, np.nan)
    return daily, acute, chronic, acwr


def period_summary(df: pd.DataFrame, days: int, today: pd.Timestamp, label: str):
    d = df[df['date'] >= today - pd.Timedelta(days=days)].copy()
    d['_group'] = d['Activiteitstype'].apply(sport_group)
    by_sport = []
    for sport, g in d.groupby('_group'):
        by_sport.append({
            'sport': SPORT_LABELS.get(sport, sport),
            'sessies': int(len(g)),
            'uren': round(g['Beweegtijd'].sum() / 3600.0, 1),
            'km': round(g['Afstand.1'].sum() / 1000.0, 1),
            'hm': round(float(g['Totale stijging'].sum())) if g['Totale stijging'].notna().any() else 0,
            'hr': round(float(g['Gemiddelde hartslag'].mean())) if g['Gemiddelde hartslag'].notna().any() else None,
            'load': round(float(g['load'].sum())),
        })
    by_sport.sort(key=lambda x: -x['load'])
    start = today - pd.Timedelta(days=days)
    return {
        'label': f"{label} ({start.strftime('%d %b')} - {today.strftime('%d %b %Y')})",
        # Lengte van de periode: de jaarplanning rekent hiermee sessies/week per sport uit.
        '_dagen': days,
        'sessies': int(len(d)),
        'uren': round(d['Beweegtijd'].sum() / 3600.0, 1),
        'km': round(d['Afstand.1'].sum() / 1000.0, 1),
        'hoogtemeters': round(float(d['Totale stijging'].sum())) if d['Totale stijging'].notna().any() else 0,
        'load': round(float(d['load'].sum())),
        'bySport': by_sport,
    }


def detect_gaps(df: pd.DataFrame, today: pd.Timestamp, min_history_sessions=5, absence_days=182):
    """Sporten die historisch >=N keer voorkomen maar afwezig zijn in de laatste periode -> mogelijke blinde vlek."""
    gaps = []
    grp = df['Activiteitstype'].apply(sport_group)
    counts = grp.value_counts()
    recent = grp[df['date'] >= today - pd.Timedelta(days=absence_days)].unique()
    for sport, n in counts.items():
        if n >= min_history_sessions and sport not in recent:
            last_date = df[grp == sport]['date'].max()
            gaps.append({
                'sport': SPORT_LABELS.get(sport, sport),
                'totaal_historisch': int(n),
                'laatste_sessie': last_date.strftime('%d %b %Y'),
                'dagen_geleden': int((today - last_date).days),
            })
    return gaps


def generate_advies(acwr_table, current, weeks_green, weeks_high, weeks_low, weeks_total, gaps):
    """Regelgebaseerd trainingsadvies voor de komende 1-2 weken, afgeleid uit de ACWR-stand en -trend.

    Uitgangspunten (zie literatuurstudie h.3-4): sweet spot 0,8-1,3; verhoogd risico bij ACWR>1,5;
    vuistregel van max. ~5-10% wekelijkse opbouw van de belasting. Dit is een advies-signaal op basis
    van 1 parameter (trainingslast) — geen diagnose, geen automatische planning. De coach combineert dit
    altijd met herstelindicatoren, klachten en context, en beslist het uiteindelijke programma.
    """
    items = []
    if current is None:
        items.append({'level': 'info', 'title': 'Onvoldoende data voor een advies',
                      'text': 'Er is nog niet genoeg recente trainingsdata om een betrouwbaar advies te berekenen. '
                              'Zodra er enkele weken aan sessies bijkomen, verschijnt hier een advies.'})
        return items

    # 1. Statusbepaling op basis van de huidige ACWR
    if current > 1.5:
        items.append({'level': 'alert', 'title': 'Piekbelasting — bouw bewust af',
                      'text': f'ACWR staat op {current:.1f}, ruim boven de sweet spot (0,8-1,3). Advies: verlaag het '
                              'trainingsvolume deze week merkbaar (richtlijn: ~20-30% minder), zet in op herstel '
                              '(slaap, voeding, actief herstel) en bouw pas weer op zodra vermoeidheid/klachten '
                              'genormaliseerd zijn.'})
    elif current > 1.3:
        items.append({'level': 'warning', 'title': 'Boven de sweet spot — stabiliseren',
                      'text': f'ACWR staat op {current:.1f}. Advies: geen verdere opbouw deze week — houd het volume '
                              'gelijk of bouw licht af, en plan een extra hersteldag of een lichtere sessie in.'})
    elif current < 0.8:
        items.append({'level': 'warning', 'title': 'Onder de sweet spot — ruimte om op te bouwen',
                      'text': f'ACWR staat op {current:.1f}, wat kan wijzen op een rustige periode of onderbelasting. '
                              'Advies: als er geen blessure of aanhoudende vermoeidheid speelt, kan de belasting de '
                              'komende 1-2 weken geleidelijk omhoog (richtlijn: max. ~5-10% per week).'})
    else:
        items.append({'level': 'positive', 'title': 'In de sweet spot',
                      'text': f'ACWR staat op {current:.1f}, binnen de veilige zone. Advies: goed moment om de belasting '
                              'gecontroleerd verder op te bouwen (richtlijn: max. ~5-10% per week) als het doel dat '
                              'vraagt, of om te consolideren op dit niveau.'})

    # 2. Trend van de laatste weken: snelle, aanhoudende stijging = verhoogd risico
    recent = [w['acwr'] for w in acwr_table[-4:] if w['acwr'] is not None]
    if len(recent) >= 3:
        stijgingen = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1] + 0.05)
        if stijgingen >= len(recent) - 1 and (recent[-1] - recent[0]) > 0.2:
            items.append({'level': 'warning', 'title': 'Snel stijgende belasting over meerdere weken',
                          'text': 'De ACWR is de laatste weken gestaag gestegen. Advies: bouw een lichtere week '
                                  '("deload") in voor verder op te bouwen, om het risico op een piekbelasting te beperken.'})

    # 3. Consistentie: sterk wisselende weken (veel pieken/dalen) is doorgaans risicovoller dan een gelijkmatige opbouw
    if weeks_total >= 8 and (weeks_green / weeks_total) < 0.4:
        items.append({'level': 'info', 'title': 'Belasting schommelt sterk',
                      'text': f'Slechts {weeks_green} van de laatste {weeks_total} weken zaten in de sweet spot '
                              f'({weeks_high} te hoog, {weeks_low} te laag). Advies: probeer een gelijkmatiger '
                              'wekelijks patroon aan te houden — dat is doorgaans veiliger dan afwisselend erg '
                              'hoge en erg lage weken.'})

    # 4. Blinde vlekken -> concreet heropbouw-advies
    for g in gaps:
        items.append({'level': 'info', 'title': f"Heropstart overwegen: {g['sport']}",
                      'text': f"{g['sport']} is al {g['dagen_geleden']} dagen afwezig (laatste sessie: "
                              f"{g['laatste_sessie']}). Advies: bij heropstart eerst laag volume en lage intensiteit "
                              "om het lichaam te laten wennen, en pas daarna geleidelijk opbouwen."})

    return items


def _acwr_overview(acwr: pd.Series, today: pd.Timestamp):
    """Bouwt de 16-weken ACWR-tabel en telt hoe die weken verdeeld zijn over de zones.
    Gedeeld door build_summary (volledige analyse) en compute_belastbaarheid (lichte versie),
    zodat beide gegarandeerd dezelfde cijfers geven."""
    weekly_dates = pd.date_range(end=today, periods=16, freq='W')
    acwr_table = []
    for d in weekly_dates:
        v = acwr.asof(d)
        acwr_table.append({'week_ending': d.strftime('%d %b'), 'acwr': None if pd.isna(v) else round(float(v), 1)})
    valid_vals = [w['acwr'] for w in acwr_table if w['acwr'] is not None]
    weeks_green = sum(1 for v in valid_vals if 0.8 <= v <= 1.3)
    weeks_high = sum(1 for v in valid_vals if v > 1.3)
    weeks_low = sum(1 for v in valid_vals if v < 0.8)
    return acwr_table, weeks_green, weeks_high, weeks_low, len(valid_vals)


def compute_belastbaarheid(df: pd.DataFrame, today: pd.Timestamp) -> dict:
    """Lichte berekening: enkel de huidige belastbaarheid (A:C ratio) uit een activities.csv.

    Geen grafiek, geen periode-overzichten en geen trainingsadvies — dat blijft voorbehouden
    aan build_summary (de Belastbaarheidsanalyse-tool). Wél het sportprofiel en de blinde
    vlekken: de jaarplanning heeft die nodig om concrete actiepunten per discipline te kunnen
    formuleren ("0,8x/week gezwommen" → techniekfocus), niet alleen een A:C ratio."""
    df = estimate_load(df)
    _daily, acute, chronic, acwr = compute_acwr(df, today)
    current = float(acwr.iloc[-1]) if not np.isnan(acwr.iloc[-1]) else None
    _table, weeks_green, weeks_high, weeks_low, weeks_total = _acwr_overview(acwr, today)
    periode_3m = period_summary(df, 91, today, 'Laatste 3 maanden')
    return {
        'current': None if current is None else round(current, 1),
        'acute7d': round(float(acute.iloc[-1])),
        'chronic28d_weekly_avg': round(float(chronic.iloc[-1])),
        'weeks_green': weeks_green, 'weeks_high': weeks_high, 'weeks_low': weeks_low,
        'weeks_total': weeks_total,
        'sessies': int(len(df)),
        'dateRange': {'from': df['date'].min().strftime('%d %b %Y'), 'to': df['date'].max().strftime('%d %b %Y')},
        'todayIso': today.strftime('%Y-%m-%d'),
        'profiel': sport_profiel(periode_3m),
        'gaps': detect_gaps(df, today),
    }


def build_summary(df: pd.DataFrame, athlete: str, today: pd.Timestamp) -> dict:
    """Bouwt het volledige summary-dict (zelfde vorm als summary.json van de CLI-tool)."""
    df = estimate_load(df)
    daily, acute, chronic, acwr = compute_acwr(df, today)
    current_acwr = float(acwr.iloc[-1]) if not np.isnan(acwr.iloc[-1]) else None

    acwr_table, weeks_green, weeks_high, weeks_low, n_valid = _acwr_overview(acwr, today)
    valid_vals = [w['acwr'] for w in acwr_table if w['acwr'] is not None]

    n_actual = int((df['load_source'] == 'actual').sum())
    n_estimated = int((df['load_source'] == 'estimated').sum())
    n_missing = int((df['load_source'] == 'missing').sum())
    n_no_calibration = int((df['load_source'] == 'no_calibration').sum())

    gaps = detect_gaps(df, today)
    advies = generate_advies(acwr_table, current_acwr, weeks_green, weeks_high, weeks_low, len(valid_vals), gaps)

    summary = {
        'athlete': athlete,
        'reportDate': today.strftime('%d %B %Y'),
        'todayIso': today.strftime('%Y-%m-%d'),
        'totalSessionsAllTime': int(len(df)),
        'dateRange': {'from': df['date'].min().strftime('%d %b %Y'), 'to': df['date'].max().strftime('%d %b %Y')},
        'periods': {
            '2j': period_summary(df, 730, today, 'Laatste 2 jaar'),
            '1j': period_summary(df, 365, today, 'Laatste jaar'),
            '6m': period_summary(df, 182, today, 'Laatste 6 maanden'),
            '3m': period_summary(df, 91, today, 'Laatste 3 maanden'),
            '4w': period_summary(df, 28, today, 'Laatste 4 weken'),
            '1w': period_summary(df, 7, today, 'Laatste week'),
        },
        'acwr': {
            'current': None if current_acwr is None else round(current_acwr, 1),
            'acute7d': round(float(acute.iloc[-1])),
            'chronic28d_weekly_avg': round(float(chronic.iloc[-1])),
            'weeks_green': weeks_green, 'weeks_high': weeks_high, 'weeks_low': weeks_low,
            'weeks_total': len(valid_vals),
            'table': acwr_table,
        },
        'gaps': gaps,
        'advies': advies,
        'dataQuality': {'actual': n_actual, 'estimated': n_estimated, 'excluded_no_hr': n_missing,
                         'excluded_no_calibration': n_no_calibration},
    }
    return summary, daily, acute, chronic, acwr


# ---------------------------------------------------------------------------
# Jaarplanning: macro/mesocyclus-voorstel voor max. 3 A-doelen per jaar.
#
# Structuur en volgorde van de fasen volgen Joe Friel (Basis -> Opbouw -> Piek -> Taper,
# terugwerkend gepland vanaf de wedstrijddatum; 3:1-belasting/hersteld-ritme binnen een blok)
# en Jan Olbrecht (aerobe capaciteit wordt als eerste en langst opgebouwd; drempel- en
# anaerobe prikkels worden bewust pas laat en gericht ingezet, op de aerobe basis die er al
# ligt, i.p.v. vroeg in het seizoen). De taper is vast: 2 weken, week -2 op 60% volume,
# wedstrijdweek op 40% volume met behoud van intensiteit (expliciet zo gevraagd).
#
# Dit is een voorstel op macro/mesocyclus-niveau (geen dag-per-dag trainingsschema) dat
# rekening houdt met de huidige belastbaarheid van de atleet. De coach vertaalt dit naar
# concrete sessies en past het aan op individuele context (klachten, wedstrijdkalender,
# levensfase, ...) - precies de "AI assisteert, coach beslist"-filosofie van de tool.
# ---------------------------------------------------------------------------

FASE_INFO = {
    'transitie': {
        'naam': 'Transitie (herstel)',
        'focus': 'Actief herstel na de vorige wedstrijd: laag volume, vrije/losse beweging, geen '
                 'structuur. Fysiek en mentaal herladen voor de volgende opbouw (Friel).',
        'volume': 'laag (~40-50%)', 'volume_pct': 45, 'intensiteit': 'laag',
    },
    'basis1': {
        'naam': 'Basis 1',
        'focus': 'Aerobe basis opbouwen: duurcapaciteit, algemene kracht en bewegingstechniek, '
                 'vrijwel uitsluitend lage intensiteit. Dit legt de aerobe fundering (o.a. '
                 'mitochondriale en capillaire aanpassingen) waar de rest van het seizoen op '
                 'steunt — deze aanpassingen hebben tijd nodig en worden daarom als eerste en '
                 'langst opgebouwd (Olbrecht).',
        'volume': 'opbouwend (~60-80%)', 'volume_pct': 70, 'intensiteit': 'laag',
    },
    'basis2': {
        'naam': 'Basis 2',
        'focus': 'Verdere opbouw van de aerobe capaciteit, kracht wordt sport-specifieker. Eerste, '
                 'beperkte impulsen net onder de drempel — de nadruk blijft op het aerobe systeem.',
        'volume': 'opbouwend (~75-90%)', 'volume_pct': 82, 'intensiteit': 'laag tot gematigd',
    },
    'basis3': {
        'naam': 'Basis 3',
        'focus': 'Spieruithouding en aerobe power verder uitbouwen. Aerobe capaciteit blijft '
                 'prioriteit — anaerobe systemen worden bewust nog niet gericht aangesproken '
                 '(Olbrecht).',
        'volume': 'opbouwend (~85-95%)', 'volume_pct': 90, 'intensiteit': 'gematigd',
    },
    'opbouw1': {
        'naam': 'Opbouw 1',
        'focus': 'Overgang naar wedstrijdspecifieke intensiteit: tempo- en drempelwerk wint aan '
                 'belang, het volume blijft hoog (Friel/Olbrecht-volgorde, met de volumepiek '
                 'bewust later — zie FORMULES.md).',
        'volume': 'hoog (~90-95%)', 'volume_pct': 92, 'intensiteit': 'gematigd tot hoog',
    },
    'opbouw2': {
        'naam': 'Opbouw 2',
        'focus': 'Wedstrijdspecifieke intensiteit staat centraal: drempel- en (waar relevant) '
                 'anaerobe capaciteit worden nu pas gericht getraind — bewust laat in het seizoen '
                 'en gebouwd op de al aanwezige aerobe basis (Olbrecht), niet ervoor in de plaats.',
        'volume': 'hoog (~90-100%)', 'volume_pct': 95, 'intensiteit': 'hoog',
    },
    'piek': {
        'naam': 'Piekblok',
        'focus': 'De zwaarste week van de cyclus, vlak voor de taper: hoogste weekbelasting '
                 'gecombineerd met wedstrijdspecifieke intensiteit en een wedstrijdsimulatie. '
                 'De taper erna zet die belasting om in vorm.',
        'volume': 'piekvolume (~100-110%) — hoogste van de cyclus', 'volume_pct': 105, 'intensiteit': 'hoog',
    },
    'taper_afbouw': {
        'naam': 'Taper — afbouwweek',
        'focus': 'Eerste taperweek: het volume gaat fors naar beneden, de intensiteit blijft '
                 'aanwezig zodat de scherpte behouden blijft.',
        'volume': '60% van het recente trainingsvolume', 'volume_pct': 60, 'intensiteit': 'behouden',
    },
    'wedstrijdweek': {
        'naam': 'Wedstrijdweek',
        'focus': 'Laatste week voor het A-doel: minimale belasting, enkel korte activerende '
                 'prikkels. Intensiteit blijft behouden, volume is minimaal.',
        'volume': '40% van het recente trainingsvolume', 'volume_pct': 40, 'intensiteit': 'behouden',
    },
}


# ---------------------------------------------------------------------------
# Data-gestuurde focuspunten per blok.
#
# De planning krijgt het sportprofiel van de atleet mee (sessies/week en aandeel in de
# trainingslast per sport, uit de laatste 3 maanden) plus de discipline van het A-doel.
# Daaruit volgen concrete actiepunten: een triatleet die 0,8x/week zwemt krijgt een
# techniek- en frequentiefocus op zwemmen, een loper met weinig loopvolume krijgt een
# loopvolume-blok in de basis, enzovoort.
#
# Alle drempels en teksten staan hieronder bij elkaar zodat de coach ze kan bijstellen
# zonder de planningslogica aan te raken.
# ---------------------------------------------------------------------------

# Welke sporten een A-doel nodig heeft. Sleutels = disciplines uit de doel-invoer,
# waarden = sportnamen zoals SPORT_LABELS ze teruggeeft.
DISCIPLINE_SPORTEN = {
    'Triatlon': ['Zwemmen', 'Fietsen', 'Hardlopen'],
    'Lopen': ['Hardlopen'],
    'Fietsen': ['Fietsen'],
    'Zwemmen': ['Zwemmen'],
    'Andere': [],
}

# Sporten waar techniek de beperkende factor is: daar heeft frequentie meer effect dan volume.
TECHNIEKSPORTEN = ['Zwemmen']

FOCUS_DREMPELS = {
    'sessies_zeer_laag': 0.75,   # minder dan ~3 sessies per maand
    'sessies_laag': 1.5,         # minder dan ~1,5 sessies per week
    'aandeel_laag': 0.15,        # minder dan 15% van de totale trainingslast
    'doelsessies_techniek': 3,   # streefdoel voor een techniekgevoelige sport
    'doelsessies_duur': 2,       # streefdoel voor een duursport
}


def sport_profiel(period: dict) -> dict:
    """Zet een periode-overzicht (uit period_summary) om naar een profiel per sport:
    sessies per week en aandeel in de totale trainingslast. Dat is wat de planning nodig
    heeft om te zien welke discipline achterblijft."""
    weken = max(1.0, period.get('_dagen', 91) / 7.0)
    totaal_load = sum(s['load'] for s in period.get('bySport', [])) or 1
    profiel = {}
    for s in period.get('bySport', []):
        profiel[s['sport']] = {
            'sessies': s['sessies'],
            'sessies_per_week': round(s['sessies'] / weken, 2),
            'uren': s['uren'],
            'km': s['km'],
            'aandeel': round(s['load'] / totaal_load, 3),
        }
    return profiel


def _sport_status(profiel: dict, sport: str) -> dict:
    """Beoordeelt één sport tegen de drempels hierboven."""
    p = profiel.get(sport)
    spw = p['sessies_per_week'] if p else 0.0
    aandeel = p['aandeel'] if p else 0.0
    if spw == 0:
        niveau = 'ontbreekt'
    elif spw < FOCUS_DREMPELS['sessies_zeer_laag']:
        niveau = 'zeer_laag'
    elif spw < FOCUS_DREMPELS['sessies_laag']:
        niveau = 'laag'
    else:
        niveau = 'ok'
    return {'sport': sport, 'sessies_per_week': spw, 'aandeel': aandeel, 'niveau': niveau}


def _sport_prioriteit(statussen: list) -> list:
    """Zwakste discipline eerst — daar valt de meeste winst te halen."""
    rang = {'ontbreekt': 0, 'zeer_laag': 1, 'laag': 2, 'ok': 3}
    return sorted(statussen, key=lambda s: (rang[s['niveau']], s['aandeel']))


def _acties_voor_blok(fase_key, statussen, gaps_sporten, discipline, cyclus_index, is_laatste,
                       is_eerste_van_blok=True):
    """Concrete actiepunten voor één cyclus van 4 weken binnen een blok.

    cyclus_index telt dóór over blokken heen (niet vanaf 0 per blok), zodat de opbouw blijft
    oplopen: als Basis 1 de zwemfrequentie naar 2x heeft gebracht, begint Basis 2 niet opnieuw
    bij 1x. Geeft een lijst korte, uitvoerbare regels terug."""
    acties = []
    is_basis = fase_key.startswith('basis')
    is_opbouw = fase_key.startswith('opbouw')

    if fase_key in ('taper_afbouw', 'wedstrijdweek'):
        return acties
    if fase_key == 'transitie':
        return ['Losse, vrije beweging — geen structuur, geen intensiteit.',
                'Gebruik deze week om klachten en vermoeidheid te laten zakken.']

    for st in _sport_prioriteit(statussen):
        sport, niveau, spw = st['sport'], st['niveau'], st['sessies_per_week']
        techniek = sport in TECHNIEKSPORTEN
        doel = (FOCUS_DREMPELS['doelsessies_techniek'] if techniek
                else FOCUS_DREMPELS['doelsessies_duur'])

        if sport in gaps_sporten:
            if is_basis and cyclus_index == 0:
                acties.append(f'{sport}: heropstarten na een lange onderbreking — eerste 2 weken '
                              f'kort en laag intensief, daarna pas volume erbij.')
            continue

        if niveau in ('ontbreekt', 'zeer_laag'):
            if is_basis:
                # Bouw de frequentie stap voor stap op over de cycli heen. Het vertrekpunt
                # noemen we alleen in de allereerste cyclus; daarna is dat achterhaald.
                stap = min(doel, max(1, round(spw) + 1 + cyclus_index))
                huidig = f'{spw:.1f}'.replace('.', ',')
                vanaf = f' (nu {huidig}x)' if cyclus_index == 0 else ''
                if techniek:
                    acties.append(f'{sport}: naar {stap}x per week{vanaf}, met elke sessie '
                                  f'techniekwerk (korte series, veel rust) — frequentie gaat hier '
                                  f'vóór volume.')
                else:
                    acties.append(f'{sport}: naar {stap}x per week{vanaf}, rustige duurunits '
                                  f'om de belastbaarheid op te bouwen (+5-10% volume per week).')
            elif is_opbouw:
                acties.append(f'{sport}: frequentie vasthouden en nu wedstrijdspecifieke prikkels '
                              f'toevoegen — techniek blijft aandachtspunt onder vermoeidheid.'
                              if techniek else
                              f'{sport}: opgebouwde frequentie vasthouden en er drempelwerk in leggen.')
        elif niveau == 'laag':
            if is_basis:
                acties.append(f'{sport}: naar {doel}x per week en het aandeel in de weekbelasting '
                              f'verhogen met langere duurunits.')
            elif is_opbouw:
                acties.append(f'{sport}: wedstrijdspecifieke intensiteit (drempel), volume houden.')
        elif niveau == 'ok' and st['aandeel'] < FOCUS_DREMPELS['aandeel_laag'] and is_basis:
            acties.append(f'{sport}: frequentie is in orde, maar het aandeel in de weekbelasting is '
                          f'klein — verleng de duursessies in plaats van er sessies bij te steken.')

    if fase_key == 'piek':
        wedstrijd = discipline.lower() if discipline else 'de wedstrijd'
        acties.append(f'Hoogste weekbelasting van de cyclus — plan hier de wedstrijdsimulatie voor '
                      f'{wedstrijd} (tempo en voeding zoals op wedstrijddag).')
        acties.append('Na deze week gaat het volume omlaag: de taper zet deze belasting om in vorm.')

    # Disciplines die er goed voor staan verdienen ook een regel, anders lijkt het alsof er
    # met de rest van de week niets moet gebeuren.
    op_niveau = [s['sport'] for s in statussen
                 if s['niveau'] == 'ok' and s['aandeel'] >= FOCUS_DREMPELS['aandeel_laag']]
    if op_niveau and (is_basis or is_opbouw) and is_eerste_van_blok:
        namen = ' en '.join(op_niveau) if len(op_niveau) < 3 else \
            ', '.join(op_niveau[:-1]) + ' en ' + op_niveau[-1]
        acties.append(f'{namen}: op niveau — huidige frequentie aanhouden, hier geen extra '
                      f'volume bij zolang de achterstand elders wordt weggewerkt.')

    if is_opbouw and not acties:
        acties.append('Wedstrijdspecifieke intensiteit centraal; volume vasthouden.')
    if is_basis and not acties:
        acties.append('Aerobe basis verder uitbouwen — volume geleidelijk op (+5-10% per week), '
                      'intensiteit laag houden.')

    if is_laatste and is_basis:
        acties.append('Laatste cyclus van dit blok: consolideer wat staat in plaats van er nog bij '
                      'te leggen.')
    return acties


def _distribute(total_weeks, weights, min_each=1):
    """Verdeelt total_weeks (int) over len(weights) sub-fasen volgens de gewichten, elk minstens
    min_each weken. Geeft None terug als er niet genoeg weken zijn om op te splitsen."""
    n = len(weights)
    if total_weeks < n * min_each:
        return None
    raw = [total_weeks * w / sum(weights) for w in weights]
    weeks = [max(min_each, round(x)) for x in raw]
    diff = total_weeks - sum(weeks)
    weeks[weeks.index(max(weeks))] += diff
    return weeks


def _basis_blocks(weeks):
    if weeks <= 0:
        return []
    if weeks >= 6:
        split = _distribute(weeks, [0.4, 0.3, 0.3], min_each=2) or [weeks]
        keys = ['basis1', 'basis2', 'basis3'][:len(split)]
    elif weeks >= 3:
        split = _distribute(weeks, [0.6, 0.4], min_each=1) or [weeks]
        keys = ['basis1', 'basis2'][:len(split)]
    else:
        split, keys = [weeks], ['basis1']
    return list(zip(keys, split))


def _opbouw_blocks(weeks):
    if weeks <= 0:
        return []
    if weeks >= 4:
        split = _distribute(weeks, [0.5, 0.5], min_each=2) or [weeks]
        keys = ['opbouw1', 'opbouw2'][:len(split)]
    elif weeks >= 2:
        split, keys = [1, weeks - 1], ['opbouw1', 'opbouw2']
    else:
        split, keys = [weeks], ['opbouw1']
    return list(zip(keys, split))


def _split_3_1(n_weeks):
    """Verdeelt n_weken in cycli van 3 opbouwweken + 1 hersteldweek (Friel's 3:1-ritme). Een niet-volledige
    laatste cyclus (rest van 1-3 weken) blijft opbouw — je forceert nooit een geïsoleerde hersteldweek op
    het einde van een blok als er geen volledige cyclus meer past."""
    cycles = []
    remaining = n_weeks
    while remaining >= 4:
        cycles.append(('opbouw', 3))
        cycles.append(('herstel', 1))
        remaining -= 4
    if remaining > 0:
        cycles.append(('opbouw', remaining))
    return cycles


def _cycli_van_blok(block_start, wks, fase_key, statussen, gaps_sporten, discipline,
                     cyclus_offset=0):
    """Splitst een blok in cycli van 4 weken (3 opbouw + 1 herstel) en hangt aan elke cyclus
    de concrete actiepunten. De bloklengte volgt uit de tijd tot het doel, niet uit het ritme;
    een rest van 1-3 weken blijft dus opbouw in plaats van een losse hersteldweek te forceren."""
    # Taper, wedstrijdweek en transitie kennen geen 3:1-ritme — dat zijn afgebakende weken
    # met een eigen doel. Ze worden als één geheel getoond, zonder cyclus-taal.
    if fase_key in ('taper_afbouw', 'wedstrijdweek', 'transitie') or wks < 4:
        return [{
            'nr': 1, 'start': block_start,
            'einde': block_start + pd.Timedelta(weeks=wks) - pd.Timedelta(days=1),
            'weken': wks, 'week_van': 1, 'week_tot': wks, 'ritme': None, 'herstelweek': False,
            'acties': _acties_voor_blok(fase_key, statussen, gaps_sporten, discipline,
                                         cyclus_offset, False, True),
        }]

    ritme = _split_3_1(wks)

    # Groepeer het ritme terug tot cycli van (opbouw + eventueel herstel).
    groepen, huidig = [], None
    for soort, n in ritme:
        if soort == 'opbouw':
            if huidig:
                groepen.append(huidig)
            huidig = {'opbouw': n, 'herstel': 0}
        elif huidig:
            huidig['herstel'] += n
    if huidig:
        groepen.append(huidig)

    cycli = []
    week_cursor = block_start
    week_nr = 1
    for i, g in enumerate(groepen):
        totaal = g['opbouw'] + g['herstel']
        start = week_cursor
        einde = week_cursor + pd.Timedelta(weeks=totaal) - pd.Timedelta(days=1)
        ritme_tekst = (f"{g['opbouw']} opbouwweken + {g['herstel']} hersteldweek (~-30% volume)"
                       if g['herstel'] else
                       f"{g['opbouw']} opbouwweek{'en' if g['opbouw'] > 1 else ''} (geen volledige "
                       f"cyclus meer tot het einde van dit blok)")
        cycli.append({
            'nr': i + 1,
            'start': start,
            'einde': einde,
            'weken': totaal,
            'week_van': week_nr,
            'week_tot': week_nr + totaal - 1,
            'ritme': ritme_tekst,
            'herstelweek': g['herstel'] > 0,
            'acties': _acties_voor_blok(fase_key, statussen, gaps_sporten, discipline,
                                         cyclus_offset + i,
                                         i == len(groepen) - 1 and len(groepen) > 1,
                                         is_eerste_van_blok=(i == 0)),
        })
        week_cursor = einde + pd.Timedelta(days=1)
        week_nr += totaal
    return cycli


def _startaanpassing(acwr_current):
    """Past het beginpunt van de EERSTE macrocyclus aan op basis van de huidige belastbaarheid."""
    if acwr_current is None:
        return None
    if acwr_current > 1.3:
        return {'type': 'te_hoog'}
    if acwr_current < 0.8:
        return {'type': 'te_laag'}
    return None


def _plan_segment(start, race_monday, is_first_segment, startaanpassing, goal_name,
                   profiel=None, gaps_sporten=(), discipline=''):
    """Bouwt de macro/mesocyclus-structuur voor 1 A-doel, terugwerkend vanaf de wedstrijdweek."""
    profiel = profiel or {}
    vereiste_sporten = DISCIPLINE_SPORTEN.get(discipline, [])
    statussen = [_sport_status(profiel, s) for s in vereiste_sporten]
    n_weken = ((race_monday - start).days // 7) + 1
    if n_weken <= 0:
        return [], ('Dit doel valt te dicht op het vorige (binnen de hersteltijd) — er is geen ruimte '
                     'voor een aparte opbouw. Overweeg de doeldata verder uit elkaar te leggen.')

    warning = None
    if n_weken < 4:
        warning = (f'Slechts {n_weken} week(en) tot dit doel — te weinig tijd voor een echte opbouw. '
                    'Enkel een (verkorte) taper wordt voorgesteld.')

    taper_weeks = min(2, n_weken)
    remaining = n_weken - taper_weeks

    transitie_weeks = 0
    if not is_first_segment and remaining >= 3:
        transitie_weeks = 1
        remaining -= 1

    stabilisatie_note = None
    extra_basis = 0
    if is_first_segment and startaanpassing and remaining > 0:
        if startaanpassing['type'] == 'te_hoog' and remaining >= 3:
            transitie_weeks = max(transitie_weeks, 1)
            remaining -= 1
            stabilisatie_note = ('Extra stabilisatieweek ingelast: de huidige belastbaarheid staat boven '
                                  'de sweet spot, dus eerst afbouwen/stabiliseren voor de opbouw start.')
        elif startaanpassing['type'] == 'te_laag':
            extra_basis = 1
            stabilisatie_note = ('Basis 1 is een week langer voorzien: de recente belasting stond onder '
                                  'de sweet spot, dus extra tijd om de aerobe basis terug op te bouwen.')

    piek_weeks = 1 if remaining >= 6 else 0
    remaining -= piek_weeks

    opbouw_weeks = 0
    if remaining >= 2:
        opbouw_weeks = min(max(1, round(remaining * 0.35)), remaining)
    # Alleen als er ook echt een week van Opbouw naar Basis verschuift, klopt de stabilisatie-notitie
    # verderop nog met het gegenereerde schema — bij een kort blok (opbouw_weeks <= 1) gebeurt die
    # verschuiving niet, en mag de notitie dan ook niet getoond worden.
    basis_extended = bool(extra_basis and opbouw_weeks > 1)
    if basis_extended:
        # verschuif 1 week van Opbouw naar Basis i.p.v. het totaal aantal weken op te rekken
        # (de wedstrijddatum/taper ligt vast) — de extra basisweek komt dus uit het opbouwblok.
        opbouw_weeks -= 1
    basis_weeks = remaining - opbouw_weeks

    blocks = []
    if transitie_weeks:
        blocks.append(('transitie', transitie_weeks))
    blocks += _basis_blocks(basis_weeks)
    blocks += _opbouw_blocks(opbouw_weeks)
    if piek_weeks:
        blocks.append(('piek', piek_weeks))
    if taper_weeks == 2:
        blocks.append(('taper_afbouw', 1))
        blocks.append(('wedstrijdweek', 1))
    elif taper_weeks == 1:
        blocks.append(('wedstrijdweek', 1))

    out = []
    cursor = start
    basis_note_used = False
    cyclus_teller = {}
    for key, wks in blocks:
        if wks <= 0:
            continue
        block_start = cursor
        block_end = cursor + pd.Timedelta(weeks=wks) - pd.Timedelta(days=1)
        info = FASE_INFO[key]
        note = None
        if key == 'transitie' and stabilisatie_note and transitie_weeks and not extra_basis:
            note = stabilisatie_note
        if key == 'basis1' and stabilisatie_note and basis_extended and not basis_note_used:
            note = stabilisatie_note
            basis_note_used = True
        # De opbouwteller loopt door binnen een fasefamilie (alle basisblokken samen, alle
        # opbouwblokken samen), zodat Basis 2 verdergaat waar Basis 1 eindigde.
        familie = 'basis' if key.startswith('basis') else ('opbouw' if key.startswith('opbouw') else key)
        cycli = _cycli_van_blok(block_start, wks, key, statussen, gaps_sporten, discipline,
                                 cyclus_offset=cyclus_teller.get(familie, 0))
        cyclus_teller[familie] = cyclus_teller.get(familie, 0) + len(cycli)
        out.append({
            'fase_key': key, 'fase': info['naam'], 'start': block_start, 'einde': block_end,
            'weken': wks, 'focus': info['focus'], 'volume': info['volume'],
            'volume_pct': info.get('volume_pct'), 'intensiteit': info['intensiteit'],
            'notitie': note, 'doel': goal_name, 'cycli': cycli,
        })
        cursor = block_end + pd.Timedelta(days=1)

    return out, warning


def generate_jaarplanning(today: pd.Timestamp, a_goals: list, acwr_current,
                           profiel: dict = None, gaps: list = None) -> dict:
    """Bouwt een voorgestelde jaarplanning (macro/mesocyclus-structuur) voor max. 3 A-doelen,
    terugwerkend gepland vanaf elke wedstrijddatum, volgens Friel en Olbrecht (zie module-doc
    hierboven), aangepast aan de huidige belastbaarheid van de atleet.

    a_goals: lijst van dicts {'name': str, 'date': pd.Timestamp, 'discipline': str}
    profiel: sportprofiel uit sport_profiel() — bepaalt de concrete actiepunten per cyclus.
             Zonder profiel valt de planning terug op algemene focuspunten per fase.
    gaps:    blinde vlekken uit detect_gaps(), zodat een lang afwezige discipline voorzichtig
             heropgestart wordt in plaats van meteen op volume te gaan.

    Retourneert {'goals': [...], 'blocks': [...]} (blocks in chronologische volgorde, elk met
    een 'doel'-sleutel om te groeperen per A-doel en een 'cycli'-lijst van 4 weken).
    """
    goals = sorted([g for g in a_goals if g['date'] >= today], key=lambda g: g['date'])[:3]
    if not goals:
        return {'goals': [], 'blocks': []}

    monday = today - pd.Timedelta(days=today.weekday())
    startaanpassing = _startaanpassing(acwr_current)
    gaps_sporten = {g['sport'] for g in (gaps or [])}

    all_blocks = []
    goal_summaries = []
    cursor = monday
    for i, g in enumerate(goals):
        race_monday = g['date'] - pd.Timedelta(days=g['date'].weekday())
        blocks, warning = _plan_segment(cursor, race_monday, i == 0,
                                         startaanpassing if i == 0 else None, g['name'],
                                         profiel=profiel, gaps_sporten=gaps_sporten,
                                         discipline=g.get('discipline', ''))
        all_blocks += blocks
        n_weken = max(0, ((race_monday - cursor).days // 7) + 1)
        goal_summaries.append({
            'name': g['name'], 'date': g['date'], 'discipline': g.get('discipline', ''),
            'weken_beschikbaar': n_weken, 'warning': warning,
        })
        cursor = race_monday + pd.Timedelta(weeks=2)

    return {'goals': goal_summaries, 'blocks': all_blocks}
