"""
De Musculatuur — opslag van atleetprofielen (Supabase).

Streamlit Cloud bewaart zelf niets tussen herstarts, dus alles wat een coach invoert
(intake, analyses, A-doelen, testdocumenten) gaat naar een Postgres-database bij Supabase
(regio Frankfurt). Twee tabellen volstaan:

  atleten   — één rij per atleet: basisgegevens + intake
  records   — alles wat bij een atleet hoort, als JSON: belastbaarheidsanalyses,
              jaarplanning (A-doelen), prestatietest-/voedingsdocumenten uit de suite

De verbinding leest SUPABASE_URL en SUPABASE_KEY uit st.secrets (Streamlit Cloud → Settings →
Secrets, lokaal .streamlit/secrets.toml — dat bestand staat in .gitignore). Ontbreken die,
dan draait de app gewoon zonder opslag en zegt dat ook duidelijk; niets crasht.

Beveiliging, eerlijk benoemd: de app heeft één gedeeld wachtwoord, geen individuele accounts.
De databasesleutel blijft server-side in secrets en komt nooit in de browser, maar wie de
sleutel heeft, heeft de data. Dit zijn persoonsgegevens (naam, geboortedatum, trainings- en
testdata) — behandel de secrets als vertrouwelijk en gebruik een sterk app-wachtwoord.
"""
import json
import math
import unicodedata
from datetime import datetime, timezone, date

import streamlit as st

SOORTEN = {
    'intake': 'Intakeverslag',
    'belastbaarheid': 'Belastbaarheidsanalyse',
    'jaarplanning': 'Jaarplanning',
    'prestatietest': 'Prestatietest',
    'voeding': 'Voedingsplan',
    'document': 'Document',
}


# Wat er misgaat bij kopiëren/plakken van een sleutel: krulquotes, spaties, onzichtbare tekens,
# fullwidth of "vette" Unicode-letters. Wat te herstellen valt, herstellen we stil; de rest
# melden we leesbaar, want de ruwe fout ('ascii' codec can't encode …) zegt een coach niets.
_AANHALINGSTEKENS = '"\'“”‘’„‟«»`'
_ONZICHTBAAR = dict.fromkeys(map(ord, '​‌‍⁠﻿ '), None)


def _normaliseer(waarde):
    if waarde is None:
        return None
    s = unicodedata.normalize('NFKC', str(waarde)).translate(_ONZICHTBAAR)
    s = s.strip().strip(_AANHALINGSTEKENS).strip()
    return s or None


def _secrets():
    try:
        url, key = st.secrets.get('SUPABASE_URL'), st.secrets.get('SUPABASE_KEY')
    except Exception:
        return None, None
    return _normaliseer(url), _normaliseer(key)


def _probleem(url, key):
    """Leesbare uitleg als de secrets niet bruikbaar zijn, anders None."""
    for naam, waarde in (('SUPABASE_URL', url), ('SUPABASE_KEY', key)):
        if not waarde:
            continue
        vreemd = []
        for c in waarde:
            if not (32 < ord(c) < 127) and c not in vreemd:
                vreemd.append(c)
        if vreemd:
            voorbeeld = ', '.join(f"'{c}' ({unicodedata.name(c, 'onbekend').lower()})"
                                  for c in vreemd[:3])
            return (f'{naam} bevat tekens die niet in een sleutel horen: {voorbeeld}. '
                    f'Plak de waarde opnieuw als platte tekst (Settings → Secrets), '
                    f'zonder opmaak, en let op dat je de echte sleutel kopieert en niet een '
                    f'afgeschermde weergave met puntjes.')
    if url and not url.startswith('https://'):
        return 'SUPABASE_URL moet beginnen met https:// — plak de Project URL uit Supabase.'
    if key and key.count('.') != 2 and not key.startswith('sb_'):
        return ('SUPABASE_KEY lijkt onvolledig — plak de volledige anon-sleutel '
                '(begint met "eyJ" en bevat twee punten).')
    return None


def beschikbaar() -> bool:
    url, key = _secrets()
    return bool(url and key)


@st.cache_resource(show_spinner=False)
def _client():
    from supabase import create_client
    url, key = _secrets()
    fout = _probleem(url, key)
    if fout:
        raise ValueError(fout)
    return create_client(url, key)


