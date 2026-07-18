# -*- coding: utf-8 -*-
"""
PROBAR_LOCAL.PY - Prueba el bot en tu PC antes de subirlo a la nube.

1) Abre 'credenciales.txt' y pega tu TELEGRAM_TOKEN y TELEGRAM_CHAT_ID.
2) Ejecuta:   python probar_local.py
   Te llegara un mensaje de prueba + el informe de mercado a Telegram.

Opciones:
   python probar_local.py --solo-test     (solo el mensaje de conexion)
   python probar_local.py --escanear      (modo real: solo avisa si hay setup nuevo)
"""
import os, sys, subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))
CRED = os.path.join(AQUI, "credenciales.txt")


def cargar():
    if not os.path.exists(CRED):
        sys.exit("No encuentro credenciales.txt junto a este script.")
    env = dict(os.environ)
    faltan = []
    for linea in open(CRED, encoding="utf-8"):
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        k, v = k.strip(), v.strip()
        if v.startswith("PEGA_AQUI"):
            faltan.append(k)
        env[k] = v
    if faltan:
        sys.exit("Todavia no has rellenado en credenciales.txt: " + ", ".join(faltan))
    return env


def main():
    env = cargar()
    env["PYTHONIOENCODING"] = "utf-8"
    print("Credenciales cargadas. Capital: $%s" % env.get("CAPITAL", "300"))

    if "--escanear" in sys.argv:
        args = []
    elif "--solo-test" in sys.argv:
        args = ["--test"]
    else:
        args = ["--forzar"]   # por defecto: manda el informe aunque no haya setup

    if args != ["--test"]:
        print("Enviando mensaje de conexion...")
        subprocess.run([sys.executable, os.path.join(AQUI, "bot.py"), "--test"],
                       env=env, cwd=AQUI)

    print("Escaneando el mercado y enviando informe...")
    r = subprocess.run([sys.executable, os.path.join(AQUI, "bot.py")] + args,
                       env=env, cwd=AQUI)
    print("Listo. Revisa tu Telegram." if r.returncode == 0 else "Termino con errores.")


if __name__ == "__main__":
    main()
