# -*- coding: utf-8 -*-
"""
Motor de Analisis Tecnico - Sistema CriptoBuzz / Salario Infinito
Python puro, sin dependencias. Expone compute() (metricas estructuradas) y
format_summary() (texto compacto). Tambien funciona como CLI sobre un JSON.
"""
import sys, json, argparse

def ema(values, period):
    if len(values) < period:
        return [None] * len(values)
    k = 2.0 / (period + 1)
    out = [None] * len(values)
    sma = sum(values[:period]) / period
    out[period - 1] = sma
    prev = sma
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out

def rsi(closes, period=14):
    out = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0)); losses.append(max(-ch, 0.0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    def rv(g, l):
        if l == 0: return 100.0
        return 100.0 - (100.0 / (1 + g / l))
    out[period] = rv(avg_g, avg_l)
    for i in range(period + 1, len(closes)):
        avg_g = (avg_g * (period - 1) + gains[i - 1]) / period
        avg_l = (avg_l * (period - 1) + losses[i - 1]) / period
        out[i] = rv(avg_g, avg_l)
    return out

def atr(highs, lows, closes, period=14):
    trs = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])))
    if len(trs) < period: return None
    a = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        a = (a * (period - 1) + trs[i]) / period
    return a

def atr_series(highs, lows, closes, period=14):
    """ATR completo (lista), necesario para medir compresion de volatilidad."""
    n = len(closes)
    out = [None] * n
    if n < period + 1:
        return out
    trs = [highs[0] - lows[0]]
    for i in range(1, n):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])))
    a = sum(trs[:period]) / period
    out[period - 1] = a
    for i in range(period, n):
        a = (a * (period - 1) + trs[i]) / period
        out[i] = a
    return out

def pivots(highs, lows, k=3):
    sh, sl = [], []
    for i in range(k, len(highs) - k):
        if highs[i] == max(highs[i-k:i+k+1]) and highs[i] > highs[i-1]:
            sh.append((i, highs[i]))
        if lows[i] == min(lows[i-k:i+k+1]) and lows[i] < lows[i-1]:
            sl.append((i, lows[i]))
    return sh, sl

def classify_structure(sh, sl):
    last_h = sh[-2:] if len(sh) >= 2 else []
    last_l = sl[-2:] if len(sl) >= 2 else []
    hh = len(last_h) == 2 and last_h[-1][1] > last_h[0][1]
    lh = len(last_h) == 2 and last_h[-1][1] < last_h[0][1]
    hl = len(last_l) == 2 and last_l[-1][1] > last_l[0][1]
    ll = len(last_l) == 2 and last_l[-1][1] < last_l[0][1]
    if hh and hl: trend = "ALCISTA"
    elif lh and ll: trend = "BAJISTA"
    elif hh and ll: trend = "EXPANSION"
    elif lh and hl: trend = "CONTRACCION"
    else: trend = "RANGO"
    tags = [t for t,c in [("HH",hh),("HL",hl),("LH",lh),("LL",ll)] if c]
    return trend, tags

def adx_dmi(highs, lows, closes, period=14):
    """ADX + DMI (Wilder). Devuelve (adx, di_pos, di_neg) del ultimo valor.
      - ADX mide la FUERZA de la tendencia, sin decir la direccion. >25 = tendencia
        establecida; <20 = rango. Es el filtro estandar de la industria y el que
        usa el screener del video de CriptoBuzz.
      - DI+ / DI- dan la direccion: DI+ por encima = compradores mandando.
    Se calculan con suavizado de Wilder (no EMA), como en TradingView."""
    n = len(closes)
    if n < period * 2 + 1:
        return None, None, None
    tr, dm_p, dm_n = [], [], []
    for i in range(1, n):
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])))
        up, dn = highs[i] - highs[i-1], lows[i-1] - lows[i]
        dm_p.append(up if (up > dn and up > 0) else 0.0)
        dm_n.append(dn if (dn > up and dn > 0) else 0.0)
    # suavizado de Wilder: primer valor = suma, luego resta la media y suma el nuevo
    def wilder(v):
        s = sum(v[:period])
        out = [s]
        for x in v[period:]:
            s = s - s / period + x
            out.append(s)
        return out
    atr_w, dmp_w, dmn_w = wilder(tr), wilder(dm_p), wilder(dm_n)
    dxs = []
    for a, p, m in zip(atr_w, dmp_w, dmn_w):
        if a <= 0:
            continue
        dip, din = 100.0 * p / a, 100.0 * m / a
        s = dip + din
        dxs.append(100.0 * abs(dip - din) / s if s > 0 else 0.0)
    if len(dxs) < period:
        return None, None, None
    adx = sum(dxs[:period]) / period
    for x in dxs[period:]:
        adx = (adx * (period - 1) + x) / period
    a = atr_w[-1]
    if a <= 0:
        return None, None, None
    return adx, 100.0 * dmp_w[-1] / a, 100.0 * dmn_w[-1] / a


