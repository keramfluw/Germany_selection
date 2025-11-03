# Interaktive Deutschlandkarte – Streamlit-App (v7)

**Fix:** Tooltip-Felder werden strikt aus vorhandenen Keys gebildet. Falls nichts geeignet ist, wird **kein Tooltip** registriert (verhindert `AssertionError: The field NAME_1 is not available ...`).  
**Weiterhin:** Robuste Klickerkennung + Dropdown-Fallback, PDF-Export.

## Installation
```bash
pip install -r requirements.txt
```

## Start
```bash
streamlit run deutschland_karte_app.py
```
