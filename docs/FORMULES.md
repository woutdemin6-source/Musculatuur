# Formules & gedachtegang — Prestatietest-suite

Dit document beschrijft élke berekening in de tool, met de redenering en bronnen erachter,
zodat het gedrag exact reproduceerbaar is bij integratie in een groter project.

Interne conventie: de intensiteit heet overal `v`. Voor **lopen** is `v` de snelheid in
km/u (afgeleid uit afstand + tijd) en wordt ze weergegeven als tempo (min/km). Voor
**fietsen** is `v` het vermogen in watt. Alle drempel-, curve- en zonewiskunde werkt op `v`
en is dus eenheden-onafhankelijk.

---

## 1. Lactaattest

### 1.1 Invoer → intensiteit
- **Lopen:** per trap afstand `d` (m) en tijd `t` (s). Snelheid `v = (d/1000) / (t/3600)` km/u.
  Weergave als tempo: `pace(v) = 3600 / v` seconden per km → mm:ss.
- **Fietsen:** per trap vermogen `v` (watt) rechtstreeks; tijd/trapduur wordt geregistreerd
  (bv. 5-min-protocol) maar beïnvloedt de analyse niet.
- Elk meetpunt heeft verder hartslag (bpm) en lactaat (mmol/l). Punten worden gesorteerd op `v`.

### 1.2 Curve-fit
Zowel de lactaat- als de hartslagcurve worden gemodelleerd als een **3e-graads polynoom**
via kleinste-kwadraten (`polyfit`, normaalvergelijkingen + Gauss-eliminatie). De curve wordt
met 120 tussenpunten glad getekend tussen de laagste en hoogste gemeten `v`. De 4 zone-
kleuren onder de curve (achtergrondbanden) en de curve zelf worden gesplitst op LT1 en LT2:
groen < LT1, geel tussen LT1–LT2, rood > LT2.

Hulpfuncties:
- `polyval(co, x)` — evalueert de polynoom.
- `interpY(xs, ys, x)` — lineaire interpolatie (voor HF bij een gegeven `v`).
- `speedAtLactate(pts, target)` — zoekt op het stijgende deel de `v` waar lactaat = `target`
  via lineaire interpolatie tussen de omliggende punten.
- `baseline(pts)` = laagste gemeten lactaatwaarde.

### 1.3 Aerobe drempel (LT1) — methodes
Elke methode geeft een `v`; de coach kiest de meest geschikte (chips of slepen op de grafiek).
- **Baseline** = `speedAtLactate(baseline + 0,2)`
- **Baseline + 0,4** = `speedAtLactate(baseline + 0,4)`
- **Baseline + 0,5** = `speedAtLactate(baseline + 0,5)`
- **2 mmol** = `speedAtLactate(2,0)` (vaste drempelwaarde)
- **Lactate turn point 1 (LTP1)** = eerste knikpunt uit een 3-segments stuksgewijze lineaire
  regressie (zie 1.5).
- **Manueel** = zelf ingegeven waarde, of de bol slepen op de grafiek.

### 1.4 Anaerobe drempel (LT2) — methodes
- **D-max** = punt op de polynoomcurve met de grootste loodrechte afstand tot de rechte van
  het eerste naar het laatste meetpunt (400 samples). Formule loodrechte afstand:
  `d = |dy·x − dx·y + x2·y1 − y2·x1| / hypot(dx, dy)`.
- **D-max modified** = zelfde D-max, maar de startlijn begint pas bij het eerste punt met een
  lactaatstijging ≥ 0,4 mmol t.o.v. het vorige punt (`dmaxModStart`).
- **4 mmol (OBLA)** = `speedAtLactate(4,0)`.
- **Lactate turn point 2 (LTP2)** = tweede knikpunt uit de 3-segments regressie.
- **Manueel** = zelf ingegeven of gesleept.

