import requests
import time
import schedule
import os
import json
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OCORRENCIAS_URL = "https://api.fogos.pt/v2/incidents/active?all=1"
OPENWEATHER_API_KEY = "d3ca2afa41223a9d5ac00a5c53576bd9"

ocorrencias_enviadas = set()


def get_weather(lat, lon):
    """Vai buscar dados meteorológicos ao OpenWeather"""
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&units=metric&appid={OPENWEATHER_API_KEY}"
        )
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            temp = data['main']['temp']
            wind_speed = data['wind']['speed']
            wind_deg = data['wind']['deg']
            humidity = data['main']['humidity']
            wind_dir = deg_to_compass(wind_deg)
            return f"\n🌡️ *Temperatura:* {temp}°C" \
                   f"\n💨 *Vento:* {wind_speed} km/h ({wind_dir})" \
                   f"\n💧 *Humidade:* {humidity}%"
        else:
            print(f"❌ OpenWeather error {response.status_code}")
            return ""
    except Exception as e:
        print(f"❌ Erro ao obter meteo: {e}")
        return ""


def deg_to_compass(deg):
    """Converte graus em direção cardinal"""
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    ix = int((deg / 45) + 0.5) % 8
    return dirs[ix]


def enviar_alerta(ocorrencia):
    lat = ocorrencia.get("lat")
    lon = ocorrencia.get("lng")
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        print("⚠️ Coordenadas inválidas, não adiciona meteo.")
        lat = lon = None

    meteo_texto = get_weather(lat, lon) if lat and lon else ""

    mensagem = (
        f"*⚠️ Nova ocorrência!*\n\n"
        f"🕒 *Data:* {ocorrencia['date']} às {ocorrencia['hour']}\n"
        f"🚨 *Tipo:* {ocorrencia['natureza']}\n"
        f"📍 *Local:* {ocorrencia['concelho']} / {ocorrencia['localidade']}\n"
        f"{meteo_texto}\n\n"
        f"📡 _Dados: Prociv / fogos.pt_\n"
        f"💬 Esta mensagem é automática | @bvofrades"
    )

    atualizacoes_url = f"https://bvofrades.pt/ocorrencias/?id={ocorrencia['id']}"

    buttons = {
        "inline_keyboard": [
            [{"text": "📋 Atualizações", "url": atualizacoes_url}]
        ]
    }

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": mensagem,
            "parse_mode": "Markdown",
            "reply_markup": json.dumps(buttons)
        }
    )

    print(f"✅ Alerta enviado! Status: {response.status_code}")


def verificar_ocorrencias():
    try:
        res = requests.get(OCORRENCIAS_URL)
        dados = res.json().get("data", [])
        print(f"🔍 Ocorrências recebidas: {len(dados)}")

        for ocorrencia in dados:
            if ocorrencia["id"] in ocorrencias_enviadas:
                continue

            enviar_alerta(ocorrencia)
            ocorrencias_enviadas.add(ocorrencia["id"])

    except Exception as e:
        print(f"❌ Erro ao verificar ocorrências: {e}")

# Agendamento
schedule.every(2).minutes.do(verificar_ocorrencias)

print("🕒 Agendamentos ativos: Ocorrências a cada 2 min")

while True:
    schedule.run_pending()
    print(f"⏳ A correr... {datetime.now()}")
    time.sleep(30)
