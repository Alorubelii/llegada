#!/usr/bin/env python3
"""
Llegada · empaquetador.

Mete los datos (estaciones, horario del día, puntualidad, mapa e instantánea)
dentro de un único index.html para que funcione aunque no haya servidor.

Uso:
  python3 bundle.py --data ../data --fecha 2026-11-01 --api https://llegada.TU-USUARIO.workers.dev --out ../index.html
  python3 bundle.py ... --instantanea flota.csv   (añade posiciones reales de respaldo)
"""
import argparse, csv, json, os

SKELETON = (
    '<!doctype html><html lang="es"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    '<meta name="apple-mobile-web-app-capable" content="yes">'
    '<link rel="icon" href="icon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="icon-192.png">'
    '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
    'body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>'
    '</head><body>@@BODY@@</body></html>'
)

def compact(obj):
    # evita que "</script>" dentro de un nombre cierre la etiqueta
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

def instantanea(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    ts = max(r["timestamp_utc"] for r in rows)
    out = []
    for r in rows:
        if r["timestamp_utc"] != ts:
            continue
        try:
            d = int(float(r["retraso_min"]))
            if not (-60 < d < 600):
                continue
            out.append([r["tren"].zfill(5), d, round(float(r["latitud"]), 5), round(float(r["longitud"]), 5),
                        r["mat"], r["origen"].zfill(5), r["destino"].zfill(5), 1 if r["accesible"] == "True" else 0])
        except (ValueError, KeyError):
            pass
    return {"ts": ts, "trenes": out}

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(here, "..", "src", "app.html"))
    ap.add_argument("--data", default=os.path.join(here, "..", "data"))
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--api", default="")
    ap.add_argument("--geo", default=None)
    ap.add_argument("--instantanea", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--standalone", action="store_true", help="añade <!doctype>, <head> y <body> (para GitHub Pages)")
    a = ap.parse_args()

    def load(name):
        p = os.path.join(a.data, name)
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

    html = open(a.src, encoding="utf-8").read()
    rep = {
        "/*@ESTACIONES@*/": compact(load("estaciones.json") or {}),
        "/*@HORARIOS@*/": compact(load(f"horarios-{a.fecha}.json") or {"fecha": None, "trenes": {}}),
        "/*@PUNTUALIDAD@*/": compact(load("puntualidad.json") or {"trenes": {}}),
        "/*@GEO@*/": compact(json.load(open(a.geo or os.path.join(a.data, "geo.json"), encoding="utf-8"))),
        "/*@INSTANTANEA@*/": compact(instantanea(a.instantanea)) if a.instantanea else "/*@INSTANTANEA@*/",
    }
    for k, v in rep.items():
        html = html.replace(k, v, 1)
    if a.api:
        html = html.replace('"/*@API@*/"', json.dumps(a.api.rstrip("/")), 1)
    if a.standalone:
        html = SKELETON.replace("@@BODY@@", html)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{a.out}: {os.path.getsize(a.out)//1024} KB")

if __name__ == "__main__":
    main()