### 1.5 Stuksgewijze regressie (LTP1/LTP2) — `segFit`
Verdeel de punten in 3 aaneensluitende segmenten; zoek de splitsing (i, j) die de som van de
gekwadrateerde residu's (SSE) van drie afzonderlijke lineaire regressies minimaliseert.
- `ltp1` = snijpunt van regressielijn 1 en 2; `ltp2` = snijpunt van lijn 2 en 3.
- Snijpunt van lijnen A, B: `x = (B.q − A.q) / (A.m − B.m)`.
- Beide knikpunten worden geklemd binnen het gemeten bereik. Bij < 4 punten valt het terug op
  eerste/laatste `v`.

### 1.6 Maximale waarden
`Max` = hoogste gemeten `v` en hoogste HF (of handmatig overschreven). Dient als bovenanker
voor de hoogste zones.

### 1.7 Trainingszones (7) — `ZONE_MODEL`
De zones zijn fracties/interpolaties tussen drie ankers: `a1 = LT1`, `a2 = LT2`, `mx = Max`,
apart toegepast op HF én op `v`:

| Zone | Label | Ondergrens | Bovengrens |
|---|---|---|---|
| 1 | LSD / Herstel | 0,80·a1 | 0,92·a1 |
| 2 | Aerobe duur | 0,92·a1 | a1 |
| 3 | Tempo | a1 | a1 + 0,5·(a2−a1) |
| 4 | Subthreshold | a1 + 0,5·(a2−a1) | a2 |
| 5a | Superthreshold (LT2) | a2 | a2 + 0,40·(mx−a2) |
| 5b | Aerobe capaciteit (VO₂max) | a2 + 0,40·(mx−a2) | a2 + 0,85·(mx−a2) |
| 6 | Anaerobe capaciteit | a2 + 0,85·(mx−a2) | mx |

Bewerkbaar in `ZONE_MODEL`. HF- en tempokolommen zijn niet exact elkaars spiegelbeeld omdat
de HF- en `v`-ankers licht anders op de curve liggen (fysiologisch correct).

---

## 2. Critical Power (fietsen) — `calcCP`

2-parametermodel: vermogen `P(t) = CP + W'/t`, oftewel arbeid `W = P·t = CP·t + W'`.
- **2 inspanningen** (bv. 3 en 12 min, tijden in seconden):
  `CP = (P_lang·t_lang − P_kort·t_kort) / (t_lang − t_kort)`
  `W' = (P_kort − CP) · t_kort`
- **3+ inspanningen:** lineaire regressie van arbeid `W` tegen tijd `t` (`linreg`):
  helling = `CP`, snijpunt = `W'`.
- `CP` ligt doorgaans net boven FTP (rapport toont `≈ FTP = 0,97·CP`). `W'` typisch 10–30 kJ.

Vermogenszones (% van CP), Coggan-stijl — `CP_ZONES`:
Z1 Herstel <55 · Z2 Duur 55–75 · Z3 Tempo 75–90 · Z4 Drempel 90–105 · Z5 VO₂max 105–120 ·
Z6 Anaeroob 120–150 · Z7 Neuromusculair >150.

---

## 3. Critical Swim Speed (zwemmen) — `calcCSS`

Zelfde model op afstand–tijd. Twee (of meer) all-out tijdritten, standaard 400 m en 200 m:
- `CSS = (D_lang − D_kort) / (t_lang − t_kort)` m/s.
- Tempo per 100 m = `100 / CSS`.
- 3+ afstanden: lineaire regressie afstand vs tijd; helling = `CSS`.

Zwemzones (% van CSS-snelheid), weergegeven als tempo/100 m — `CSS_ZONES`:
Z1 Herstel <85 · Z2 Aeroob 85–95 · Z3 Drempel (CSS) 95–100 · Z4 VO₂max 100–110 · Z5 Sprint >110.

---

## 4. Critical Velocity — 3 of 5 km looptest — `calcCV`

Zelfde 2-parametermodel op afstand–tijd (lopen).
- **Twee afstanden (3 én 5 km):** `CV = (5000 − 3000) / (t5k − t3k) = 2000 / (t5k − t3k)` m/s;
  `D' = 3000 − CV·t3k` (m). Gemeten drempel.
