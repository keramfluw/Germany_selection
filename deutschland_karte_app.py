# deutschland_karte_app.py (v7)
# Fixes:
# - Tooltip-Felder werden NUR aus tatsächlich vorhandenen Property-Keys befüllt.
# - Wenn kein passender Key existiert, wird KEIN Tooltip registriert (verhindert AssertionError).
# - Robuster Kartenklick (prepared + buffer) und Dropdown-Fallback bleiben erhalten.

import os, io, json
import streamlit as st
from streamlit_folium import st_folium
import folium, requests
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape

st.set_page_config(page_title="Interaktive Deutschlandkarte", layout="wide")

@st.cache_data
def load_states_geojson():
    urls = [
        "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/2_hoch.geo.json",
        "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/1_sehr_hoch.geo.json",
    ]
    last_err = None
    for u in urls:
        try:
            r = requests.get(u, timeout=20); r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
    raise RuntimeError(f"GeoJSON konnte nicht geladen werden: {last_err}")

CITIES = [
    ("Berlin", 52.520008, 13.404954),
    ("Hamburg", 53.551086, 9.993682),
    ("München", 48.137154, 11.576124),
    ("Köln", 50.937531, 6.960279),
    ("Frankfurt am Main", 50.110924, 8.682127),
    ("Stuttgart", 48.77845, 9.180013),
    ("Düsseldorf", 51.227741, 6.773456),
    ("Dortmund", 51.513587, 7.465298),
    ("Essen", 51.455643, 7.011555),
    ("Leipzig", 51.339695, 12.373075),
    ("Bremen", 53.079296, 8.801694),
    ("Dresden", 51.050409, 13.737262),
    ("Hannover", 52.375892, 9.73201),
    ("Nürnberg", 49.452103, 11.076665),
    ("Duisburg", 51.434408, 6.762329),
    ("Bochum", 51.481845, 7.216236),
    ("Wuppertal", 51.256213, 7.150764),
    ("Bielefeld", 52.030228, 8.532471),
    ("Bonn", 50.73743, 7.098207),
    ("Münster", 51.960665, 7.626135),
    ("Karlsruhe", 49.00689, 8.403653),
    ("Mannheim", 49.487459, 8.466039),
    ("Augsburg", 48.370545, 10.89779),
    ("Wiesbaden", 50.078218, 8.239761),
    ("Gelsenkirchen", 51.517744, 7.085717),
    ("Mönchengladbach", 51.180457, 6.442804),
    ("Braunschweig", 52.268874, 10.52677),
    ("Chemnitz", 50.827845, 12.92137),
    ("Kiel", 54.323293, 10.122765),
    ("Aachen", 50.775346, 6.083887),
]

@st.cache_data
def prepare_geometries(geojson):
    feats = []
    names = []
    for f in geojson["features"]:
        props = f.get("properties", {}) or {}
        # State name robust ermitteln
        name = props.get("NAME_1") or props.get("GEN") or props.get("name") or props.get("NAME") or props.get("id") or "Unbekannt"
        geom = shape(f["geometry"])
        feats.append({"name": name, "geom": geom, "prep": prep(geom), "props": props})
        names.append(name)
    bounds = unary_union([d["geom"] for d in feats]).bounds
    # Tooltip-Kandidaten nur aus tatsächlich vorhandenen Props ableiten
    preferred = ("name", "GEN", "NAME_1", "NAME", "id")
    available = set().union(*(set((d["props"] or {}).keys()) for d in feats))
    tooltip_fields = [k for k in preferred if k in available]
    return feats, bounds, tooltip_fields, sorted([n for n in names if n])

def create_pdf(features, bounds, cities, selected_name):
    page_w, page_h = landscape(A4); margin = 36
    draw_w = page_w - 2*margin; draw_h = page_h - 2*margin
    minx, miny, maxx, maxy = bounds
    data_w = maxx - minx; data_h = maxy - miny
    s = min(draw_w / data_w, draw_h / data_h)
    ox = margin + (draw_w - s*data_w) / 2; oy = margin + (draw_h - s*data_h) / 2
    def proj(lon, lat): return ox + (lon - minx)*s, oy + (lat - miny)*s

    buff = io.BytesIO(); c = canvas.Canvas(buff, pagesize=landscape(A4))
    c.setFont("Helvetica-Bold", 14)
    title = "Deutschland – Bundesländer & Großstädte"
    if selected_name: title += f" (markiert: {selected_name})"
    c.drawString(margin, page_h - margin + 10, title)

    from reportlab.lib import colors as C
    c.setLineWidth(0.5)
    for d in features:
        draw_geom(c, d["geom"], proj, C.Color(0.12,0.23,0.54), C.Color(0.38,0.65,0.98), 0.2, 0.6)

    if selected_name:
        for d in features:
            if d["name"] == selected_name:
                draw_geom(c, d["geom"], proj, C.Color(0.09,0.4,0.2), C.Color(0.13,0.77,0.37), 0.5, 1.2)

    c.setFont("Helvetica", 7)
    for nm, lat, lon in cities:
        x, y = proj(lon, lat); c.circle(x, y, 1.6, fill=1, stroke=0); c.drawString(x + 3, y + 1, nm)

    c.showPage(); c.save(); buff.seek(0); return buff

