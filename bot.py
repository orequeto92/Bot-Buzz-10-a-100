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
SALDO_VIS = [CAPITAL]   # saldo mostrado en cabecera (lo actualiza saldo_actual)
ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado.json")
REPETIR_TRAS_H = 6


def tg(method, params):
    url = "https://api.telegram.org/bot%s/%s" % (TOKEN, method)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode(params).encode()), timeout=25) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # El cuerpo de la respuesta dice la causa real (token malo, chat no encontrado...)
        try:
            body = e.read().decode()[:300]
        except Exception:
            body = ""
        print("TG ERROR %s -> HTTP %s: %s" % (method, e.code, body))
        if e.code == 401:
            print("  >> TOKEN INVALIDO: revisa el secret TELEGRAM_TOKEN.")
        elif e.code == 400 and "chat not found" in body.lower():
            print("  >> CHAT_ID INCORRECTO o no pulsaste INICIAR en el bot.")
        return {}
    except Exception as e:
        print("TG error %s: %s" % (method, e)); return {}


def enviar(txt):
    if not TOKEN or not CHAT_ID:
        print("[SIN CREDENCIALES] Mensaje:\n" + txt); return
    tg("sendMessage", {"chat_id": CHAT_ID, "text": txt, "parse_mode": "HTML",
                       "disable_web_page_preview": "true"})


def cargar():
    try:
        e = json.load(open(ESTADO, encoding="utf-8"))
    except Exception as ex:
        # Si esto se ve en los logs, el anti-spam se acaba de resetear a cero:
        # estado.json no se pudo leer (JSON invalido, p.ej. por un conflicto de
        # git a medio resolver) y esta vuelta arranca sin memoria de alertas.
        print("AVISO: no se pudo leer estado.json (%s) -> arranco con estado vacio "
              "(anti-spam reseteado esta vuelta)." % ex)
        e = {"alertas": {}, "update_id": 0}
    e.setdefault("alertas", {}); e.setdefault("update_id", 0)
    return e


def saldo_actual(estado):
    """Saldo del reto: el guardado por /saldo manda; si no, el secret CAPITAL."""
    v = estado.get("saldo")
    try:
        val = float(v) if v is not None else CAPITAL
    except Exception:
        val = CAPITAL
    SALDO_VIS[0] = val
    return val


def guardar(e):
    json.dump(e, open(ESTADO, "w", encoding="utf-8"), indent=1)


def g(x, p=6):
    return "n/d" if x is None else ("%.*g" % (p, x))


def firma(s):
    # Solo simbolo + direccion: el precio de entrada oscila entre escaneos de 15 min
    # (redondeaba distinto con %.4g y burlaba el anti-spam) y la calidad A/B puede
    # cambiar por un umbral limite sin ser una operacion nueva. Misma moneda + mismo
    # lado dentro de las 6h = misma alerta, se calle.
    return hashlib.md5(("%s|%s" % (s["symbol"], s["lado"])).encode()).hexdigest()[:12]


def fmt_setup(s):
    em = "🟢 LONG" if s["lado"] == "long" else "🔴 SHORT"
    est = "⭐️" if s["calidad"] == "A+" else ("✅" if s["calidad"] == "A" else "👀")
    L = [f"{est} <b>{s['symbol'].replace('USDT','')} — {em}</b>  [{s['calidad']}]",
         f"Precio: <code>{g(s['precio'])}</code>", "",
         f"📍 Entrada: <code>{g(s['entrada'])}</code>",
         f"🛑 SL: <code>{g(s['sl'])}</code>  ({s['dist_pct']:.2f}%)",
         f"🎯 TP1: <code>{g(s['tp1'])}</code> (50% + BE)   🎯 TP2: <code>{g(s['tp2'])}</code>", "",
         f"⚙️ {s['lev']}x aislado · margen ${s['margen']:.2f}",
         f"⚖️ Riesgo -${s['riesgo_usd']:.2f} / +${s['neto']:.2f} neto (50% TP1 + 50% TP2)"]
    if s.get("liq_nivel"):
        L.append(f"💥 Cúmulo liquidaciones: <code>{g(s['liq_nivel'])}</code> "
                 f"({s.get('liq_dist_pct',0):+.1f}%, fuerza {s['liq_fuerza']/1e6:.0f}M) — imán del precio")
        if s.get("liq_aviso"):
            L.append("⚠️ <i>" + s["liq_aviso"] + "</i>")
    L.append("<b>Confluencias:</b> " + " · ".join(s["conf"]))
    return "\n".join(L)