- **Eén afstand (3 km óf 5 km):** geschat via `CV = (afstand − D') / tijd` met een
  **aangenomen D'** (standaard 200 m, aanpasbaar; D' bij lopers ~100–300 m). D' is een
  capaciteit (meter), geen aparte testafstand.
- Drempeltempo = `1000 / CV` s/km. `CV` ≈ Functional Threshold Pace.

Loopzones volgens **Joe Friel**:
- Pace-zones = veelvouden van het drempeltempo (`FRIEL_PACE`, >1 = trager):
  Z1 >1,29 · Z2 1,14–1,29 · Z3 1,06–1,14 · Z4 1,01–1,06 · Z5a 0,97–1,01 · Z5b 0,93–0,97 · Z5c <0,93.
- HF-zones = % van LTHR (`FRIEL_HR`): Z1 <85 · Z2 85–89 · Z3 90–94 · Z4 95–99 · Z5a 100–102 ·
  Z5b 102–106 · Z5c >106. LTHR optioneel in te vullen (uit 30-min tijdrit: gem. HF laatste 20 min).

Nuance in het verslag: Friels kanonieke drempeltest is de 30-min tijdrit; de 3/5 km-aanpak
benadert de drempel via het critical-velocity-model (TrainingPeaks leidt pace-zones ook uit
een 3k/5k/10k af).

---

## 5. Wedstrijdvoedingsplan — `nutriPlan`

Richtwaarden op basis van de ACSM/AND/DC-positie *Nutrition and Athletic Performance* (2016),
aangevuld met recentere ultra-praktijk (tot ~120 g/u bij getrainde darm).

**Duur** komt uit de verwachte eindtijd; bij triatlon wordt de zwemtijd afgetrokken zodat het
voeden pas op de fiets start (`feedStart = zwemtijd`, `feedEnd = totaal − 5 min`).

**Koolhydraten per uur** (`cph`), naar duur en niveau (recreatief / elite):

| Duur | Recreatief | Elite |
|---|---|---|
| < 45 min | 0 | 0 |
| 45–75 min | 30 | 45 |
| 1–2,5 u | 60 | 90 |
| 2,5–3 u | 90 | 120 |
| > 3 u (ultra) | 120 | 120 |

Totaal KH = `cph × voedingsuren`. Eigen bronnen (naam, g/portie, aantal) worden afgetrokken;
de rest wordt met gels ingevuld: `aantal gels = round((totaal − bron-KH) / gram_per_gel)`.
Boven ~60 g/u wordt glucose:fructose (meerdere transporteerbare koolhydraten) aangeraden.

**Vocht** (ml/u) naar temperatuur `t` (°C): <12 → 450 · <18 → 550 · <24 → 650 · <29 → 750 ·
≥29 → 850. Vertaald naar ml per drinkinterval. Houd het vochttekort < ~2% lichaamsgewicht.

**Natrium** (mg/u) naar temperatuur: <18 → 500 · <24 → 700 · <29 → 900 · ≥29 → 1100. Meer bij
hitte, lange duur of 'zoute zweters'. Zweet bevat gemiddeld ~1 g natrium per liter.

**Vóór de start:** koolhydraatlading `1–4 g/kg` (`preLo = 1·kg`, `preHi = 3·kg`) 1–4 u vooraf.

**Tijdlijn** (`nutriTimeline`): drinkinterval = 15 min (≤ 3 u) of 20 min (> 3 u). Op elk
interval staat de drinkhoeveelheid; de gels worden gelijkmatig over de intervallen verdeeld
(soms meerdere per moment bij hoge doelen). Output = samenvatting + uitgeschreven schema
(tijd, drinken, gel, cumulatieve KH).

---

## 6. Overige rekenhulp
- `pace(v) = 3600/v` → mm:ss; `paceToSpeed("m:ss") = 60/(min + sec/60)`.
- `niceStep(range)` — nette asinterval (1/2/5/10 × macht van 10) voor de grafiek-x-as.
- `hm(min)` / `hhmm(min)` / `parseHM("u:mm")` — tijdweergave/parsing voor de voedingsplanner.
- Alle algoritmes zijn puur en testbaar in Node (zie ARCHITECTUUR.md).