def _nu() -> str:
    return datetime.now(timezone.utc).isoformat()


def _schoon(obj):
    """NaN → None, recursief. json.dumps schrijft NaN als het token `NaN`, en dat is geen
    geldige JSON — Postgres weigert de rij dan. Analyses bevatten NaN's (bv. A:C ratio op
    dagen zonder chronische last), dus dit moet vóór het serialiseren gebeuren."""
    if isinstance(obj, dict):
        return {k: _schoon(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_schoon(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if hasattr(obj, 'item') and not isinstance(obj, (str, bytes)):
        try:
            v = obj.item()
            return None if isinstance(v, float) and math.isnan(v) else v
        except Exception:
            return obj
    return obj


def _json_veilig(obj):
    """Maakt een object JSON-serialiseerbaar: NaN's, pandas/numpy-types, datums en
    Timestamps worden omgezet. De rest gaat ongewijzigd door."""
    return json.loads(json.dumps(_schoon(obj), default=_default, ensure_ascii=False))


def _default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if hasattr(o, 'isoformat'):          # pandas Timestamp
        return o.isoformat()
    if hasattr(o, 'item'):               # numpy scalars
        return o.item()
    if hasattr(o, 'tolist'):             # numpy arrays / pandas Series
        return o.tolist()
    return str(o)


# --- Atleten ---------------------------------------------------------------

ATLEET_VELDEN = ('naam', 'geboortedatum', 'sport', 'doelen', 'contact', 'intake')


def lijst_atleten() -> list:
    res = (_client().table('atleten')
           .select('id, naam, geboortedatum, sport, doelen, bijgewerkt_op')
           .order('naam').execute())
    return res.data or []


def haal_atleet(atleet_id: str):
    res = _client().table('atleten').select('*').eq('id', atleet_id).limit(1).execute()
    return res.data[0] if res.data else None


def zoek_atleet_op_naam(naam: str):
    """Hoofdletterongevoelig, zodat een geïmporteerd document aan de juiste atleet hangt."""
    if not naam:
        return None
    res = _client().table('atleten').select('*').ilike('naam', naam.strip()).limit(1).execute()
    return res.data[0] if res.data else None


def bewaar_atleet(gegevens: dict, atleet_id: str = None) -> dict:
    rij = {k: gegevens.get(k) for k in ATLEET_VELDEN if k in gegevens}
    rij = _json_veilig(rij)
    rij['bijgewerkt_op'] = _nu()
    tabel = _client().table('atleten')
    if atleet_id:
        res = tabel.update(rij).eq('id', atleet_id).execute()
    else:
        res = tabel.insert(rij).execute()
    return res.data[0] if res.data else rij


def verwijder_atleet(atleet_id: str):
    # records verdwijnen mee via ON DELETE CASCADE
    _client().table('atleten').delete().eq('id', atleet_id).execute()


# --- Records ---------------------------------------------------------------

def bewaar_record(atleet_id: str, soort: str, titel: str, data: dict, record_id: str = None) -> dict:
    rij = {'atleet_id': atleet_id, 'soort': soort, 'titel': titel,
           'data': _json_veilig(data), 'bijgewerkt_op': _nu()}
    tabel = _client().table('records')
    if record_id:
        res = tabel.update(rij).eq('id', record_id).execute()
    else:
        res = tabel.insert(rij).execute()
    return res.data[0] if res.data else rij


def lijst_records(atleet_id: str, soort: str = None, met_data: bool = False) -> list:
    kolommen = '*' if met_data else 'id, atleet_id, soort, titel, aangemaakt_op, bijgewerkt_op'
    q = _client().table('records').select(kolommen).eq('atleet_id', atleet_id)
    if soort:
        q = q.eq('soort', soort)
    res = q.order('aangemaakt_op', desc=True).execute()
    return res.data or []


def haal_record(record_id: str):
    res = _client().table('records').select('*').eq('id', record_id).limit(1).execute()
    return res.data[0] if res.data else None


def laatste_record(atleet_id: str, soort: str):
    res = (_client().table('records').select('*')
           .eq('atleet_id', atleet_id).eq('soort', soort)
           .order('aangemaakt_op', desc=True).limit(1).execute())
    return res.data[0] if res.data else None


def verwijder_record(record_id: str):
    _client().table('records').delete().eq('id', record_id).execute()
