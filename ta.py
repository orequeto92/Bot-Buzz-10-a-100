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
        "trend": trend, "tags": tags, "bias": bias,
        "divergences": divs, "fvgs": fvgs,
        "resistances": res, "supports": sop,
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
    L.append(f"  Sesgo:{m['bias']} | Estructura:{m['trend']} ({'/'.join(m['tags']) or '-'}) | ATR {g(m['atr'])} ({g(m['atr_pct'],3)}%)")
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
