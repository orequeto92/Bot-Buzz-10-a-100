# -*- coding: utf-8 -*-
"""
BOT.PY - Radar de Telegram del RETO $10->$100 (LBank).
Escanea la watchlist del reto y avisa de setups A/A+ al movil. NO ejecuta ordenes.
Brahian valida en el PC antes de operar. Todo con APIs publicas (LBank/Binance/CoinGecko).

Variables de entorno (GitHub Secrets):
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID   (obligatorias)
  CAPITAL     saldo actual del reto en USDT (default 10)

Uso:
  python bot.py            -> escanea; avisa setups nuevos (proactivo solo en ventana buena) + atiende comandos
  python bot.py --test     -> mensaje de prueba
  python bot.py --forzar   -> manda el informe completo aunque no haya setup
"""
import os, sys, json, time, hashlib, urllib.request, urllib.parse
import reglas

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
CAPITAL = float(os.environ.get("CAPITAL", "10") or 10)
ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado.json")
REPETIR_TRAS_H = 6


def tg(method, params):
    url = "https://api.telegram.org/bot%s/%s" % (TOKEN, method)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode(params).encode()), timeout=25) as r:
            return json.load(r)
    except Exception as e:
        print("TG error %s: %s" % (method, e)); return {}


def enviar(txt):
    if not TOKEN or not CHAT_ID:
        print("[SIN CREDENCIALES] Mensaje:\n" + txt); return
    tg("sendMessage", {"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML",
                       "disable_web_page_preview": "true"})


def cargar():
    try:
        return json.load(open(ESTADO, encoding="utf-8"))
    except Exception:
        return {"alertas": {}, "update_id": 0}


def guardar(e):
    json.dump(e, open(ESTADO, "w", encoding="utf-8"), indent=1)


def g(x, p=6):
    return "n/d" if x is None else ("%.*g" % (p, x))


def firma(s):
    return hashlib.md5(("%s|%s|%s|%.4g" % (s["symbol"], s["lado"], s["calidad"], s["entrada"])).encode()).hexdigest()[:12]


def fmt_setup(s):
    em = "🟢 LONG" if s["lado"] == "long" else "🔴 SHORT"
    est = "⭐️" if s["calidad"] == "A+" else ("✅" if s["calidad"] == "A" else "👀")
    L = [f"{est} <b>{s['symbol'].replace('USDT','')} — {em}</b>  [{s['calidad']}]",
         f"Precio: <code>{g(s['precio'])}</code>", "",
         f"📍 Entrada: <code>{g(s['entrada'])}</code>",
         f"🛑 SL: <code>{g(s['sl'])}</code>  ({s['dist_pct']:.2f}%)",
         f"🎯 TP1: <code>{g(s['tp1'])}</code> (50% + BE)   🎯 TP2: <code>{g(s['tp2'])}</code>", "",
         f"⚙️ {s['lev']}x aislado · margen ${s['margen']:.2f}",
         f"⚖️ Riesgo -${s['riesgo_usd']:.2f} / +${s['neto_tp2']:.2f} neto (R:R 1:2)",
         "<b>Confluencias:</b> " + " · ".join(s["conf"])]
    return "\n".join(L)


def cabecera(r, ses):
    em = {"VERDE": "🟢", "AMARILLO": "🟡", "ROJO": "🔴"}[r["semaforo"]]
    L = [f"🕐 <b>{reglas.hora_medellin()} Medellín</b> — {ses[0]}",
         f"{em} Semáforo: <b>{r['semaforo']}</b> · Sesgo BTC: <b>{r['director'].upper()}</b>"]
    for m in (r["macro"] or [])[:2]:
        L.append(m.strip())
    if ses[2]:
        L.append("⚠️ <i>Fin de semana: el plan recomienda cautela.</i>")
    L.append(f"💵 Reto: saldo ${CAPITAL:.2f} · riesgo 2% · freno 2 SL")
    return "\n".join(L)


def atender_comandos(estado):
    if not TOKEN:
        return
    r = tg("getUpdates", {"offset": estado.get("update_id", 0) + 1, "timeout": 0})
    for upd in (r.get("result") or []):
        estado["update_id"] = max(estado.get("update_id", 0), upd.get("update_id", 0))
        msg = upd.get("message") or {}
        txt = (msg.get("text") or "").lower().strip()
        chat = str((msg.get("chat") or {}).get("id", ""))
        if CHAT_ID and chat != str(CHAT_ID):
            continue
        if txt.startswith("/start"):
            enviar("👋 <b>Radar del Reto $10→$100 activo.</b>\n\nEscaneo LBank y te aviso de setups A/A+.\n/oportunidades — análisis ahora\n/estado — contexto\n\n<i>Solo soy un radar: valida en el PC antes de operar. No ejecuto órdenes.</i>")
        elif txt.startswith("/oportunidades"):
            res = reglas.escanear(CAPITAL); ses = reglas.sesion_actual()
            if res["setups"]:
                enviar(cabecera(res, ses) + "\n\n" + "\n\n➖➖➖\n\n".join(fmt_setup(s) for s in res["setups"]))
            else:
                enviar(cabecera(res, ses) + "\n\n😴 <b>Sin setups de calidad ahora.</b>\n<i>No operar también es ganar. Valida en el PC.</i>")
        elif txt.startswith("/estado"):
            res = reglas.escanear(CAPITAL); ses = reglas.sesion_actual()
            enviar(cabecera(res, ses) + f"\n\nSetups activos: {len(res['setups'])}")


def main():
    estado = cargar()
    if "--test" in sys.argv:
        enviar("✅ Radar del reto conectado. Escaneando LBank."); return
    atender_comandos(estado)

    res = reglas.escanear(CAPITAL)
    ses = reglas.sesion_actual()
    ahora = time.time()
    nuevos = []
    for s in res["setups"]:
        if s["calidad"] == "B":
            continue  # proactivo solo A/A+
        f = firma(s)
        if estado["alertas"].get(f) and ahora - estado["alertas"][f] < REPETIR_TRAS_H * 3600:
            continue
        estado["alertas"][f] = ahora
        nuevos.append(s)
    estado["alertas"] = {k: v for k, v in estado["alertas"].items() if ahora - v < 48 * 3600}

    # proactivo: solo en ventana buena y entre semana (radar limpio, sin ruido de zona muerta)
    proactivo_ok = ses[1] and not ses[2]

    if nuevos and (proactivo_ok or "--forzar" in sys.argv):
        enviar("🔔 <b>OPORTUNIDAD DETECTADA</b>\n\n" + cabecera(res, ses) + "\n\n" +
               "\n\n➖➖➖\n\n".join(fmt_setup(s) for s in nuevos))
        print("Enviadas %d alertas" % len(nuevos))
    elif "--forzar" in sys.argv:
        enviar(cabecera(res, ses) + ("\n\n" + "\n\n➖➖➖\n\n".join(fmt_setup(s) for s in res["setups"]) if res["setups"] else "\n\n😴 Sin setups."))
    else:
        print("Sin alertas nuevas. Semaforo %s, sesion '%s', setups %d, proactivo=%s"
              % (res["semaforo"], ses[0], len(res["setups"]), proactivo_ok))
    guardar(estado)


if __name__ == "__main__":
    main()
