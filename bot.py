import requests
import time
import schedule
import os
import json
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OCORRENCIAS_URL = "https://api.fogos.pt/v2/incidents/active?all=1"
OPENWEATHER_API_KEY = "01b51257a7270ea6df00f03338671a70"

ocorrencias_enviadas = set()


def get_weather(lat, lon):
    """Vai buscar dados meteorológicos ao OpenWeather"""
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&units=metric&appid={OPENWEATHER_API_KEY}"
        )
        print(f"🌐 Meteo API chamada: {url}")
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
            return "\n⚠️ *Meteo:* Dados indisponíveis"
    except Exception as e:
        print(f"❌ Erro ao obter meteo: {e}")
        return "\n⚠️ *Meteo:* Erro ao obter dados"


def deg_to_compass(deg):
    """Converte graus em direção cardinal"""
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    ix = int((deg / 45) + 0.5) % 8
    return dirs[ix]


def geocode_local(localidade, concelho):
    """Tenta obter lat/lng a partir de localidade + concelho"""
    try:
        query = f"{localidade}, {concelho}, Portugal"
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 1}
        headers = {"User-Agent": "BVOFradesBot/1.0"}
        print(f"📍 Geocoding '{query}'...")
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200 and response.json():
            result = response.json()[0]
            lat = float(result['lat'])
            lon = float(result['lon'])
            print(f"✅ Geocoding → lat={lat}, lon={lon}")
            return lat, lon
        else:
            print(f"❌ Geocoding falhou para '{query}'")
            return None, None
    except Exception as e:
        print(f"❌ Erro no geocoding: {e}")
        return None, None


def enviar_alerta(ocorrencia):
    lat = ocorrencia.get("lat")
    lon = ocorrencia.get("lng")

    # Tentativa de converter coordenadas do JSON
    try:
        lat = float(lat) if lat else None
        lon = float(lon) if lon else None
    except (TypeError, ValueError):
        lat = lon = None

    # Se não houver coordenadas, tenta geocoding
    if not lat or not lon:
        print("⚠️ Sem lat/lon no JSON, a tentar geocoding...")
        lat, lon = geocode_local(ocorrencia['localidade'], ocorrencia['concelho'])

    # Meteo (se conseguirmos coordenadas)
    meteo_texto = get_weather(lat, lon) if lat and lon else "\n⚠️ *Meteo:* Sem coordenadas disponíveis"

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
