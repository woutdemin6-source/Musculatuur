# Architectuur & integratie

## Wat het is
Eén zelfstandig HTML-bestand (`index.html`): een prestatietest- en voedingssuite voor een
coach/kinesitherapeut, met atleet-verslagen (print/PDF). **Geen build-stap, geen framework,
geen dependencies.** Enige externe bron: Google Fonts (CDN) — werkt ook offline met systeemfonts.
Taal van UI en verslagen: **Nederlands**.

## Testtypes (`state.testType`)
- `lactate` — lactaattest, met sportschakelaar `state.lactSport` (`run` = afstand+tijd→tempo,
  `bike` = watt).
- `cp` — Critical Power (fietsen).
- `css` — Critical Swim Speed (zwemmen).
- `cv` — 3 of 5 km looptest (Critical Velocity, Friel).
- `voeding` — Wedstrijdvoedingsplan (planner, geen test).

## Bestandsopbouw van index.html
Drie delen binnen één bestand:
1. `<style>` — design tokens (CSS-variabelen), componenten, en `@media print` (A4, toont enkel
   `#reportPanel`).
2. HTML — topbar, 4-staps stepper (`section.panel`): Gegevens, Testdata, Analyse/Drempels,
   Verslag. Test-specifieke kaarten dragen klassen `tt-only tt-<type>` (+ `tt-generic` voor
   cp/css/cv).
3. `<script>` — config → wiskunde → per-test rekenkernen → render → bindings → init (onderaan).

## Belangrijke, bewerkbare config (bovenaan het script)
- `DEFAULT_LOGO` — base64 data-URI van het logo (vervangbaar in UI of hier).
- `TEST_META` — naam/subtitel/discipline per testtype.
- `RACES` — wedstrijdpresets voor de voedingsplanner.
- `ZONE_MODEL` + `ZONE_DESC` — lactaatzones en omschrijvingen.
- `CP_ZONES`, `CSS_ZONES`, `FRIEL_PACE`, `FRIEL_HR`, `ZCOLORS` — zonemodellen nieuwe testen.
- `LT1_METHODS`, `LT2_METHODS` — drempelmethodes.
Zie `FORMULES.md` voor de betekenis en formules.

## Render-flow
`refreshAnalysis()` schakelt per testtype:
- `voeding` → `renderNutri()` + `renderReport()`.
- `cp/css/cv` → `renderGeneric()` + `renderReport()`.
- `lactate` → chart (`chartSVG` in `#liveChart`) + `bindChartDrag()` + methodes + zones + report.
`renderReport()` schakelt naar `renderReportNutri()` / `renderReportGeneric()` / lactaatverslag.
Verslagen krijgen vooraan een voorblad (`coverPage`).

## Conventies / valkuilen
- **Geen localStorage/sessionStorage.** State leeft in het `state`-object; persistentie via
  "Project opslaan/laden" (JSON export/import, `bootFromState()`).
- Herbouw van invoervelden mag typende invoer niet overschrijven → check
  `document.activeElement` vóór je een `.value` zet (manuele drempelvelden, max, tabel).
- SVG-grafiek gebruikt **vaste hex-kleuren**, geen `var(--x)` als presentatie-attribuut.
- **Sleepbare drempel:** `drawTh` tekent `[data-drag]`-grepen; `bindChartDrag()` bindt
  `pointerdown`, met `pointermove/up` op `window` zodat herrenderen tijdens het slepen niet
  onderbreekt. De SVG draagt schaalinfo in `data-*` om pixel→`v` om te rekenen; de code vraagt
  telkens de live SVG op (niet de stale referentie).
- **Diep-link:** `index.html#voeding` (of `#lactate`/`#cp`/`#css`/`#cv`) opent rechtstreeks dat
  type en verbergt de test-keuze (`applyDeepLink()`) — handig om als aparte site-pagina te embedden.
- **Spraak→tekst advies:** `initSpeech()` gebruikt de Web Speech API (nl-BE); valt terug op typen.

## Wiskunde testen zonder browser (Node)
De rekenkern is puur en los te testen:
1. Knip het script uit `index.html`.
2. Stub `document`/`window`/`location` minimaal.
3. `eval` het script (zonder de laatste init-regel) en roep de functies aan
   (`calcCP`, `calcCSS`, `calcCV`, `computeLT1/2`, `computeZones`, `nutriPlan`, `nutriTimeline`).
Zo is dit project tijdens de bouw stap voor stap gevalideerd.

## Integreren in een groter project
Omdat het één statisch bestand zonder dependencies is:
- **Als aparte pagina/route:** host `index.html` (of hernoem het, bv. `tools/prestatietest.html`).
  Link vanuit je site; gebruik `#voeding` e.d. voor directe deep-links naar een specifiek onderdeel.
- **Als iframe/embed:** `<iframe src="prestatietest.html#voeding">` in een bestaande pagina.
- **In een build-pipeline:** je kan het bestand as-is opnemen als static asset; er is niets te
  compileren. Wil je het splitsen in aparte HTML/CSS/JS-bestanden, dan is de scheiding recht-
  toe-rechtaan (één `<style>`-blok, één `<script>`-blok).
- **Foto-OCR** vereist een eigen Anthropic API-sleutel (client-side, `claude-sonnet-5`); zet
  een versie met sleutel niet op een openbaar toegankelijke pagina.
