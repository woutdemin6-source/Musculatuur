#!/usr/bin/env python3
"""
De Musculatuur — Workload & A:C ratio analyse-tool (v1, CLI)

Command-line versie. Voor de webversie: zie app.py (`streamlit run app.py`).
Beide gebruiken dezelfde reken-/parsing-logica uit core.py.

Gebruik:
    python analyze_athlete.py --export /pad/naar/export.zip --athlete "Naam" --output ./out

Vereisten: pandas, numpy, matplotlib  (pip install pandas numpy matplotlib --break-system-packages)
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import core


def make_chart(daily, acwr, today, athlete, outpath):
    start = today - pd.Timedelta(days=182)
    d_acwr = acwr[acwr.index >= start]
    weekload = daily.rolling(7).sum()
    w = weekload[weekload.index >= start]

    fig, ax1 = plt.subplots(figsize=(9, 4.2))
    ax1.bar(w.index, w.values, width=0.9, color='#c9d6e3', label='Wekelijkse trainingslast (7d som)')
    ax1.set_ylabel('Trainingslast (7-daagse som)', color='#4a6b8a')
    ax1.tick_params(axis='y', labelcolor='#4a6b8a')
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))

    ax2 = ax1.twinx()
    ax2.plot(d_acwr.index, d_acwr.values, color='#c0392b', linewidth=2, label='A:C ratio')
    ax2.axhspan(0.8, 1.3, color='#2ecc71', alpha=0.15)
    ax2.axhline(1.5, color='#c0392b', linestyle='--', linewidth=1, alpha=0.6)
    ax2.axhline(0.8, color='gray', linestyle=':', linewidth=1, alpha=0.6)
    ax2.set_ylabel('A:C ratio', color='#c0392b')
    ax2.tick_params(axis='y', labelcolor='#c0392b')
    ax2.set_ylim(0, max(1.8, float(np.nanmax(d_acwr.values)) * 1.15 if len(d_acwr) else 1.8))

    fig.suptitle(f'Belastbaarheid laatste 6 maanden — {athlete}')
    fig.tight_layout()
    plt.savefig(outpath, dpi=150)


def main():
    ap = argparse.ArgumentParser(description='De Musculatuur workload & A:C ratio analyse-tool')
    ap.add_argument('--export', required=True, help='Pad naar Strava export .zip')
    ap.add_argument('--athlete', required=True, help='Naam van de atleet (voor rapport)')
    ap.add_argument('--output', default='./out', help='Output-map voor summary.json en acwr_chart.png')
    ap.add_argument('--today', default=None, help='Referentiedatum YYYY-MM-DD (default: vandaag)')
    args = ap.parse_args()

    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)
    export_path = Path(args.export)
    if not export_path.exists():
        raise SystemExit(f'Fout: bestand niet gevonden: {export_path}')

    today = pd.Timestamp(args.today) if args.today else pd.Timestamp.now().normalize()

    try:
        df = core.load_export_from_path(export_path, outdir)
    except ValueError as e:
        raise SystemExit(f'Fout: {e}')

    summary, daily, acute, chronic, acwr = core.build_summary(df, args.athlete, today)

    with open(outdir / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    make_chart(daily, acwr, today, args.athlete, outdir / 'acwr_chart.png')

    print(f'Klaar. Output geschreven naar: {outdir}/summary.json en {outdir}/acwr_chart.png')
    print(f"Sessies: {summary['totalSessionsAllTime']} totaal | huidige A:C ratio: {summary['acwr']['current']}")
    if summary['gaps']:
        print('Mogelijke blinde vlekken (sport historisch actief, recent afwezig):')
        for g in summary['gaps']:
            print(f"  - {g['sport']}: laatst actief {g['laatste_sessie']} ({g['dagen_geleden']} dagen geleden)")


if __name__ == '__main__':
    main()
