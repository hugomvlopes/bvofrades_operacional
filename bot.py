import requests
import time
import schedule
import os
import json
import csv
from datetime import datetime
from math import radians, cos, sin, asin, sqrt

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OCORRENCIAS_URL = "https://api.fogos.pt/v2/incidents/active?all=1"
OPENWEATHER_API_KEY = "d3ca2afa41223a9d5ac00a5c53576bd9"
GOOGLE_MAPS_API_KEY = "AIzaSyCWB5tAKnFKHIlgulZwtasNHSKSIwwdDxg"

ocorrencias_enviadas = set()


def haversine(lat1, lon1, lat2, lon2):
    """Calcula a distância em km entre dois pontos"""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


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


def carregar_pontos_agua_csv():
    """Carrega pontos de água do CSV online"""
    try:
        url = "https://gist.githubusercontent.com/hugomvlopes/d50eb30cff380c73f09579789046e190/raw/redehidra.csv"
        response = requests.get(url)
        if response.status_code == 200:
            decoded = response.content.decode('utf-8').splitlines()
            reader = csv.DictReader(decoded)
            pontos = []
            for row in reader:
                pontos.append({
                    "nome": f"Hidrante {row['id_hidra']}",
                    "tipo": row['tipo_hidra'],
                    "lat": float(row['latitude']),
                    "lon": float(row['longitude'])
                })
            print(f"✅ Pontos de água carregados: {len(pontos)}")
            return pontos
        else:
            print(f"❌ Erro ao carregar CSV: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Erro ao carregar pontos de água CSV: {e}")
        return []


def ponto_agua_proximo(lat, lon, pontos_agua):
    """Encontra o ponto de água mais próximo da ocorrência"""
    menor_dist = float("inf")
    ponto_mais_proximo = None

    for ponto in pontos_agua:
        ponto_lat = ponto['lat']
        ponto_lon = ponto['lon']
        dist = haversine(lat, lon, ponto_lat, ponto_lon)
        if dist < menor_dist:
            menor_dist = dist
            ponto_mais_proximo = {
                "nome": ponto['nome'],
                "tipo": ponto['tipo'],
                "lat": ponto_lat,
                "lon": ponto_lon,
                "distancia": round(menor_dist, 2)
            }
    return ponto_mais_proximo


def gerar_mapa(lat, lon, ponto_lat, ponto_lon, user_lat=None, user_lon=None):
    """Gera URL do mapa satélite com ocorrência, ponto de água e user"""
    base_url = (
        "https://maps.googleapis.com/maps/api/staticmap"
        f"?size=600x400&maptype=satellite"
        f"&markers=color:red|label:O|{lat},{lon}"
        f"&markers=color:blue|label:P|{ponto_lat},{ponto_lon}"
    )
    if user_lat and user_lon:
        base_url += f"&markers=color:green|label:U|{user_lat},{user_lon}"
    base_url += f"&key={GOOGLE_MAPS_API_KEY}"
    return base_url


def enviar_alerta(ocorrencia, user_location=None):
    lat = ocorrencia.get("lat")
    lon = ocorrencia.get("lng")

    try:
        lat = float(lat) if lat else None
        lon = float(lon) if lon else None
    except (TypeError, ValueError):
        lat = lon = None

    if not lat or not lon:
        print("⚠️ Sem lat/lon no JSON, sem dados adicionais.")
        meteo_texto = "\n⚠️ *Meteo:* Sem coordenadas disponíveis"
        ponto_texto = "\n⚠️ *Ponto de Água:* Sem coordenadas disponíveis"
        mapa_url = None
    else:
        meteo_texto = get_weather(lat, lon)
        pontos_agua = carregar_pontos_agua_csv()
        ponto = ponto_agua_proximo(lat, lon, pontos_agua) if pontos_agua else None

        if ponto:
            ponto_texto = (
                f"\n💧 *Ponto de Água mais próximo:*\n"
                f"📌 {ponto['nome']} ({ponto['tipo']})\n"
                f"📍 Distância: {ponto['distancia']} km\n"
                f"🌐 [Ver no mapa](https://www.google.com/maps?q={ponto['lat']},{ponto['lon']})"
            )
            user_lat = user_location['latitude'] if user_location else None
            user_lon = user_location['longitude'] if user_location else None
            mapa_url = gerar_mapa(lat, lon, ponto['lat'], ponto['lon'], user_lat, user_lon)
        else:
            ponto_texto = "\n⚠️ *Ponto de Água:* Nenhum encontrado"
            mapa_url = None

    mensagem = (
        f"*⚠️ Nova ocorrência!*\n\n"
        f"🕒 *Data:* {ocorrencia['date']} às {ocorrencia['hour']}\n"
        f"🚨 *Tipo:* {ocorrencia['natureza']}\n"
        f"📍 *Local:* {ocorrencia['concelho']} / {ocorrencia['localidade']}\n"
        f"{meteo_texto}\n"
        f"{ponto_texto}\n\n"
        f"📡 _Dados: Prociv / fogos.pt_\n"
        f"💬 Esta mensagem é automática | @bvofrades"
    )

    atualizacoes_url = f"https://bvofrades.pt/ocorrencias/?id={ocorrencia['id']}"

    buttons = {
        "inline_keyboard": [
            [{"text": "📋 Atualizações", "url": atualizacoes_url}]
        ]
    }

    if mapa_url:
        photo_payload = {
            'chat_id': CHAT_ID,
            'photo': mapa_url,
            'caption': mensagem,
            'parse_mode': 'Markdown'
        }
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data=photo_payload
        )
    else:
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


schedule.every(2).minutes.do(verificar_ocorrencias)

print("🕒 Agendamentos ativos: Ocorrências a cada 2 min")

while True:
    schedule.run_pending()
    print(f"⏳ A correr... {datetime.now()}")
    time.sleep(30)
