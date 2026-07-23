# -*- coding: utf-8 -*-
"""
REGLAS.PY (bot LBank/reto) - Motor de deteccion de setups para el radar de Telegram.
Replica la logica del sistema /oportunidades: sesgo director BTC, zonas SMC,
sentimiento de derivados, macro, patrones de vela y sizing del reto $10->$100.
NO ejecuta ordenes: solo detecta y describe.
"""
import time
import lbank, ta, sentimiento, macro
try:
    import liquidaciones
except Exception:
    liquidaciones = None

WATCHLIST = ["ETHUSDT", "SOLUSDT", "ADAUSDT", "HYPEUSDT", "WLDUSDT", "LDOUSDT", "VIRTUALUSDT", "INJUSDT", "HBARUSDT", "DOTUSDT", "ARBUSDT", "BCHUSDT", "ANKRUSDT", "PEPEUSDT"]
TFS = ("4H", "1H", "15m")
MAJORS_ORDEN_GRANDE = {"BTC", "BNB"}  # no dimensionan con $10

RIESGO_PCT = 2.0
SL_MIN_PCT = 1.5
SL_MAX_PCT = 4.0
FEE_LADO = 0.0006
PCT_OPERATIVO = 0.75
RR = 2.0
LEV_MAX = {"ETH": 25}  # resto 20


# ---------------------------------------------------------------- sesiones (Medellin UTC-5)
def sesion_actual():
    """Devuelve (etiqueta, es_buena, es_finde) segun la hora UTC."""
    t = time.gmtime()
    h = t.tm_hour
    finde = t.tm_wday >= 5
    # ventana dorada overlap Londres-NY: 12-15 UTC | asiatica cripto: 0-6 UTC
    if 12 <= h < 15:
        return "VENTANA DORADA (overlap Londres-NY)", True, finde
    if 0 <= h < 6:
        return "Sesion asiatica (cripto)", True, finde
    if 15 <= h < 18:
        return "ZONA MUERTA (break post-overlap)", False, finde
    if 20 <= h or h < 0:
        return "ZONA MUERTA (NY cerrada)", False, finde
    return "Sesion secundaria", False, finde


def hora_medellin():
    t = time.gmtime()
    return "%02d:%02d" % ((t.tm_hour - 5) % 24, t.tm_min)


# ---------------------------------------------------------------- sesgo director BTC
def director_btc(btc_tfm):
    b4 = (btc_tfm.get("4H") or {}).get("bias", "neutral")
    b1 = (btc_tfm.get("1H") or {}).get("bias", "neutral")
    if b4 == "alcista" and b1 in ("alcista", "neutral"):
        return "alcista"
    if b4 == "bajista" and b1 in ("bajista", "neutral"):
        return "bajista"
    return "neutral"


# ---------------------------------------------------------------- evaluar un activo
def evaluar(symbol, tfm, funding, director, semaforo_color):
    m4, m1, m15 = tfm.get("4H"), tfm.get("1H"), tfm.get("15m")
    if not (m4 and m1 and m15):
        return None
    # 1) tendencia 4H clara
    if m4["bias"].startswith("entre") or m4["bias"] == "neutral":
        return None
    lado = "long" if m4["bias"] == "alcista" else "short"
    # 2) a favor del sesgo director de BTC (si BTC tiene sesgo)
    if director != "neutral":
        if (director == "alcista" and lado != "long") or (director == "bajista" and lado != "short"):
            return None
    # 3) 1H no debe estar entre EMAs
    if m1["bias"].startswith("entre"):
        return None
    precio = m15["price"]
    atr15 = m15["atr"] or 0
    rsi15 = m15["rsi"]
    if not atr15 or rsi15 is None:
        return None
    # 4) anti-FOMO
    if lado == "long" and rsi15 > 68:
        return None
    if lado == "short" and rsi15 < 32:
        return None
    # 5) zona SMC: long solo en discount/equilibrio, short solo en premium/equilibrio
    z = (m15.get("zona") or "")
    if lado == "long" and "PREMIUM" in z:
        return None
    if lado == "short" and "DISCOUNT" in z:
        return None
    # 6) entrada EMA13 15m, SL estructural ancho
    entrada = m15["ema13"] or precio
    if lado == "long":
        sops = [s for s in (m15["supports"] + m1["supports"]) if s < entrada]
        if not sops:
            return None
        sl = min(sops) - 0.3 * atr15
    else:
        ress = [r for r in (m15["resistances"] + m1["resistances"]) if r > entrada]
        if not ress:
            return None
        sl = max(ress) + 0.3 * atr15
    dist_pct = abs(entrada - sl) / entrada * 100
    if not (SL_MIN_PCT <= dist_pct <= SL_MAX_PCT):
        return None
    dist = abs(entrada - sl)
    tp1 = entrada + dist if lado == "long" else entrada - dist
    tp2 = entrada + dist * RR if lado == "long" else entrada - dist * RR
    # 7) confluencias
    score, conf = 2, ["Tendencia 4H+1H %s" % m4["bias"]]
    if (lado == "long" and m1["trend"] == "ALCISTA") or (lado == "short" and m1["trend"] == "BAJISTA"):
        score += 1; conf.append("Estructura 1H alineada")
    quiere = "ALCISTA" if lado == "long" else "BAJISTA"
    for tf in ("15m", "1H"):
        for d in (tfm[tf]["divergences"] if tfm.get(tf) else []):
            if d.startswith(quiere):
                score += 1; conf.append("Divergencia RSI %s" % quiere.lower()); break
        else:
            continue
        break
    pat = m15.get("patron")
    if pat and pat[0] and pat[1] == ("alcista" if lado == "long" else "bajista"):
        score += 1; conf.append("Vela %s" % pat[0])
    if "DISCOUNT" in z and lado == "long":
        score += 1; conf.append("Zona SMC Discount (compra)")
    if "PREMIUM" in z and lado == "short":
        score += 1; conf.append("Zona SMC Premium (venta)")
    if m15.get("vol_spike"):
        score += 1; conf.append("Pico de volumen")
    f = funding or 0
    if lado == "long" and f < -0.0003:
        score += 1; conf.append("Funding negativo (squeeze alcista)")
    elif lado == "short" and f > 0.0003:
        score += 1; conf.append("Funding positivo (longs cargados)")

    calidad = "A+" if score >= 7 else ("A" if score >= 5 else ("B" if score >= 4 else None))
    if calidad is None:
        return None
    if semaforo_color == "ROJO":
        return None
    return {"symbol": symbol, "lado": lado, "calidad": calidad, "score": score,
            "precio": precio, "entrada": entrada, "sl": sl, "tp1": tp1, "tp2": tp2,
            "dist_pct": dist_pct, "conf": conf, "funding": funding}


