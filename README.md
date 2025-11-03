# Deutschlandkarte – Checkbox + Zahlen + PDF (v11)

**Neu:**
- Pro Bundesland ein **Zahlenfeld** erfassen.
- Zahl wird in der **Webkarte** (optional) und im **PDF** am Landes-Zentroid ausgegeben.
- Checkbox-Mehrfachauswahl & Kartenklick (Toggle) bleiben erhalten.

## Installation
```bash
pip install -r requirements.txt
```

## Start
```bash
streamlit run deutschland_karte_app.py
```

## PDF
- Alle erfassten Werte werden mit max. **2 Dezimalstellen** gedruckt.
- Optional: Code kann erweitert werden (Farbskala/Choropleth, Legende, Datenexport).
