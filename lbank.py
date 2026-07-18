# -*- coding: utf-8 -*-
"""
Capa de datos para el exchange LBank (API publica, sin API key).

- Velas: SPOT USDT (kline.do). Devuelve [ts, o, h, l, c, vol] igual que Bitget,
  asi que ta.compute() funciona sin cambios.
- Precio de futuros + funding: endpoint marketData de futuros (SwapU).
- Open Interest: NO disponible en la API publica de LBank -> None.
- SOL no cotiza en spot LBank: tendra precio/funding de futuros pero sin velas.
"""
import json, time, urllib.request, urllib.parse, urllib.error

SPOT_BASE = "https://api.lbank.info"
FUT_MARKET = "https://lbkperp.lbank.com/cfd/openApi/v1/pub/marketData?productGroup=SwapU"

# nuestro nombre -> par spot LBank
def to_spot(symbol):        # "BTCUSDT" -> "btc_usdt"
    s = symbol.upper().replace("USDT", "")
    return s.lower() + "_usdt"

# nuestro TF -> tipo de vela LBank y segundos por vela
TF = {
    "15m": ("minute15", 900),
    "1H":  ("hour1", 3600),
    "4H":  ("hour4", 14400),
    "1D":  ("day1", 86400),
}

_FUT_CACHE = {"ts": 0, "data": {}}


def _get(url, timeout=20):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1.2)
    return None


def candles(symbol, tf, limit=300):
    """Velas spot LBank -> [ts_seg, open, high, low, close, vol] (mas antigua primero)."""
    if tf not in TF:
        return []
    ktype, secs = TF[tf]
    start = int(time.time()) - limit * secs
    params = urllib.parse.urlencode({
        "symbol": to_spot(symbol), "size": str(min(limit, 2000)),
        "type": ktype, "time": str(start)})
    d = _get(SPOT_BASE + "/v2/kline.do?" + params)
    if not d or d.get("error_code") not in (0, "0"):
        return []
    # data ya viene como [ts,o,h,l,c,vol]; garantizamos floats
    out = []
    for row in d.get("data", []):
        if len(row) >= 6:
            out.append([int(row[0])] + [float(x) for x in row[1:6]])
    return out


def _load_futures():
    """Descarga (con cache de 30s) el marketData de TODOS los futuros SwapU."""
    if time.time() - _FUT_CACHE["ts"] < 30 and _FUT_CACHE["data"]:
        return _FUT_CACHE["data"]
    d = _get(FUT_MARKET)
    idx = {}
    if d and isinstance(d.get("data"), list):
        for r in d["data"]:
            idx[r.get("symbol")] = r
    _FUT_CACHE["ts"] = time.time()
    _FUT_CACHE["data"] = idx
    return idx


def futures_info(symbol):
    """Precio de futuros, funding y cambio 24h aprox para 'BTCUSDT'."""
    r = _load_futures().get(symbol.upper())
    if not r:
        return {}
    try:
        last = float(r.get("lastPrice"))
    except Exception:
        last = None
    try:
        op = float(r.get("openPrice"))
        chg = (last - op) / op if (last and op) else None
    except Exception:
        chg = None
    try:
        fund = float(r.get("fundingRate"))
    except Exception:
        fund = None
    return {"lastPrice": last, "change24h": chg, "fundingRate": fund,
            "high": r.get("highestPrice"), "low": r.get("lowestPrice"),
            "volume": r.get("volume")}


def snapshot(symbol, tfs=("1D", "4H", "1H", "15m"), limit=300):
    fi = futures_info(symbol)
    out = {"symbol": symbol,
           "ticker": {"lastPr": fi.get("lastPrice"), "change24h": fi.get("change24h")},
           "funding": fi.get("fundingRate"),
           "oi": None,                    # LBank no expone OI publico
           "candles": {}}
    for tf in tfs:
        out["candles"][tf] = candles(symbol, tf, limit)
    return out
