# Project page

Static page published to GitHub Pages by `.github/workflows/pages.yml`
(https://marcjohnce.github.io/homebridge-panel/).

- `index.html` – the whole page (HTML, CSS, JS in one file; English with German toggle)
- `assets/screens/` – screenshots, regenerate with `python tools/site_screenshots.py`
- `assets/fonts/` – Jost (SIL Open Font License, see `OFL.txt`), same font as the app

Preview locally: `python3 -m http.server -d site 8000` and open http://localhost:8000.