def retroceso_fibo(res_zonas, sop_zonas, entrada, lado):
    """% de retroceso de Fibonacci al que corresponde 'entrada' dentro del ultimo
    impulso: 0% = en el extremo del impulso, 100% = en su origen.
      - 38,2%-61,8% es la "zona dorada" (el retroceso sano dentro de la tendencia).
      - Por encima del 61,8% ya NO es un retroceso: la tendencia se esta rompiendo.
    Medido sobre 90 dias, las entradas con retroceso >61,8% dan -0,625R de media
    frente a +0,265R del resto (t=-2,08), y pierden en las dos mitades del periodo."""
    hi = max([p for p, _ in (res_zonas or [])], default=None)
    lo = min([p for p, _ in (sop_zonas or [])], default=None)
    if hi is None or lo is None or hi <= lo:
        return None
    if lado == "long":
        return (hi - entrada) / (hi - lo) * 100.0
    return (entrada - lo) / (hi - lo) * 100.0


def eficiencia(closes, n=24):
    """Ratio de eficiencia de Kaufman sobre las ultimas n velas:
        |cambio neto| / recorrido total
    Va de 0 a 1. Cerca de 1 = el precio avanza en linea recta (TENDENCIA, terreno
    favorable para entrar en retrocesos). Cerca de 0 = mucho movimiento y ningun
    avance (LATIGAZO/RANGO, donde una estrategia de retroceso se desangra)."""
    if len(closes) < n + 1:
        return None
    tramo = closes[-(n + 1):]
    neto = abs(tramo[-1] - tramo[0])
    recorrido = sum(abs(tramo[i] - tramo[i - 1]) for i in range(1, len(tramo)))
    if recorrido <= 0:
        return None
    return neto / recorrido


def zonas_por_toques(pivotes, tol):
    """Agrupa niveles de pivote cercanos (dentro de 'tol') en ZONAS y cuenta cuantas
    veces reacciono el precio ahi. Una zona vale mas cuantos mas toques tiene: el
    mentor lo resume como 'esta zona ha tenido muchos toques y esta ninguno, para
    nosotros este soporte es mas importante'. Devuelve [(nivel_medio, n_toques), ...]."""
    if not pivotes:
        return []
    ps = sorted(p for (_, p) in pivotes)
    grupos = []
    actual = [ps[0]]
    for p in ps[1:]:
        # Se compara contra el MINIMO del grupo, no contra el ultimo punto: si se
        # encadenase punto a punto, una fila de pivotes poco separados acabaria
        # fundiendose en una "zona" enorme y el nivel medio no significaria nada.
        if p - actual[0] <= tol:
            actual.append(p)
        else:
            grupos.append(actual); actual = [p]
    grupos.append(actual)
    zonas = [(sum(g) / len(g), len(g)) for g in grupos]
    zonas.sort(key=lambda z: -z[1])          # mas tocadas primero
    return zonas

def detect_divergence(closes, rsis, sh, sl):
    out = []
    if len(sh) >= 2:
        (i1,p1),(i2,p2) = sh[-2], sh[-1]
        if rsis[i1] and rsis[i2] and p2 > p1 and rsis[i2] < rsis[i1]:
            out.append(f"BAJISTA (precio HH, RSI {rsis[i1]:.0f}->{rsis[i2]:.0f})")
    if len(sl) >= 2:
        (i1,p1),(i2,p2) = sl[-2], sl[-1]
        if rsis[i1] and rsis[i2] and p2 < p1 and rsis[i2] > rsis[i1]:
            out.append(f"ALCISTA (precio LL, RSI {rsis[i1]:.0f}->{rsis[i2]:.0f})")
    return out

def detect_fvg(highs, lows, closes, lookback=40):
    n = len(closes); start = max(2, n - lookback); fvgs = []; last = closes[-1]
    for i in range(start, n):
        if highs[i-2] < lows[i] and last > lows[i]:
            fvgs.append(("alcista", highs[i-2], lows[i]))
        if lows[i-2] > highs[i] and last < highs[i]:
            fvgs.append(("bajista", highs[i], lows[i-2]))
    fvgs.sort(key=lambda f: abs(((f[1]+f[2])/2) - last))
    return fvgs[:3]

