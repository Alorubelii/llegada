#!/usr/bin/env python3
"""
Llegada · generador de datos estáticos.

Lee el GTFS oficial de Renfe (Alta Velocidad, Larga y Media Distancia) y genera:
  data/estaciones.json        catálogo de estaciones  {codigo: [nombre, lat, lon]}
  data/horarios-AAAA-MM-DD.json  trenes que circulan ese día con sus paradas
  data/puntualidad.json       (opcional) histórico de retrasos por tren

Uso:
  python3 build_data.py --gtfs carpeta_gtfs --fecha 2026-11-01 --out ../data
  python3 build_data.py --gtfs carpeta_gtfs --historico carpeta_csv --out ../data

El GTFS se descarga de:
  https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip
"""
import argparse, csv, datetime as dt, json, os, statistics, glob, collections

PRODUCTOS = {  # nombre comercial -> grupo para colores y filtros
    "AVE": "av", "AVE INT": "av", "AVLO": "av", "EUROMED": "av",
    "AVANT": "md", "AVANT EXP": "md",
    "ALVIA": "ld", "Intercity": "ld", "TRENCELTA": "ld",
    "MD": "md", "REGIONAL": "md", "REG.EXP.": "md", "PROXIMDAD": "md",
}


def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            yield {k.strip(): (v or "").strip() for k, v in r.items() if k}


def hhmm_to_min(t):
    h, m, *_ = t.split(":")
    return int(h) * 60 + int(m)


def servicios_activos(gtfs, fecha):
    ymd = fecha.strftime("%Y%m%d")
    dia = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][fecha.weekday()]
    activos = set()
    for r in rows(os.path.join(gtfs, "calendar.txt")):
        if r["start_date"] <= ymd <= r["end_date"] and r[dia] == "1":
            activos.add(r["service_id"])
    p = os.path.join(gtfs, "calendar_dates.txt")
    if os.path.exists(p):
        for r in rows(p):
            if r["date"] != ymd:
                continue
            if r["exception_type"] == "1":
                activos.add(r["service_id"])
            elif r["exception_type"] == "2":
                activos.discard(r["service_id"])
    return activos


def estaciones(gtfs):
    out = {}
    for r in rows(os.path.join(gtfs, "stops.txt")):
        try:
            out[r["stop_id"].zfill(5)] = [r["stop_name"], round(float(r["stop_lat"]), 5), round(float(r["stop_lon"]), 5)]
        except ValueError:
            pass
    return out


def horarios(gtfs, fecha):
    activos = servicios_activos(gtfs, fecha)
    rutas = {r["route_id"]: r["route_short_name"] for r in rows(os.path.join(gtfs, "routes.txt"))}
    trips = {}
    for r in rows(os.path.join(gtfs, "trips.txt")):
        if r["service_id"] in activos:
            trips[r["trip_id"]] = (r["trip_short_name"].zfill(5), rutas.get(r["route_id"], ""))
    paradas = collections.defaultdict(list)
    for r in rows(os.path.join(gtfs, "stop_times.txt")):
        if r["trip_id"] in trips:
            paradas[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"].zfill(5),
                                          hhmm_to_min(r["arrival_time"]), hhmm_to_min(r["departure_time"])))
    trenes = {}
    for tid, (num, prod) in trips.items():
        ps = sorted(paradas.get(tid, []))
        if len(ps) < 2:
            continue
        # [codigo, llegada (min desde 00:00), salida]
        trenes[num] = {"p": prod, "s": [[c, a, d] for _, c, a, d in ps]}
    return {"fecha": fecha.isoformat(), "trenes": trenes}


def puntualidad(carpeta):
    """CSV de instantáneas (timestamp_utc,tren,linea,retraso_min,origen,destino,...).
    Para cada tren y día se toma el retraso máximo observado como aproximación
    del retraso con el que terminó el viaje."""
    por_tren_dia = collections.defaultdict(dict)
    for f in sorted(glob.glob(os.path.join(carpeta, "**", "*.csv"), recursive=True)):
        for r in rows(f):
            try:
                d = int(float(r["retraso_min"]))
            except (ValueError, KeyError):
                continue
            if d < -30 or d > 600:  # valores anómalos del feed
                continue
            dia = r["timestamp_utc"][:10]
            k = (r["tren"].zfill(5), r["origen"].zfill(5), r["destino"].zfill(5))
            por_tren_dia[k][dia] = max(por_tren_dia[k].get(dia, -99), d)
    trenes = {}
    for (num, o, de), dias in por_tren_dia.items():
        v = list(dias.values())
        if len(v) < 4:
            continue
        prev = trenes.get(num)
        if prev and prev["n"] >= len(v):
            continue
        trenes[num] = {
            "o": o, "d": de, "n": len(v),
            "med": round(statistics.median(v)),
            "p5": round(100 * sum(1 for x in v if x <= 5) / len(v)),
            "p15": round(100 * sum(1 for x in v if x > 15) / len(v)),
            "max": max(v),
        }
    fechas = sorted({d for dias in por_tren_dia.values() for d in dias})
    return {"desde": fechas[0] if fechas else None, "hasta": fechas[-1] if fechas else None, "trenes": trenes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gtfs", required=True)
    ap.add_argument("--fecha", default=dt.date.today().isoformat())
    ap.add_argument("--historico")
    ap.add_argument("--out", default="data")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    fecha = dt.date.fromisoformat(a.fecha)

    def dump(nombre, obj):
        p = os.path.join(a.out, nombre)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{p}: {os.path.getsize(p)//1024} KB")

    dump("estaciones.json", estaciones(a.gtfs))
    h = horarios(a.gtfs, fecha)
    dump(f"horarios-{fecha.isoformat()}.json", h)
    print(f"  {len(h['trenes'])} trenes el {fecha}")
    if a.historico:
        p = puntualidad(a.historico)
        dump("puntualidad.json", p)
        print(f"  {len(p['trenes'])} trenes con histórico ({p['desde']} → {p['hasta']})")


if __name__ == "__main__":
    main()
