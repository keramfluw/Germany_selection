# deutschland_karte_app.py (v12.1)
# Fix: Streamlit CacheError (PicklingError for shapely.prepared.Prepare)
# - load_states_geojson() -> st.cache_data (serializable)
# - prepare_geometries()  -> st.cache_resource (returns shapely/prep)  ✅
# Keeps: Mobile-Ansicht, Checkboxen, Zahlen, PDF
#
# Tested against Streamlit 1.51.x and Shapely 2.1.x

import io
import streamlit as st
from streamlit_folium import st_folium
import folium, requests
from folium.plugins import Fullscreen, LocateControl
from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.prepared import prep
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape

st.set_page_config(page_title="Deutschlandkarte – Mobile + Werte (v12.1)", layout="wide")

@st.cache_data(show_spinner=False)
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

@st.cache_resource(show_spinner=False)
def prepare_geometries(geojson: dict):
    feats = []
    names = []
    for f in geojson.get("features", []):
        props = (f.get("properties") or {})
        name = props.get("name") or props.get("GEN") or props.get("NAME_1") or props.get("NAME") or props.get("id") or "Unbekannt"
        geom = shape(f["geometry"])
        feats.append({"name": name, "geom": geom, "prep": prep(geom), "props": props})
        names.append(name)
    bounds = unary_union([d["geom"] for d in feats]).bounds if feats else (5.8, 47.2, 15.1, 55.1)
    preferred = ("name","GEN","NAME_1","NAME","id")
    available = set().union(*(set((d["props"] or {}).keys()) for d in feats)) if feats else set()
    tooltip_fields = [k for k in preferred if k in available]
    state_names = sorted([n for n in names if n])
    return feats, bounds, tooltip_fields, state_names

def create_pdf(features, bounds, cities, selected_names, values_by_state):
    page_w, page_h = landscape(A4); margin = 36
    draw_w = page_w - 2*margin; draw_h = page_h - 2*margin
    minx, miny, maxx, maxy = bounds
    data_w = maxx - minx; data_h = maxy - miny
    s = min(draw_w / data_w, draw_h / data_h) if data_w*data_h else 1.0
    ox = margin + (draw_w - s*data_w) / 2; oy = margin + (draw_h - s*data_h) / 2
    def proj(lon, lat): return ox + (lon - minx)*s, oy + (lat - miny)*s

    buff = io.BytesIO(); c = canvas.Canvas(buff, pagesize=landscape(A4))
    c.setFont("Helvetica-Bold", 14)
    title = "Deutschland – Bundesländer & Werte"
    if selected_names:
        title += " (markiert: " + ", ".join(selected_names) + ")"
    c.drawString(margin, page_h - margin + 10, title)

    from reportlab.lib import colors as C
    c.setLineWidth(0.5)
    for d in features:
        draw_geom(c, d["geom"], proj, C.Color(0.12,0.23,0.54), C.Color(0.38,0.65,0.98), 0.18, 0.5)

    if selected_names:
        sel = set(selected_names)
        for d in features:
            if d["name"] in sel:
                draw_geom(c, d["geom"], proj, C.Color(0.09,0.4,0.2), C.Color(0.13,0.77,0.37), 0.5, 1.2)

    c.setFont("Helvetica-Bold", 9)
    for d in features:
        nm = d["name"]
        val = values_by_state.get(nm, None)
        if val is None: continue
        try:
            centroid = d["geom"].centroid
            x, y = proj(centroid.x, centroid.y)
            c.setFillColor(C.black); c.drawString(x+2, y+2, f"{val:.2f}")
        except Exception:
            pass

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

def mobile_css():
    st.markdown("""
    <style>
    @media screen and (max-width: 600px) {
        .stButton>button, .stDownloadButton>button { width: 100%; padding: 12px 16px; font-size: 1.05rem; }
        .stCheckbox { padding: 6px 4px; }
        label { font-size: 1.02rem !important; }
        .stNumberInput input { font-size: 1.02rem !important; }
        .block-container { padding-top: 0.5rem; padding-bottom: 4rem; }
    }
    </style>
    """, unsafe_allow_html=True)