def patron_vela(o, h, l, c):
    """Detecta el patron de la ULTIMA vela (diapositiva 'Patrones de velas relevantes').
    Devuelve (nombre, sesgo) o (None, None)."""
    n = len(c)
    if n < 2:
        return None, None
    O, H, L, C = o[-1], h[-1], l[-1], c[-1]
    po, pc = o[-2], c[-2]
    cuerpo = abs(C - O)
    rango = H - L
    if rango <= 0:
        return None, None
    mecha_sup = H - max(O, C)
    mecha_inf = min(O, C) - L
    # Envolvente (engulfing): cuerpo actual envuelve al anterior y color opuesto
    if C > O and pc < po and C >= po and O <= pc and cuerpo > abs(pc - po):
        return "ENVOLVENTE alcista", "alcista"
    if C < O and pc > po and C <= po and O >= pc and cuerpo > abs(pc - po):
        return "ENVOLVENTE bajista", "bajista"
    # Doji: apertura ~ cierre
    if cuerpo <= 0.1 * rango:
        return "DOJI (indecision)", "neutral"
    # Hammer / Pin bar: mecha inferior larga, cuerpo pequeno arriba
    if mecha_inf >= 2 * cuerpo and mecha_sup <= cuerpo:
        return "HAMMER/PIN alcista", "alcista"
    # Shooting star: mecha superior larga
    if mecha_sup >= 2 * cuerpo and mecha_inf <= cuerpo:
        return "SHOOTING STAR bajista", "bajista"
    return None, None


def compute(symbol, tf, candles):
    candles = [c for c in candles if c and len(c) >= 5]
    candles.sort(key=lambda c: int(c[0]))
    o = [float(c[1]) for c in candles]
    h = [float(c[2]) for c in candles]; l = [float(c[3]) for c in candles]
    c = [float(c[4]) for c in candles]
    v = [float(x[5]) for x in candles] if len(candles[0]) > 5 else [0]*len(candles)
    n = len(c); price = c[-1]
    e13, e50, e200 = ema(c,13), ema(c,50), ema(c,200)
    rsis = rsi(c,14); a = atr(h,l,c,14)
    atrs = atr_series(h,l,c,14)
    sh, sl = pivots(h,l,3)
    trend, tags = classify_structure(sh, sl)
    divs = detect_divergence(c, rsis, sh, sl)
    fvgs = detect_fvg(h,l,c,40)
    bias = "neutral"
    if e50[-1] and e200[-1]:
        if price > e50[-1] > e200[-1]: bias = "alcista"
        elif price < e50[-1] < e200[-1]: bias = "bajista"
        elif min(e50[-1],e200[-1]) < price < max(e50[-1],e200[-1]): bias = "entre-EMAs(no-operar)"
    res = sorted([p for (_,p) in sh if p > price])[:3]
    sop = sorted([p for (_,p) in sl if p < price], reverse=True)[:3]
    vol_avg = sum(v[-20:]) / min(20, len(v)) if v else 0

    _adx, _dip, _din = adx_dmi(h, l, c, 14)

    # Zonas por nº de toques: agrupa pivotes cercanos y cuenta reacciones.
    # tolerancia = 0.6 x ATR (o 0.4% del precio si no hay ATR).
    tol = (a * 0.6) if a else (price * 0.004)
    res_zonas = [(lvl, n_t) for (lvl, n_t) in zonas_por_toques(sh, tol) if lvl > price][:3]
    sop_zonas = [(lvl, n_t) for (lvl, n_t) in zonas_por_toques(sl, tol) if lvl < price][:3]

    # Compresion de volatilidad: ATR actual vs su media reciente. Solo INFORMATIVO
    # (no filtra setups): comprimido = puede estar preparando un breakout, vigilar.
    compresion = None
    validos = [x for x in atrs[-50:] if x]
    if a and len(validos) >= 20:
        media = sum(validos) / len(validos)
        if media > 0:
            ratio = a / media
            compresion = ("COMPRIMIDO" if ratio < 0.7 else
                          "EXPANDIDO" if ratio > 1.5 else "NORMAL")

    # Premium / Equilibrio / Discount (concepto SMC que usan los mentores del curso):
    # rango de negociacion = ultimos swings; comprar en Discount, vender en Premium.
    zona, eq, pos_pct = None, None, None
    hi_pool = [p for (_, p) in sh[-3:]]
    lo_pool = [p for (_, p) in sl[-3:]]
    if hi_pool and lo_pool:
        rango_hi, rango_lo = max(hi_pool), min(lo_pool)
        if rango_hi > rango_lo:
            eq = (rango_hi + rango_lo) / 2.0
            pos_pct = (price - rango_lo) / (rango_hi - rango_lo) * 100
            if pos_pct >= 75:
                zona = "PREMIUM-alto"
            elif pos_pct >= 55:
                zona = "PREMIUM"
            elif pos_pct <= 25:
                zona = "DISCOUNT-bajo"
            elif pos_pct <= 45:
                zona = "DISCOUNT"
            else:
                zona = "EQUILIBRIO"
    return {
        "symbol": symbol, "tf": tf, "n": n, "price": price,
        "ema13": e13[-1], "ema50": e50[-1], "ema200": e200[-1],
        "rsi": rsis[-1], "atr": a, "atr_pct": (a/price*100) if a else None,
        "compresion": compresion,
        "er": eficiencia(c, 24),            # regimen a corto (1 dia en 1H)
        "er_largo": eficiencia(c, 168),     # regimen a 7 dias en 1H (separa mejor)
        "adx": _adx, "di_pos": _dip, "di_neg": _din,
        "trend": trend, "tags": tags, "bias": bias,
        "divergences": divs, "fvgs": fvgs,
        "resistances": res, "supports": sop,
        "res_zonas": res_zonas, "sop_zonas": sop_zonas,
        "vol_last": v[-1] if v else 0, "vol_avg20": vol_avg,
        "vol_spike": bool(vol_avg and v and v[-1] > 2*vol_avg),
        "zona": zona, "eq": eq, "pos_pct": pos_pct,
        "patron": patron_vela(o, h, l, c),
    }