def cabecera(r, ses):
    em = {"VERDE": "🟢", "AMARILLO": "🟡", "ROJO": "🔴"}[r["semaforo"]]
    L = [f"🕐 <b>{reglas.hora_medellin()} Medellín</b> — {ses[0]}",
         f"{em} Semáforo: <b>{r['semaforo']}</b> · Sesgo BTC: <b>{r['director'].upper()}</b>"]
    for m in (r["macro"] or [])[:2]:
        L.append(m.strip())
    if ses[2]:
        L.append("⚠️ <i>Fin de semana: el plan recomienda cautela.</i>")
    # el % se lee de reglas.py: si se cambia el riesgo, la cabecera no puede mentir
    L.append(f"💵 Reto: saldo ${SALDO_VIS[0]:.2f} · riesgo {reglas.RIESGO_PCT:g}% · freno 2 SL")
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
            res = reglas.escanear(saldo_actual(estado)); ses = reglas.sesion_actual()
            if res["setups"]:
                enviar(cabecera(res, ses) + "\n\n" + "\n\n➖➖➖\n\n".join(fmt_setup(s) for s in res["setups"]))
            else:
                enviar(cabecera(res, ses) + "\n\n😴 <b>Sin setups de calidad ahora.</b>\n<i>No operar también es ganar. Valida en el PC.</i>")
        elif txt.startswith("/saldo"):
            partes = txt.split()
            if len(partes) > 1:
                try:
                    nuevo = float(partes[1].replace(",", ".").replace("$", ""))
                    if nuevo <= 0 or nuevo > 100000:
                        enviar("❌ Saldo fuera de rango. Ejemplo: <code>/saldo 12.50</code>")
                    else:
                        anterior = saldo_actual(estado)
                        estado["saldo"] = nuevo
                        guardar(estado)
                        pct = (nuevo / 10.0 - 1) * 100
                        enviar("✅ <b>Saldo actualizado</b>\n\n"
                               "Antes: $%.2f  →  Ahora: <b>$%.2f</b>\n"
                               "Riesgo por trade (2%%): <b>$%.2f</b>\n"
                               "Meta de hoy (5.2%%): <b>$%.2f</b>\n"
                               "Progreso del reto: %.1f%% (objetivo $100)\n\n"
                               "<i>Los próximos setups se dimensionarán con este saldo.</i>"
                               % (anterior, nuevo, nuevo * 0.02, nuevo * 0.052, pct))
                except ValueError:
                    enviar("❌ No entendí el número. Ejemplo: <code>/saldo 12.50</code>")
            else:
                s_act = saldo_actual(estado)
                enviar("💵 <b>Saldo actual: $%.2f</b>\n"
                       "Riesgo 2%%: $%.2f · Meta diaria: $%.2f\n\n"
                       "Para cambiarlo: <code>/saldo 12.50</code>" % (s_act, s_act * 0.02, s_act * 0.052))
        elif txt.startswith("/liquidaciones") or txt.startswith("/liq"):
            try:
                import liquidaciones as _liq
                sym = "BTCUSDT"
                partes = txt.split()
                if len(partes) > 1:
                    sym = partes[1].upper().replace("USDT", "") + "USDT"
                lin = _liq.lineas(sym, 72)
                enviar("💥 <b>Mapa de liquidaciones (estimado)</b>\n<code>"
                       + "\n".join(x.strip() for x in lin)
                       + "</code>\n\n<i>Estimación con datos públicos de Binance, "
                         "no la data de Coinglass.</i>")
            except Exception as ex:
                enviar("❌ No pude calcular el mapa: %s" % ex)
        elif txt.startswith("/estado"):
            res = reglas.escanear(saldo_actual(estado)); ses = reglas.sesion_actual()
            enviar(cabecera(res, ses) + f"\n\nSetups activos: {len(res['setups'])}")


def main():
    estado = cargar()
    if "--test" in sys.argv:
        enviar("✅ Radar del reto conectado. Escaneando LBank."); return
    atender_comandos(estado)

    # Fuera de la ventana proactiva (o en finde) solo atendemos comandos y salimos:
    # los comandos como /oportunidades ya hacen su propio escaneo dentro de
    # atender_comandos, y asi no machacamos las APIs cada 15 min sin necesidad.
    ses = reglas.sesion_actual()
    if not (ses[1] and not ses[2]) and "--forzar" not in sys.argv:
        guardar(estado)
        print("Comandos atendidos. Sin escaneo proactivo: sesion '%s'%s."
              % (ses[0], " (fin de semana)" if ses[2] else ""))
        return

    SALDO = saldo_actual(estado)
    res = reglas.escanear(SALDO)
    ahora = time.time()
    nuevos = []
    for s in res["setups"]:
        # Las [B] TAMBIEN se avisan (cambio del 5-ago-2026). El backtest de 90 dias
        # mostro que son 61 de las 77 operaciones y aportan +11.0R de los +12.0R:
        # filtrarlas dejaba el sistema en +1.0R. No es que sean mejores que las [A]
        # (la diferencia es ruido, t=0.37), es que ahi esta casi toda la muestra.
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
        # BITACORA DE PAPEL: se anota cada señal enviada con sus niveles para poder
        # medir despues, con precios reales, si el sistema gana o pierde. No implica
        # operar: es el registro del forward-test. Lo persiste el workflow.
        hist = estado.setdefault("historial", [])
        for s in nuevos:
            hist.append({"t": int(ahora), "symbol": s["symbol"], "lado": s["lado"],
                         "calidad": s["calidad"], "entrada": s["entrada"], "sl": s["sl"],
                         "tp1": s["tp1"], "tp2": s["tp2"], "dist_pct": s["dist_pct"],
                         "adx": s.get("adx"), "di": s.get("di_favor")})
        del hist[:-300]                     # se guardan las ultimas 300 señales
    elif "--forzar" in sys.argv:
        enviar(cabecera(res, ses) + ("\n\n" + "\n\n➖➖➖\n\n".join(fmt_setup(s) for s in res["setups"]) if res["setups"] else "\n\n😴 Sin setups."))
    else:
        print("Sin alertas nuevas. Semaforo %s, sesion '%s', setups %d, proactivo=%s"
              % (res["semaforo"], ses[0], len(res["setups"]), proactivo_ok))
    guardar(estado)


if __name__ == "__main__":
    main()
