/*
 * De Musculatuur — Workload & A:C ratio rapportgenerator (v1)
 * Generiek: leest summary.json + acwr_chart.png uit een output-map
 * (gegenereerd door analyze_athlete.py) en bouwt een .docx rapport
 * voor EENDER WELKE atleet.
 *
 * Gebruik:
 *   node build_report.js --dir ./out
 *
 * Vereist: npm package "docx" (globaal beschikbaar via NODE_PATH)
 */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, BorderStyle, ImageRun, PageBreak,
  Footer, PageNumber, LevelFormat,
} = require('docx');

const args = process.argv.slice(2);
const dirIdx = args.indexOf('--dir');
const dir = dirIdx >= 0 ? args[dirIdx + 1] : './out';

const data = JSON.parse(fs.readFileSync(path.join(dir, 'summary.json'), 'utf8'));
const chartPath = path.join(dir, 'acwr_chart.png');

const NAVY = '1F3B57', BLUE = '2E5C8A', GRAY = '666666';
const TABLE_W = 9360;

function h1(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 160 } }); }
function h2(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 120 } }); }
function p(text, opts = {}) { return new Paragraph({ spacing: { after: 140 }, children: [new TextRun({ text, ...opts })] }); }
function bullet(text, opts = {}) { return new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text, ...opts })] }); }
function cell(text, { bold = false, width, shading, color, align, size } = {}) {
  return new TableCell({
    width: { size: width || 1500, type: WidthType.DXA },
    shading: shading ? { type: ShadingType.CLEAR, fill: shading } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ alignment: align || AlignmentType.LEFT, children: [new TextRun({ text: String(text), bold, color, size: size || 19 })] })],
  });
}
function makeTable(headers, rows, widths) {
  const headerRow = new TableRow({ tableHeader: true, children: headers.map((hText, i) => cell(hText, { bold: true, width: widths[i], shading: NAVY, color: 'FFFFFF' })) });
  const dataRows = rows.map((r, idx) => new TableRow({ children: r.map((val, i) => cell(val, { width: widths[i], shading: idx % 2 === 1 ? 'F2F5F8' : undefined })) }));
  return new Table({ width: { size: TABLE_W, type: WidthType.DXA }, columnWidths: widths, rows: [headerRow, ...dataRows] });
}
function fmt(n, d = 0) {
  if (n === null || n === undefined) return '-';
  return Number(n).toLocaleString('nl-BE', { minimumFractionDigits: d, maximumFractionDigits: d });
}

function periodSection(per, title) {
  const widths = [2400, 1000, 1300, 1300, 1300, 1200, 1360];
  const rows = per.bySport.map(s => [s.sport, String(s.sessies), fmt(s.uren, 1), fmt(s.km, 1), fmt(s.hm, 0), s.hr ? fmt(s.hr, 0) : '-', fmt(s.load, 0)]);
  rows.push(['TOTAAL', String(per.sessies), fmt(per.uren, 1), fmt(per.km, 1), fmt(per.hoogtemeters, 0), '-', fmt(per.load, 0)]);
  return [
    h2(title),
    p(per.label, { italics: true, color: GRAY, size: 19 }),
    makeTable(['Sport', 'Sessies', 'Uren', 'Km', 'Hoogtemeters', 'Gem. HS', 'Trainingslast'], rows, widths),
    new Paragraph({ spacing: { after: 200 } }),
  ];
}

function acwrTable() {
  const rows = data.acwr.table.filter(w => w.acwr !== null).map(w => {
    let zone = 'Sweet spot';
    if (w.acwr > 1.3) zone = 'Piekbelasting';
    else if (w.acwr < 0.8) zone = 'Onderbelasting';
    return [w.week_ending, fmt(w.acwr, 2), zone];
  });
  return makeTable(['Week (t/m)', 'A:C ratio', 'Zone'], rows, [3120, 3120, 3120]);
}

const numbering = { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 260 } } } }] }] };

const children = [];

// Title
children.push(
  new Paragraph({ spacing: { before: 800, after: 40 }, children: [new TextRun({ text: 'TRAININGSANALYSE', bold: true, size: 40, color: NAVY })] }),
  new Paragraph({ spacing: { after: 300 }, children: [new TextRun({ text: 'Activiteitenoverzicht & belastbaarheid (A:C ratio)', size: 26, color: BLUE })] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: `Sporter: ${data.athlete}`, size: 20 })] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: `Datum rapport: ${data.reportDate}`, size: 20 })] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: `Bron: Strava-export, ${data.totalSessionsAllTime} activiteiten (${data.dateRange.from} – ${data.dateRange.to})`, size: 20, color: GRAY })] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: 'Gegenereerd door De Musculatuur — workload & A:C ratio tool v1', size: 18, italics: true, color: GRAY })] }),
  new Paragraph({ border: { bottom: { color: NAVY, space: 8, style: BorderStyle.SINGLE, size: 12 } }, spacing: { after: 300 } }),
);