def draw_geom(c, geom, proj, stroke_color, fill_color, fill_alpha, line_width):
    from shapely.geometry import Polygon, MultiPolygon
    c.setStrokeColor(stroke_color); c.setLineWidth(line_width); c.setFillColor(fill_color)
    try: c.setFillAlpha(fill_alpha)
    except Exception: pass
    def draw_polygon(poly: Polygon):
        ext = list(poly.exterior.coords)
        if len(ext) < 3: return
        p = c.beginPath(); x0,y0 = proj(ext[0][0], ext[0][1]); p.moveTo(x0,y0)
        for lon, lat in ext[1:]: x,y = proj(lon,lat); p.lineTo(x,y)
        p.close(); c.drawPath(p, fill=1, stroke=1)
        for interior in poly.interiors:
            coords = list(interior.coords)
            if len(coords) < 3: continue
            p2 = c.beginPath(); x0,y0 = proj(coords[0][0], coords[0][1]); p2.moveTo(x0,y0)
            for lon, lat in coords[1:]: x,y = proj(lon,lat); p2.lineTo(x,y)
            p2.close(); c.drawPath(p2, fill=1, stroke=0); c.setFillColor(fill_color)
    if geom.geom_type == "Polygon": draw_polygon(geom)
    elif geom.geom_type == "MultiPolygon":
        for poly in geom.geoms: draw_polygon(poly)

def main():
    st.title("Interaktive Deutschlandkarte – Bundesländer & Großstädte (PDF-Export)")

    geojson = load_states_geojson()
    feats, bounds, tooltip_fields, state_names = prepare_geometries(geojson)

    left, right = st.columns([2,1], gap="large")

    with left:
        m = folium.Map(location=[51.1657, 10.4515], zoom_start=6, tiles="OpenStreetMap", control_scale=True)

        if "selected_state" not in st.session_state: st.session_state.selected_state = None
        if "last_click" not in st.session_state: st.session_state.last_click = None

        def style_fn(feature):
            props = feature.get("properties", {}) or {}
            nm = props.get("name") or props.get("GEN") or props.get("NAME_1") or props.get("NAME") or props.get("id")
            if st.session_state.selected_state and nm == st.session_state.selected_state:
                return dict(color="#166534", weight=2, fill=True, fillOpacity=0.5, fillColor="#22c55e")
            return dict(color="#1e3a8a", weight=1, dash_array="3", fill=True, fillOpacity=0.2, fillColor="#60a5fa")

        # Hover-Highlight
        def highlight_fn(feature):
            return dict(weight=3, color="#0f766e", fillOpacity=0.35)

        gj = folium.GeoJson(data=geojson, style_function=style_fn, highlight_function=highlight_fn, name="Bundesländer").add_to(m)

        # Tooltip sicher hinzufügen (nur wenn es mind. 1 gültiges Feld gibt)
        safe_fields = [f for f in tooltip_fields if f in (feats[0]["props"] or {}).keys()]
        if not safe_fields:
            # Wenn sich Property-Schemata unterscheiden, nimm Schnittmenge über alle Features
            common = set((feats[0]["props"] or {}).keys())
            for d in feats[1:]:
                common &= set((d["props"] or {}).keys())
            safe_fields = [next(iter(common))] if common else []
        if safe_fields:
            folium.GeoJsonTooltip(fields=safe_fields, sticky=True).add_to(gj)

        # Stadtmarker
        for name, lat, lon in CITIES:
            folium.CircleMarker([lat, lon], radius=4, color="black", weight=1, fill=True, fill_opacity=1).add_to(m)
            folium.Marker([lat, lon], tooltip=name, popup=f"{name} ({lat:.4f}, {lon:.4f})").add_to(m)

        data = st_folium(m, height=640, width=None, returned_objects=[])

        # Klick robust auswerten
        if data and data.get("last_clicked"):
            lat = float(data["last_clicked"]["lat"]); lon = float(data["last_clicked"]["lng"])
            st.session_state.last_click = (lat, lon)
            pt = Point(lon, lat); buf = pt.buffer(1e-6)
            hit = None
            for d in feats:
                try:
                    if d["prep"].intersects(buf) and (d["geom"].contains(pt) or d["geom"].intersects(buf)):
                        hit = d["name"]; break
                except Exception: pass
            st.session_state.selected_state = hit

    with right:
        st.subheader("Auswahl")
        choice = st.selectbox("Bundesland", options=["– kein –"] + state_names, index=(["– kein –"] + state_names).index(st.session_state.selected_state) if st.session_state.selected_state in state_names else 0)
        if choice != "– kein –":
            st.session_state.selected_state = choice

        st.markdown("---")
        st.write(st.session_state.selected_state or "Kein Bundesland ausgewählt")
        if "last_click" in st.session_state and st.session_state.last_click:
            lat, lon = st.session_state.last_click
            st.caption(f"Letzter Klick: lat={lat:.6f}, lon={lon:.6f}")
        if st.session_state.selected_state and st.button("Auswahl löschen"):
            st.session_state.selected_state = None

        st.markdown("---")
        st.subheader("PDF-Export")
        if st.button("PDF generieren"):
            buff = create_pdf(feats, bounds, CITIES, st.session_state.selected_state)
            st.download_button("PDF herunterladen", data=buff.getvalue(),
                               file_name=f"Deutschlandkarte{'_'+st.session_state.selected_state.replace(' ','_') if st.session_state.selected_state else ''}.pdf",
                               mime="application/pdf")

        st.markdown("---")
        st.subheader("Hinweise")
        st.markdown("- Grenzen: GitHub `isellsoap/deutschlandGeoJSON`  \n- Basiskarte: © OpenStreetMap-Mitwirkende  \n- PDF: Vektorzeichnung (keine Kachel-Screenshots)")

if __name__ == "__main__":
    main()