def g(x, p=6):
    return "n/d" if x is None else f"{x:.{p}g}"

def format_summary(m):
    L = []
    L.append(f"--- {m['symbol']} [{m['tf']}] {m['n']} velas | precio {g(m['price'])} ---")
    rsi_tag = ""
    if m['rsi'] is not None:
        rsi_tag = " SOBRECOMPRA" if m['rsi']>70 else " SOBREVENTA" if m['rsi']<30 else ""
    L.append(f"  EMA13 {g(m['ema13'])} | EMA50 {g(m['ema50'])} | EMA200 {g(m['ema200'])} | RSI {g(m['rsi'],3)}{rsi_tag}")
    L.append(f"  Sesgo:{m['bias']} | Estructura:{m['trend']} ({'/'.join(m['tags']) or '-'}) | ATR {g(m['atr'])} ({g(m['atr_pct'],3)}%) {m.get('compresion') or ''}")
    if m.get("compresion") == "COMPRIMIDO":
        L.append("  *** VOLATILIDAD COMPRIMIDA: posible breakout preparandose, vigilar de cerca")
    def _z(zonas):
        # nivel xN, donde N = nº de toques (una zona con mas toques es mas fuerte)
        return ", ".join(("%s x%d" % (g(lvl), nt)) if nt > 1 else g(lvl) for lvl, nt in zonas) or "-"
    if m.get("res_zonas") is not None or m.get("sop_zonas") is not None:
        L.append(f"  Resist(toques): {_z(m.get('res_zonas') or [])}   Soportes(toques): {_z(m.get('sop_zonas') or [])}")
    else:
        L.append(f"  Resist: {', '.join(g(x) for x in m['resistances']) or '-'}   Soportes: {', '.join(g(x) for x in m['supports']) or '-'}")
    if m.get("zona"):
        tag = ""
        if "DISCOUNT" in m["zona"]: tag = " [zona de COMPRA]"
        elif "PREMIUM" in m["zona"]: tag = " [zona de VENTA]"
        L.append(f"  Rango SMC: {m['zona']} ({g(m['pos_pct'],3)}% del rango) | Equilibrio {g(m['eq'])}{tag}")
    if m['divergences']: L.append("  DIVERGENCIA " + " | ".join(m['divergences']))
    if m['fvgs']:
        L.append("  FVG: " + " ; ".join(f"{t} {g(lo)}-{g(hi)}" for t,lo,hi in m['fvgs']))
    if m['vol_spike']: L.append("  *** PICO DE VOLUMEN (>2x prom20)")
    if m.get("patron") and m["patron"][0]:
        L.append(f"  Vela actual: {m['patron'][0]}")
    return "\n".join(L)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path"); ap.add_argument("--symbol"); ap.add_argument("--tf")
    args = ap.parse_args()
    raw = json.load(open(args.path, encoding="utf-8"))
    if isinstance(raw, dict) and "candles" in raw:
        candles = raw["candles"]; symbol = raw.get("symbol", args.symbol); tf = raw.get("tf", args.tf)
    elif isinstance(raw, dict) and "data" in raw:
        d = raw["data"]; candles = d["data"] if isinstance(d, dict) and "data" in d else d
        symbol = args.symbol; tf = args.tf
    else:
        candles = raw; symbol = args.symbol; tf = args.tf
    print(format_summary(compute(symbol or "?", tf or "?", candles)))

if __name__ == "__main__":
    main()
