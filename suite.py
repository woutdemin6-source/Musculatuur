"""
De prestatietest-suite als Streamlit-component.

Apart module-bestand omdat Streamlit bij declare_component de aanroepende module opzoekt;
zo werkt de registratie altijd, ook wanneer app.py anders dan als bestand uitgevoerd wordt.
De suite zelf (HTML/JS, ongewijzigde rekenlogica) staat in components/prestatietest/index.html.
"""
import os

import streamlit.components.v1 as components

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'components', 'prestatietest')
component = components.declare_component('dm_prestatietest', path=_DIR)

# Bewerkbare weergave van verslagen (trajectverslag): rechtstreeks typen + bewaren.
_DIR_VERSLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'components', 'verslag')
verslag = components.declare_component('dm_verslag', path=_DIR_VERSLAG)