# ---------------------------------------------------------------- mapa de liquidaciones
def contexto_liquidaciones(s):
    """Busca el cumulo de liquidaciones en la direccion del trade y valida el TP2.
    Regla del curso: el TP va HASTA el cumulo (iman del precio), nunca mas alla."""
    if not liquidaciones:
        return s
    try:
        m = liquidaciones.mapa(s["symbol"], horas=72)
    except Exception:
        m = None
    if not m:
        return s
    entrada, tp2 = s["entrada"], s["tp2"]
    # De los cumulos mas fuertes, nos interesa el MAS CERCANO en la direccion del
    # trade: es el primer iman que encontrara el precio.
    if s["lado"] == "long":
        cands = [(lvl, w) for lvl, w in m["arriba"] if lvl > entrada]
        cands.sort(key=lambda x: x[0] - entrada)        # el mas cercano primero
        supera = lambda lvl: tp2 > lvl
    else:
        cands = [(lvl, w) for lvl, w in m["abajo"] if lvl < entrada]
        cands.sort(key=lambda x: entrada - x[0])
        supera = lambda lvl: tp2 < lvl
    if cands:
        lvl, w = cands[0]
        s["liq_nivel"], s["liq_fuerza"] = lvl, w
        s["liq_dist_pct"] = abs(lvl - entrada) / entrada * 100
        s["liq_aviso"] = ("TP2 %.6g pasa del cúmulo en %.6g — plantéate cerrar ahí"
                          % (tp2, lvl)) if supera(lvl) else None
    return s


# ---------------------------------------------------------------- sizing reto
def tamano(s, saldo):
    asset = s["symbol"].replace("USDT", "")
    lev_max = LEV_MAX.get(asset, 20)
    riesgo_usd = saldo * RIESGO_PCT / 100.0
    notional = riesgo_usd / (s["dist_pct"] / 100.0)
    lev_seguro = max(1, int((100.0 / s["dist_pct"]) / 3.0))
    lev = max(1, min(lev_max, lev_seguro))
    margen = notional / lev
    fees = notional * FEE_LADO * 2
    neto_tp2 = notional * (s["dist_pct"] * 2) / 100.0 - fees
    s.update({"riesgo_usd": riesgo_usd, "notional": notional, "lev": lev,
              "margen": margen, "neto_tp2": neto_tp2})
    return s


# ---------------------------------------------------------------- escaneo completo
def escanear(saldo=10.0):
    btc_snap = lbank.snapshot("BTCUSDT", TFS, 300)
    btc_tfm = {tf: ta.compute("BTCUSDT", tf, btc_snap["candles"][tf])
               for tf in TFS if len(btc_snap["candles"].get(tf) or []) >= 60}
    director = director_btc(btc_tfm)

    # semaforo: funding + sentimiento
    color, flags = "VERDE", []
    try:
        _, avisos, sc, _ = sentimiento.analizar("BTCUSDT", btc_snap["funding"])
        flags += avisos
        if sc >= 4:
            color = "ROJO"
        elif sc >= 2:
            color = "AMARILLO"
    except Exception:
        pass

    setups = []
    for sym in WATCHLIST:
        try:
            snap = lbank.snapshot(sym, TFS, 300)
            tfm = {tf: ta.compute(sym, tf, snap["candles"][tf])
                   for tf in TFS if len(snap["candles"].get(tf) or []) >= 60}
            s = evaluar(sym, tfm, snap["funding"], director, color)
            if s:
                setups.append(tamano(contexto_liquidaciones(s), saldo))
        except Exception:
            continue
    orden = {"A+": 0, "A": 1, "B": 2}
    setups.sort(key=lambda x: (orden.get(x["calidad"], 9), -x["score"]))
    return {"director": director, "semaforo": color, "flags": flags,
            "macro": macro.lineas(), "setups": setups}
