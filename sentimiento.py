# -*- coding: utf-8 -*-
"""
SENTIMIENTO.PY - Datos de derivados globales GRATIS (lo que Coinglass cobra a $35/mes).

Fuentes publicas (sin API key):
  - Binance Futures: ratio Long/Short (global y de top traders) + historial de Open Interest.
  - Bitget: ratio de cuentas y de posiciones long/short.
El sentimiento de derivados es GLOBAL, no de un exchange concreto: por eso sirve aunque
operemos en LBank. El propio video de CriptoBuzz lo dice: Coinglass agrega Binance/OKX,
y Binance es el mayor liquidador.

UMBRALES (transcritos del video "Coinglass" del curso, min 15:38 y 25:32):
  - L/S ratio >= 3.0   -> exceso de LONGS  -> riesgo de liquidaciones bajistas. NO abrir longs.
  - L/S ratio <= 0.5   -> exceso de SHORTS -> posible squeeze alcista. NO abrir shorts.
  - L/S ratio > 1      -> inclinacion alcista (sesgo long, sin dominio de cortos).
  - Funding muy positivo -> euforia -> riesgo de correccion.
  - Funding muy negativo -> miedo   -> riesgo de rebote (oportunidad de compra).
  - OI subiendo >3%    -> tendencia definida, entra dinero nuevo (PDF Coinglass del curso).
  - Precio baja + OI cae >10% en 24h -> CASCADA de liquidaciones. Fuera.

USO:
  python sentimiento.py            # BTC
  python sentimiento.py ETHUSDT
"""
import urllib.request, urllib.parse, json, sys, argparse

UA = {"User-Agent": "Mozilla/5.0"}
BINANCE = "https://fapi.binance.com"
BITGET = "https://api.bitget.com"


def _get(url):
    try:
        r = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(r, timeout=15) as resp:
            return json.load(resp)
    except Exception:
        return None


def ls_binance(symbol="BTCUSDT", period="1h"):
    """Ratio long/short de cuentas (todo el mercado) y de top traders."""
    out = {}
    d = _get(f"{BINANCE}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period={period}&limit=2")
    if d:
        try:
            out["global"] = float(d[-1]["longShortRatio"])
            out["global_long_pct"] = float(d[-1]["longAccount"]) * 100
        except Exception:
            pass
    d = _get(f"{BINANCE}/futures/data/topLongShortPositionRatio?symbol={symbol}&period={period}&limit=2")
    if d:
        try:
            out["top"] = float(d[-1]["longShortRatio"])
        except Exception:
            pass
    return out


def ls_bitget(symbol="BTCUSDT"):
    d = _get(f"{BITGET}/api/v2/mix/market/account-long-short?symbol={symbol}&productType=usdt-futures&period=1h")
    try:
        return float((d["data"])[-1]["longShortAccountRatio"])
    except Exception:
        return None


def oi_binance(symbol="BTCUSDT"):
    """Historial de Open Interest -> variacion 1h / 4h / 24h."""
    d = _get(f"{BINANCE}/futures/data/openInterestHist?symbol={symbol}&period=1h&limit=25")
    if not d or len(d) < 2:
        return {}
    try:
        vals = [float(x["sumOpenInterestValue"]) for x in d]
    except Exception:
        return {}
    now = vals[-1]
    def chg(n):
        if len(vals) > n:
            prev = vals[-1 - n]
            return (now - prev) / prev * 100 if prev else None
        return None
    return {"oi_usd": now, "chg1h": chg(1), "chg4h": chg(4), "chg24h": chg(24)}


def precio_chg24h(symbol="BTCUSDT"):
    d = _get(f"{BINANCE}/fapi/v1/ticker/24hr?symbol={symbol}")
    try:
        return float(d["priceChangePercent"])
    except Exception:
        return None


def analizar(symbol="BTCUSDT", funding=None):
    """Devuelve (lineas, avisos, score_riesgo, sesgo)."""
    ls = ls_binance(symbol)
    lsb = ls_bitget(symbol)
    oi = oi_binance(symbol)
    pchg = precio_chg24h(symbol)

    L, avisos, score, sesgo = [], [], 0, None

    # --- Long/Short ratio ---
    r = ls.get("global")
    if r is not None:
        etiqueta = ""
        if r >= 3.0:
            etiqueta = " >> EXCESO DE LONGS: riesgo de liquidaciones bajistas. NO abrir longs."
            score += 2; sesgo = "bajista"; avisos.append("L/S %.2f >= 3: exceso de longs" % r)
        elif r <= 0.5:
            etiqueta = " >> EXCESO DE SHORTS: posible squeeze alcista. NO abrir shorts."
            score += 2; sesgo = "alcista"; avisos.append("L/S %.2f <= 0.5: exceso de shorts" % r)
        elif r > 1:
            etiqueta = " (inclinacion alcista, sin dominio de cortos)"
        else:
            etiqueta = " (inclinacion bajista)"
        L.append("  L/S ratio global (Binance): %.2f  [longs %.1f%%]%s"
                 % (r, ls.get("global_long_pct", 0), etiqueta))
    if ls.get("top") is not None:
        L.append("  L/S top traders (Binance):  %.2f" % ls["top"])
        if r and abs(ls["top"] - r) > 0.5:
            L.append("     ojo: los top traders NO estan posicionados como la masa.")
    if lsb is not None:
        L.append("  L/S cuentas (Bitget):       %.2f" % lsb)

    # --- Open Interest ---
    if oi:
        L.append("  Open Interest: $%.2fB  |  1h %+.2f%%  4h %+.2f%%  24h %+.2f%%"
                 % (oi["oi_usd"] / 1e9,
                    oi.get("chg1h") or 0, oi.get("chg4h") or 0, oi.get("chg24h") or 0))
        c24 = oi.get("chg24h")
        if c24 is not None and pchg is not None:
            if pchg < 0 and c24 < -10:
                L.append("     >> CASCADA: precio %.1f%% + OI %.1f%% en 24h. Reduce exposicion." % (pchg, c24))
                score += 3; avisos.append("Cascada de liquidaciones (precio y OI cayendo)")
            elif c24 > 3:
                L.append("     >> OI +%.1f%%: entra dinero nuevo, tendencia definida." % c24)
            elif c24 < -3:
                L.append("     >> OI %.1f%%: se cierran posiciones, tendencia perdiendo fuerza." % c24)

    # --- Funding (lo pasa el llamador; interpretacion del video) ---
    if funding is not None:
        f = funding * 100
        if f > 0.05:
            L.append("  Funding %+.4f%%/8h >> EUFORIA: riesgo de correccion. Cuidado con longs." % f)
            score += 2; avisos.append("Funding en euforia")
        elif f < -0.05:
            L.append("  Funding %+.4f%%/8h >> MIEDO: riesgo de rebote. Oportunidad de compra." % f)
            score += 1; avisos.append("Funding en miedo (posible rebote)")
        else:
            L.append("  Funding %+.4f%%/8h (neutro)" % f)

    if not L:
        L.append("  (sin datos de sentimiento disponibles)")
    return L, avisos, score, sesgo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="BTCUSDT")
    a = ap.parse_args()
    print("=" * 68)
    print("SENTIMIENTO DE DERIVADOS (global) | %s" % a.symbol)
    print("=" * 68)
    L, avisos, score, sesgo = analizar(a.symbol)
    for x in L:
        print(x)
    print("-" * 68)
    print("Score de riesgo aportado: %d  |  Sesgo contrarian: %s" % (score, sesgo or "ninguno"))


if __name__ == "__main__":
    main()