def right_panel(state_names, mobile=False):
    st.subheader("Auswahl & Werte" + (" (Mobile)" if mobile else ""))
    if mobile:
        query = st.text_input("Suchen", placeholder="Bundesland filtern...")
        names = [n for n in state_names if (query.lower() in n.lower())] if query else state_names
        with st.expander("Alle Auswahl-Optionen", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Alle auswählen"):
                    st.session_state.selected_states = names.copy()
            with c2:
                if st.button("Alle abwählen"):
                    st.session_state.selected_states = []
        st.markdown("---")
        updated_sel = set(st.session_state.selected_states)
        updated_vals = dict(st.session_state.state_values)
        for nm in names:
            ck = st.checkbox(nm, value=(nm in updated_sel), key=f"chk_{nm}")
            val = st.number_input(f"Wert für {nm}", key=f"num_{nm}", value=float(updated_vals.get(nm, 0.0)), step=1.0, format="%.2f")
            if ck: updated_sel.add(nm)
            else: updated_sel.discard(nm)
            updated_vals[nm] = float(val)
        st.session_state.selected_states = sorted(list(updated_sel))
        st.session_state.state_values = updated_vals
    else:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Alle auswählen"):
                st.session_state.selected_states = state_names.copy()
        with c2:
            if st.button("Alle abwählen"):
                st.session_state.selected_states = []
        st.markdown("---")
        half = (len(state_names)+1)//2
        left_names = state_names[:half]; right_names = state_names[half:]
        colA, colB = st.columns(2)
        def render_column(names, col):
            updated_sel = set(st.session_state.selected_states)
            updated_vals = dict(st.session_state.state_values)
            with col:
                for nm in names:
                    ck = st.checkbox(nm, value=(nm in updated_sel), key=f"chk_{nm}")
                    val = st.number_input(f"Wert für {nm}", key=f"num_{nm}", value=float(updated_vals.get(nm, 0.0)), step=1.0, format="%.2f")
                    if ck: updated_sel.add(nm)
                    else: updated_sel.discard(nm)
                    updated_vals[nm] = float(val)
            return sorted(list(updated_sel)), updated_vals
        selA, valsA = render_column(left_names, colA)
        st.session_state.selected_states = selA
        st.session_state.state_values = valsA
        selB, valsB = render_column(right_names, colB)
        st.session_state.selected_states = selB
        st.session_state.state_values = valsB

def main():
    mobile_css()
    st.title("Deutschlandkarte – Mobile + Werte (v12.1)")

    mobile_mode = st.toggle("Mobile-Ansicht", value=False)
    st.session_state.mobile_mode = mobile_mode

    geojson = load_states_geojson()
    feats, bounds, tooltip_fields, state_names = prepare_geometries(geojson)

    if "selected_states" not in st.session_state: st.session_state.selected_states = []
    if "state_values" not in st.session_state: st.session_state.state_values = {}
    if "last_click" not in st.session_state: st.session_state.last_click = None

    if mobile_mode:
        map_height = 360
    else:
        map_height = 640

    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6, tiles="OpenStreetMap",
                   control_scale=not mobile_mode, prefer_canvas=True, zoom_control=True)
    Fullscreen(position="topleft").add_to(m)
    LocateControl(auto_start=False, keepCurrentZoomLevel=True, flyTo=True, position="topleft").add_to(m)

    def style_fn(feature):
        props = feature.get("properties", {}) or {}
        nm = props.get("name") or props.get("GEN") or props.get("NAME_1") or props.get("NAME") or props.get("id")
        if nm in st.session_state.selected_states:
            return dict(color="#166534", weight=2, fill=True, fillOpacity=0.5, fillColor="#22c55e")
        return dict(color="#1e3a8a", weight=1, dash_array="3", fill=True, fillOpacity=0.18 if mobile_mode else 0.2, fillColor="#60a5fa")

    highlight_fn = lambda feature: dict(weight=3, color="#0f766e", fillOpacity=0.35)

    gj = folium.GeoJson(data=geojson, style_function=style_fn, highlight_function=highlight_fn, name="Bundesländer").add_to(m)

    safe_fields = [f for f in (tooltip_fields or []) if f in ((feats[0]["props"] or {}).keys() if feats else set())]
    if safe_fields:
        folium.GeoJsonTooltip(fields=safe_fields, sticky=True).add_to(gj)

    # Städte (reduziert auf Mobile)
    city_list = CITIES[:6] if mobile_mode else CITIES
    for name, lat, lon in city_list:
        folium.CircleMarker([lat, lon], radius=4, color="black", weight=1, fill=True, fill_opacity=1).add_to(m)
        if not mobile_mode:
            folium.Marker([lat, lon], tooltip=name, popup=f"{name} ({lat:.4f}, {lon:.4f})").add_to(m)

    # Zahlen als Textmarker an Zentroiden
    for d in feats:
        nm = d["name"]
        val = st.session_state.state_values.get(nm, None)
        if val is None: continue
        lat = d["geom"].centroid.y; lon = d["geom"].centroid.x
        folium.map.Marker([lat, lon], icon=folium.DivIcon(html=f'<div style="font-size:10px; font-weight:700;">{val:.2f}</div>')).add_to(m)

    data = st_folium(m, height=map_height, width=None, returned_objects=[])

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
        if hit:
            sel = set(st.session_state.selected_states)
            if hit in sel: sel.remove(hit)
            else: sel.add(hit)
            st.session_state.selected_states = sorted(list(sel))

    # Right panel
    right_panel(state_names, mobile=mobile_mode)

    st.markdown("---")
    if st.button("PDF generieren"):
        buff = create_pdf(feats, bounds, CITIES, st.session_state.selected_states, st.session_state.state_values)
        label = "Deutschlandkarte_Werte" + ( "_" + "_".join([s.replace(' ','_') for s in st.session_state.selected_states]) if st.session_state.selected_states else "" )
        st.download_button("PDF herunterladen", data=buff.getvalue(),
                           file_name=f"{label}.pdf", mime="application/pdf", use_container_width=True)

if __name__ == "__main__":
    main()
