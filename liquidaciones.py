# -*- coding: utf-8 -*-
"""
LIQUIDACIONES.PY - Mapa de liquidaciones ESTIMADO, gratis (sustituye a Coinglass).

QUE ES Y QUE NO ES (honestidad ante todo):
  El "mapa de liquidaciones" de Coinglass NO son posiciones reales de los traders
  (ningun exchange publica eso). Es un MODELO estimado: asume que en cada vela se
  abrieron posiciones proporcionales al volumen, y proyecta donde se liquidarian
  segun los apalancamientos tipicos. Aqui replicamos ese mismo modelo con datos
  publicos de Binance Futures (el mayor liquidador del mercado).
  => Los niveles seran PARECIDOS a los de Coinglass, no identicos. Sirven igual
     para lo que nos importa: saber hasta donde poner el TP (el iman del precio).

METODOLOGIA:
  1. Velas 1H de Binance Futures (volumen en USDT).
  2. Por cada vela: posiciones abiertas al precio tipico (H+L+C)/3, peso = volumen.
  3. Por cada apalancamiento (10x, 25x, 50x, 100x):
       liquidacion LONG  = P * (1 - 1/L)
       liquidacion SHORT = P * (1 + 1/L)
  4. Se DESCARTAN los niveles ya barridos (si el precio ya paso por ahi despues,
     esas posiciones ya fueron liquidadas y no siguen ahi).
  5. Se agrupan en cubos de precio -> los cubos mas grandes son los CUMULOS.

USO:
  python liquidaciones.py BTCUSDT
  python liquidaciones.py ETHUSDT --horas 96
"""
import urllib.request, json, argparse, sys

BINANCE = "https://fapi.binance.com/fapi/v1/klines"
TIERS = (10, 25, 50, 100)          # apalancamientos tipicos (como los muestra Coinglass)
PESO_TIER = {10: 0.40, 25: 0.30, 50: 0.20, 100: 0.10}  # mas gente usa lev bajo


def _get(url):
    r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(r, timeout=20) as resp:
        return json.load(resp)


def velas(symbol="BTCUSDT", horas=72):
    try:
        d = _get(f"{BINANCE}?symbol={symbol}&interval=1h&limit={min(horas,1000)}")
    except Exception:
        return []
    out = []
    for k in d:
        try:
            out.append({"h": float(k[2]), "l": float(k[3]), "c": float(k[4]),
                        "q": float(k[7])})   # q = quote volume (USDT)
        except Exception:
            continue
    return out


def mapa(symbol="BTCUSDT", horas=72, bucket_pct=0.3):
    v = velas(symbol, horas)
    if len(v) < 10:
        return None
    precio = v[-1]["c"]
    n = len(v)
    # min de lows y max de highs POSTERIORES a cada vela (para saber si ya se barrio)
    suf_min = [0.0] * n
    suf_max = [0.0] * n
    m, M = float("inf"), 0.0
    for i in range(n - 1, -1, -1):
        suf_min[i] = m
        suf_max[i] = M
        m = min(m, v[i]["l"])
        M = max(M, v[i]["h"])

    cubos = {}   # (lado, bucket) -> volumen acumulado
    paso = precio * bucket_pct / 100.0
    for i, c in enumerate(v):
        p = (c["h"] + c["l"] + c["c"]) / 3.0
        vol = c["q"]
        if vol <= 0:
            continue
        for L in TIERS:
            w = vol * PESO_TIER[L]
            # LONGS abiertos aqui se liquidan abajo
            liq_l = p * (1 - 1.0 / L)
            if liq_l < suf_min[i] and liq_l < precio:      # aun no barrido y por debajo
                b = round(liq_l / paso)
                cubos[("long", b)] = cubos.get(("long", b), 0) + w
            # SHORTS abiertos aqui se liquidan arriba
            liq_s = p * (1 + 1.0 / L)
            if liq_s > suf_max[i] and liq_s > precio:      # aun no barrido y por encima
                b = round(liq_s / paso)
                cubos[("short", b)] = cubos.get(("short", b), 0) + w

    abajo = sorted([(b * paso, w) for (lado, b), w in cubos.items() if lado == "long"],
                   key=lambda x: -x[1])[:5]
    arriba = sorted([(b * paso, w) for (lado, b), w in cubos.items() if lado == "short"],
                    key=lambda x: -x[1])[:5]
    return {"symbol": symbol, "precio": precio,
            "abajo": sorted(abajo, key=lambda x: -x[0]),   # liquidaciones de LONGS
            "arriba": sorted(arriba, key=lambda x: x[0])}  # liquidaciones de SHORTS


def lineas(symbol="BTCUSDT", horas=72):
    m = mapa(symbol, horas)
    if not m:
        return ["  (sin datos de liquidaciones para %s)" % symbol]
    p = m["precio"]
    L = ["  Precio %s: %.6g   (cumulos estimados, modelo tipo Coinglass)" % (symbol, p)]
    if m["arriba"]:
        L.append("  ARRIBA (liq. de SHORTS - iman si sube -> TP de un LONG):")
        for lvl, w in m["arriba"][:3]:
            L.append("     %.6g  (+%.2f%%)  fuerza %.0fM" % (lvl, (lvl / p - 1) * 100, w / 1e6))
    if m["abajo"]:
        L.append("  ABAJO (liq. de LONGS - iman si baja -> TP de un SHORT):")
        for lvl, w in m["abajo"][:3]:
            L.append("     %.6g  (%.2f%%)  fuerza %.0fM" % (lvl, (lvl / p - 1) * 100, w / 1e6))
    L.append("  >> Pon el TP HASTA el cumulo mas fuerte, NO mas alla.")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="BTCUSDT")
    ap.add_argument("--horas", type=int, default=72)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 64)
    print("MAPA DE LIQUIDACIONES ESTIMADO | %s | %dh" % (a.symbol, a.horas))
    print("=" * 64)
    for x in lineas(a.symbol, a.horas):
        print(x)


if __name__ == "__main__":
    main()
