# Deutschlandkarte – Mobile + Werte (v12.1)

**Fix:** `prepare_geometries()` nutzt jetzt **st.cache_resource** (Shapely/Prepared-Objekte sind nicht pickle-bar).
Damit verschwindet der in deinen Logs sichtbare Fehler `PicklingError: Prepared geometries cannot be pickled`.

## Installation
```bash
pip install -r requirements.txt
```

## Start
```bash
streamlit run deutschland_karte_app.py
```

## Hinweis
Falls du eine ältere Datei hattest, in der `prepare_geometries` noch mit `st.cache_data` dekoriert war,
bitte durch diese Version ersetzen.
