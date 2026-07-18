# 📡 Radar del Reto $10→$100 — Bot de Telegram (LBank)

Escanea el mercado de futuros de **LBank** desde la nube (GitHub Actions, **gratis, 24/7**) y te avisa al **móvil** cuando aparece un setup A/A+ del reto. Aplica el mismo sistema que `/oportunidades` en el PC: sesgo director de BTC, zonas SMC (Premium/Discount), sentimiento de derivados, macro (Fear&Greed + dominancia), patrones de vela y sizing del reto (2% riesgo, saldo $10).

> ⚠️ **Es un RADAR, no un piloto automático.** No ejecuta órdenes ni usa tu API key. Te avisa; **tú validas en el PC** (donde está mi criterio contextual completo) y colocas la orden manualmente en LBank.

## Qué te llega al móvil
```
🕐 08:00 Medellín — VENTANA DORADA (overlap Londres-NY)
🟢 Semáforo: VERDE · Sesgo BTC: ALCISTA
Fear & Greed: 25/100 - MIEDO EXTREMO
✅ ETH — 🟢 LONG [A]
📍 Entrada 1842.6 · 🛑 SL 1812 (1.66%) · 🎯 TP1 1873 · TP2 1904
⚙️ 20x · margen $0.60 · Riesgo -$0.20 / +$0.39
Confluencias: tendencia 4H+1H · divergencia · vela envolvente · zona Discount
```
Comandos: `/oportunidades` (análisis al momento), `/estado`, `/start`.

## Cuándo avisa
- **Proactivo (sin que preguntes):** solo en tus **ventanas buenas** y entre semana → sesión asiática (7pm–12am Medellín) y ventana dorada (7–10am Medellín). Así no te llega ruido de las zonas muertas.
- **A demanda:** escríbele `/oportunidades` cuando quieras (responde en el siguiente ciclo, ≤30 min).
- **Anti-spam:** no repite la misma alerta antes de 6 h.

## Instalación (15 min, gratis)

### 1. Crear el bot
1. En Telegram habla con **@BotFather** → `/newbot` → nombre y usuario. Copia el **TOKEN**.
2. Abre tu bot y pulsa **INICIAR** (`/start`) — si no, no puede escribirte.

### 2. Tu Chat ID
1. Habla con **@userinfobot** → copia tu **Id** (un número).

### 3. Subir a GitHub
1. Crea repo nuevo en [github.com](https://github.com) — **Público** (minutos ilimitados gratis).
2. *Add file → Upload files* → sube TODO el contenido de esta carpeta (incluida `.github/`). Commit.
   `credenciales.txt` no se sube (está en `.gitignore`): en la nube las claves van en Secrets.

### 4. Secretos
Settings → Secrets and variables → Actions → New repository secret:

| Nombre | Valor |
|--------|-------|
| `TELEGRAM_TOKEN` | el token de BotFather |
| `TELEGRAM_CHAT_ID` | tu chat id |
| `CAPITAL` | tu saldo del reto (ej. `10`) — **actualízalo cuando cambie** |

### 5. Encender
Pestaña **Actions** → habilitar workflows → *"Radar del Reto"* → **Run workflow**.
A partir de ahí corre solo en tus ventanas buenas, de lunes a viernes.

**Probar en el PC antes de subir:** rellena `credenciales.txt` y ejecuta `python probar_local.py`.

## Ajustes
- **Horas:** edita el `cron` en `.github/workflows/scan.yml` (está en UTC; Medellín = UTC−5).
- **Saldo del reto:** el secret `CAPITAL`. Cámbialo cuando el reto avance.
- **Sensibilidad:** en `reglas.py` (`calidad = "A+" if score >= 7 ...`).

## Limitaciones honestas
- Reglas fijas: no tiene mi juicio contextual (por eso **valida en el PC**).
- El mapa de liquidaciones (Coinglass) sigue siendo manual — el bot no lo incluye.
- GitHub desactiva el cron si el repo pasa 60 días sin actividad → entra de vez en cuando.
- Velas de LBank spot (los majors ≈ perp); precio/funding de futuros LBank.

> Educativo, no asesoría financiera. El apalancamiento puede liquidar tu capital.
