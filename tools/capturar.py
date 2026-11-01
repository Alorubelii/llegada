#!/usr/bin/env python3
"""Llegada · guarda una lectura de posiciones y retrasos (la lanza GitHub Actions cada 15 min).
Añade filas a historico/AAAA/MM/flota-AAAA-MM-DD.csv con el mismo formato que usa build_data.py."""
import csv, datetime as dt, json, os, sys, time, urllib.request

URL = "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json?v=%d"
CAMPOS = ["timestamp_utc", "tren", "linea", "retraso_min", "origen", "destino", "latitud", "longitud", "accesible", "mat"]

def main(carpeta="historico"):
    req = urllib.request.Request(URL % int(time.time() * 1000), headers={"User-Agent": "Mozilla/5.0 (Llegada)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        datos = json.load(r)
    ahora = dt.datetime.now(dt.timezone.utc)
    ts = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    ruta = os.path.join(carpeta, ahora.strftime("%Y"), ahora.strftime("%m"), ahora.strftime("flota-%Y-%m-%d.csv"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    nuevo = not os.path.exists(ruta)
    n = 0
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(CAMPOS)
        for t in datos.get("trenes", []):
            w.writerow([ts, t.get("codComercial", ""), t.get("desCorridor", "").replace(",", " "), t.get("ultRetraso", ""),
                        t.get("codOrigen", ""), t.get("codDestino", ""), t.get("latitud", ""), t.get("longitud", ""),
                        bool(t.get("accesible")), t.get("mat", "")])
            n += 1
    print(f"{ruta}: {n} trenes")

if __name__ == "__main__":
    main(*sys.argv[1:])
