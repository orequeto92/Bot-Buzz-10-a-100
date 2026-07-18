# -*- coding: utf-8 -*-
"""
MACRO.PY - Contexto macro del mercado, GRATIS (antes era checklist manual en CMC).
 - Fear & Greed Index (alternative.me)
 - Dominancia BTC / ETH (CoinGecko global)
Interpretacion segun el video "Indice de sentimiento" del curso:
  miedo extremo = oportunidad de compra ; codicia extrema = riesgo de correccion.
"""
import urllib.request, json


def _get(url):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(r, timeout=15) as resp:
            return json.load(resp)
    except Exception:
        return None


def fear_greed():
    d = _get("https://api.alternative.me/fng/?limit=2")
    try:
        cur = int(d["data"][0]["value"])
        prev = int(d["data"][1]["value"]) if len(d["data"]) > 1 else cur
        return cur, prev
    except Exception:
        return None, None


def dominancia():
    d = _get("https://api.coingecko.com/api/v3/global")
    try:
        mc = d["data"]["market_cap_percentage"]
        return mc.get("btc"), mc.get("eth")
    except Exception:
        return None, None


def lineas():
    L = []
    fg, fgp = fear_greed()
    if fg is not None:
        if fg <= 25:
            lab = "MIEDO EXTREMO -> historicamente oportunidad de compra"
        elif fg <= 45:
            lab = "Miedo"
        elif fg < 55:
            lab = "Neutral"
        elif fg < 75:
            lab = "Codicia"
        else:
            lab = "CODICIA EXTREMA -> riesgo de correccion, cuidado con longs"
        tend = ""
        if fgp is not None:
            tend = " (ayer %d, %s)" % (fgp, "subiendo" if fg > fgp else "bajando" if fg < fgp else "igual")
        L.append("  Fear & Greed: %d/100 - %s%s" % (fg, lab, tend))
    btc, eth = dominancia()
    if btc is not None:
        L.append("  Dominancia BTC: %.1f%% | ETH: %.1f%%" % (btc, eth or 0))
        L.append("    (BTC.D subiendo => alts sufren; BTC.D bajando con BTC estable/subiendo => altseason)")
    return L


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("### CONTEXTO MACRO")
    for x in lineas():
        print(x)
