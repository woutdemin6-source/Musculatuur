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
        if pd.notna(row['Gemiddelde hartslag']) and pd.notna(row['Beweegtijd']) and row['Beweegtijd'] > 0 and blended is not None:
            r = ratios.get(row['Activiteitstype'], blended)
            return r * row['Gemiddelde hartslag'] * row['Beweegtijd'] / 60.0, 'estimated'
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
    acwr = acute / chronic.replace(0, np.nan)
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


def build_summary(df: pd.DataFrame, athlete: str, today: pd.Timestamp) -> dict:
    """Bouwt het volledige summary-dict (zelfde vorm als summary.json van de CLI-tool)."""
    df = estimate_load(df)
    daily, acute, chronic, acwr = compute_acwr(df, today)
    current_acwr = float(acwr.iloc[-1]) if not np.isnan(acwr.iloc[-1]) else None

    weekly_dates = pd.date_range(end=today, periods=16, freq='W')
    acwr_table = []
    for d in weekly_dates:
        v = acwr.asof(d)
        acwr_table.append({'week_ending': d.strftime('%d %b'), 'acwr': None if pd.isna(v) else round(float(v), 1)})
    valid_vals = [w['acwr'] for w in acwr_table if w['acwr'] is not None]
    weeks_green = sum(1 for v in valid_vals if 0.8 <= v <= 1.3)
    weeks_high = sum(1 for v in valid_vals if v > 1.3)
    weeks_low = sum(1 for v in valid_vals if v < 0.8)

    n_actual = int((df['load_source'] == 'actual').sum())
    n_estimated = int((df['load_source'] == 'estimated').sum())
    n_missing = int((df['load_source'] == 'missing').sum())

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
        'dataQuality': {'actual': n_actual, 'estimated': n_estimated, 'excluded_no_hr': n_missing},
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
        'volume': 'laag (~40-50%)', 'intensiteit': 'laag',
    },
    'basis1': {
        'naam': 'Basis 1',
        'focus': 'Aerobe basis opbouwen: duurcapaciteit, algemene kracht en bewegingstechniek, '
                 'vrijwel uitsluitend lage intensiteit. Dit legt de aerobe fundering (o.a. '
                 'mitochondriale en capillaire aanpassingen) waar de rest van het seizoen op '
                 'steunt — deze aanpassingen hebben tijd nodig en worden daarom als eerste en '
                 'langst opgebouwd (Olbrecht).',
        'volume': 'opbouwend (~60-80%)', 'intensiteit': 'laag',
    },
    'basis2': {
        'naam': 'Basis 2',
        'focus': 'Verdere opbouw van de aerobe capaciteit, kracht wordt sport-specifieker. Eerste, '
                 'beperkte impulsen net onder de drempel — de nadruk blijft op het aerobe systeem.',
        'volume': 'opbouwend (~75-90%)', 'intensiteit': 'laag tot gematigd',
    },
    'basis3': {
        'naam': 'Basis 3',
        'focus': 'Spieruithouding en aerobe power verder uitbouwen richting het volumepiek van het '
                 'seizoen. Aerobe capaciteit blijft prioriteit — anaerobe systemen worden bewust '
                 'nog niet gericht aangesproken (Olbrecht).',
        'volume': 'piek van de basisperiode (~90-100%)', 'intensiteit': 'gematigd',
    },
    'opbouw1': {
        'naam': 'Opbouw 1',
        'focus': 'Overgang naar wedstrijdspecifieke intensiteit: tempo- en drempelwerk wint aan '
                 'belang, volume daalt licht terwijl de intensiteit stijgt (Friel).',
        'volume': 'lichte daling (~80-90%)', 'intensiteit': 'gematigd tot hoog',
    },
    'opbouw2': {
        'naam': 'Opbouw 2',
        'focus': 'Wedstrijdspecifieke intensiteit staat centraal: drempel- en (waar relevant) '
                 'anaerobe capaciteit worden nu pas gericht getraind — bewust laat in het seizoen '
                 'en gebouwd op de al aanwezige aerobe basis (Olbrecht), niet ervoor in de plaats.',
        'volume': 'verder dalend (~70-85%)', 'intensiteit': 'hoog',
    },
    'piek': {
        'naam': 'Piek',
        'focus': 'Kort blok net voor de taper: laag volume, scherpe wedstrijdspecifieke prikkels. '
                 'Doel is scherpte behouden, niet nog meer belasting opbouwen.',
        'volume': 'laag (~60-70%)', 'intensiteit': 'hoog (kort en scherp)',
    },
    'taper_afbouw': {
        'naam': 'Taper — afbouwweek',
        'focus': 'Eerste taperweek: het volume gaat fors naar beneden, de intensiteit blijft '
                 'aanwezig zodat de scherpte behouden blijft.',
        'volume': '60% van het recente trainingsvolume', 'intensiteit': 'behouden',
    },
    'wedstrijdweek': {
        'naam': 'Wedstrijdweek',
        'focus': 'Laatste week voor het A-doel: minimale belasting, enkel korte activerende '
                 'prikkels. Intensiteit blijft behouden, volume is minimaal.',
        'volume': '40% van het recente trainingsvolume', 'intensiteit': 'behouden',
    },
}


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