// Kernbevindingen (auto-generated)
children.push(h1('Kernbevindingen'));
const kb = [];
kb.push(`Huidige A:C ratio: ${fmt(data.acwr.current, 2)} — ${data.acwr.current >= 0.8 && data.acwr.current <= 1.3 ? 'binnen de veilige "sweet spot" (0,8-1,3)' : (data.acwr.current > 1.3 ? 'boven de sweet spot: mogelijk verhoogd risico bij aanhoudende piekbelasting' : 'onder de sweet spot: mogelijke onderbelasting/detraining')}.`);
kb.push(`Van de laatste ${data.acwr.weeks_total} weken zaten er ${data.acwr.weeks_green} in de sweet spot, ${data.acwr.weeks_high} met piekbelasting (>1,3) en ${data.acwr.weeks_low} met onderbelasting (<0,8).`);
kb.push(`Laatste 6 maanden: ${data.periods['6m'].sessies} sessies, ${fmt(data.periods['6m'].uren, 1)}u, ${fmt(data.periods['6m'].km, 0)}km.`);
if (data.gaps.length > 0) {
  data.gaps.forEach(g => kb.push(`Mogelijke blinde vlek: ${g.sport} komt historisch ${g.totaal_historisch}x voor maar is afwezig in de laatste 6 maanden (laatste sessie: ${g.laatste_sessie}, ${g.dagen_geleden} dagen geleden).`));
} else {
  kb.push('Geen disciplines gevonden die historisch actief waren maar recent volledig afwezig zijn.');
}
kb.forEach(t => children.push(bullet(t)));

// Overzicht
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(h1('Overzicht activiteiten & trainingen'));
children.push(p('"Trainingslast" is gebaseerd op Strava Relative Effort waar geregistreerd; voor sessies zonder deze waarde maar mét hartslagdata is een schatting gemaakt via een per-sporttype gekalibreerde ratio, afgeleid uit de eigen data van deze atleet (zie methodologie).', { size: 19, color: GRAY }));
children.push(...periodSection(data.periods['6m'], 'Laatste 6 maanden'));
children.push(...periodSection(data.periods['3m'], 'Laatste 3 maanden'));
children.push(...periodSection(data.periods['4w'], 'Laatste 4 weken'));

// ACWR
children.push(h1('Belastbaarheid: Acute:Chronic Workload Ratio (A:C ratio)'));
children.push(p('De A:C ratio vergelijkt de acute trainingslast (som van de laatste 7 dagen) met de chronische trainingslast (gemiddelde wekelijkse last over de laatste 28 dagen). Een ratio tussen 0,8 en 1,3 geldt doorgaans als "sweet spot." Let op: wetenschappelijk onderzoek toont dat de A:C ratio een signaal is, geen betrouwbare geïsoleerde voorspeller van overbelasting — gebruik ze altijd samen met herstelindicatoren en coach-inzicht (zie de literatuurstudie voor De Musculatuur, hoofdstuk 3).', {}));
if (fs.existsSync(chartPath)) {
  children.push(new Paragraph({
    children: [new ImageRun({ type: 'png', data: fs.readFileSync(chartPath), transformation: { width: 620, height: 289 } })],
    spacing: { after: 200 }, alignment: AlignmentType.CENTER,
  }));
}
children.push(h2('Wekelijkse A:C ratio — laatste 16 weken'));
children.push(acwrTable());
children.push(new Paragraph({ spacing: { after: 200 } }));
children.push(p(`Huidige status: acute belasting (7d) = ${fmt(data.acwr.acute7d, 0)}, chronische belasting (gem./week over 28d) = ${fmt(data.acwr.chronic28d_weekly_avg, 0)} → A:C ratio = ${fmt(data.acwr.current, 2)}.`, {}));

// Methodologie
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(h1('Bijlage: methodologie & datakwaliteit'));
children.push(bullet(`Databron: Strava-export, ${data.totalSessionsAllTime} activiteiten, periode ${data.dateRange.from} – ${data.dateRange.to}.`));
children.push(bullet(`Trainingslast: ${data.dataQuality.actual} sessies met geregistreerde waarde ("actual"), ${data.dataQuality.estimated} sessies geschat op basis van hartslag × duur (per-sporttype gekalibreerd op de eigen data), ${data.dataQuality.excluded_no_hr} sessies uitgesloten wegens ontbrekende hartslagdata.`));
children.push(bullet('A:C ratio: acute last = som trainingslast laatste 7 dagen; chronische last = gemiddelde wekelijkse trainingslast over de laatste 28 dagen (rolling window, dagelijks bijgewerkt).'));
children.push(bullet('Dit rapport is automatisch gegenereerd en vervangt geen klinisch of coach-oordeel. Zie de literatuurstudie "Wetenschappelijke fundamenten voor een AI-analyseplatform bij De Musculatuur" voor de volledige evidence-basis en beperkingen van deze metrieken.'));

const doc = new Document({
  numbering,
  styles: {
    default: { document: { run: { font: 'Calibri', size: 21 } } },
    heading1: { run: { color: NAVY, size: 30, bold: true }, paragraph: { spacing: { before: 300, after: 160 } } },
    heading2: { run: { color: BLUE, size: 24, bold: true }, paragraph: { spacing: { before: 220, after: 100 } } },
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1000, bottom: 1000, left: 1100, right: 1100 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 17, color: GRAY })] })] }) },
    children,
  }],
});

const outFile = path.join(dir, `Trainingsanalyse_${data.athlete.replace(/\s+/g, '_')}.docx`);
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outFile, buf);
  console.log('Rapport geschreven naar:', outFile);
});