def _beschrijf_3_1(wks):
    """Zet het 3:1-ritme binnen 1 blok om naar een expliciete week-per-week beschrijving, zodat je
    precies ziet waar de hersteldweek(en) vallen — ook als de bloklengte geen veelvoud van 4 is
    (de bloklengte zelf wordt bepaald door de beschikbare tijd tot het doel, niet door het 3:1-ritme;
    dat ritme loopt er als sub-structuur doorheen, met een kortere opbouwstaart als het niet perfect uitkomt)."""
    cycles = _split_3_1(wks)
    parts = []
    week = 1
    for kind, n in cycles:
        end = week + n - 1
        label = 'opbouw' if kind == 'opbouw' else 'hersteld (~-30% volume)'
        rng = f'week {week}' if n == 1 else f'week {week}-{end}'
        parts.append(f'{rng}: {label}')
        week = end + 1
    return f"3:1-ritme binnen dit blok ({wks} weken) — " + ', '.join(parts) + '.'


def _startaanpassing(acwr_current):
    """Past het beginpunt van de EERSTE macrocyclus aan op basis van de huidige belastbaarheid."""
    if acwr_current is None:
        return None
    if acwr_current > 1.3:
        return {'type': 'te_hoog'}
    if acwr_current < 0.8:
        return {'type': 'te_laag'}
    return None


def _plan_segment(start, race_monday, is_first_segment, startaanpassing, goal_name):
    """Bouwt de macro/mesocyclus-structuur voor 1 A-doel, terugwerkend vanaf de wedstrijdweek."""
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
    if extra_basis and opbouw_weeks > 1:
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
    for key, wks in blocks:
        if wks <= 0:
            continue
        block_start = cursor
        block_end = cursor + pd.Timedelta(weeks=wks) - pd.Timedelta(days=1)
        info = FASE_INFO[key]
        note = None
        if key == 'transitie' and stabilisatie_note and transitie_weeks and not extra_basis:
            note = stabilisatie_note
        if key == 'basis1' and stabilisatie_note and extra_basis and not basis_note_used:
            note = stabilisatie_note
            basis_note_used = True
        if wks >= 4 and key not in ('taper_afbouw', 'wedstrijdweek', 'transitie'):
            loading_note = _beschrijf_3_1(wks)
            note = f'{note} {loading_note}' if note else loading_note
        out.append({
            'fase_key': key, 'fase': info['naam'], 'start': block_start, 'einde': block_end,
            'weken': wks, 'focus': info['focus'], 'volume': info['volume'], 'intensiteit': info['intensiteit'],
            'notitie': note, 'doel': goal_name,
        })
        cursor = block_end + pd.Timedelta(days=1)

    return out, warning


def generate_jaarplanning(today: pd.Timestamp, a_goals: list, acwr_current) -> dict:
    """Bouwt een voorgestelde jaarplanning (macro/mesocyclus-structuur) voor max. 3 A-doelen,
    terugwerkend gepland vanaf elke wedstrijddatum, volgens Friel en Olbrecht (zie module-doc
    hierboven), aangepast aan de huidige belastbaarheid van de atleet.

    a_goals: lijst van dicts {'name': str, 'date': pd.Timestamp, 'discipline': str}
    Retourneert {'goals': [...], 'blocks': [...]} (blocks in chronologische volgorde, elk met
    een 'doel'-sleutel om te groeperen per A-doel).
    """
    goals = sorted([g for g in a_goals if g['date'] >= today], key=lambda g: g['date'])[:3]
    if not goals:
        return {'goals': [], 'blocks': []}

    monday = today - pd.Timedelta(days=today.weekday())
    startaanpassing = _startaanpassing(acwr_current)

    all_blocks = []
    goal_summaries = []
    cursor = monday
    for i, g in enumerate(goals):
        race_monday = g['date'] - pd.Timedelta(days=g['date'].weekday())
        blocks, warning = _plan_segment(cursor, race_monday, i == 0,
                                         startaanpassing if i == 0 else None, g['name'])
        all_blocks += blocks
        n_weken = max(0, ((race_monday - cursor).days // 7) + 1)
        goal_summaries.append({
            'name': g['name'], 'date': g['date'], 'discipline': g.get('discipline', ''),
            'weken_beschikbaar': n_weken, 'warning': warning,
        })
        cursor = race_monday + pd.Timedelta(weeks=2)

    return {'goals': goal_summaries, 'blocks': all_blocks}
