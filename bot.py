import requests
import time
import schedule
import os
import json
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OCORRENCIAS_URL = "https://api.fogos.pt/v2/incidents/active?all=1&concelho=Oliveira%20De%20Frades"

ocorrencias_enviadas = set()

def enviar_alerta(ocorrencia):
    mensagem = (
        f"*⚠️ Nova ocorrência!*\n\n"
        f"🕒 *Data:* {ocorrencia['date']} às {ocorrencia['hour']}\n"
        f"🚨 *Tipo:* {ocorrencia['natureza']}\n"
        f"📍 *Local:* {ocorrencia['concelho']} / {ocorrencia['localidade']}\n\n"
        f"📡 _Dados: Prociv / fogos.pt_\n"
        f"💬 Esta mensagem é automática | @bvofrades"
    )
    # Gerar URL dinâmico
    atualizacoes_url = f"https://bvofrades.pt/ocorrencias/?id={ocorrencia['id']}"

    # Inline button
    buttons = {
        "inline_keyboard": [
            [
                {"text": "📋 Atualizações", "url": atualizacoes_url}
            ]
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


def verificar_e_enviar_pir():
    try:
        DICO = "1810"
        res = requests.get("https://api.ipma.pt/open-data/forecast/meteorology/rcm/rcm-d0.json")
        dados = res.json()

        rcm = dados['local'][DICO]['data']['rcm']
        if rcm not in [4, 5]:
            print(f"[{datetime.now()}] RCM = {rcm} (sem envio)")
            return

        nivel = "Muito Elevado" if rcm == 4 else "Máximo"
        imagem = "https://i.imgur.com/DIZs1sq.png" if rcm == 4 else "https://i.imgur.com/GL2ir8l.png"

        legenda = (
    f"🔥 *Perigo de Incêndio Rural*\n"
    f"📍 Oliveira de Frades\n"
    f"⚠️ Nível: *{nivel}*\n"
    f"📡 _Fonte: IPMA (www.ipma.pt)_\n\n"
    f"🚫 Não faça uso do fogo, seja responsável!\n"
    f"🧯 A PREVENÇÃO COMEÇA EM SI. Em caso de incêndio ligue 112!"
)


        payload = {
            'chat_id': CHAT_ID,
            'photo': imagem,
            'caption': legenda,
            'parse_mode': 'Markdown'
        }

        telegram_res = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data=payload)

        print(telegram_res.text)  # Debug do erro

        if telegram_res.status_code == 200:
            print(f"✅ PIR enviado com sucesso! ({nivel})")
        else:
            print(f"❌ Erro ao enviar PIR. Status: {telegram_res.status_code}")

    except Exception as e:
        print(f"❌ Erro ao verificar PIR: {e}")

# 🔥 ALERTA FAKE ANTES DO LOOP
ocorrencia_teste = {
    "id": "20250959975",
    "date": datetime.now().strftime("%d-%m-%Y"),
    "hour": datetime.now().strftime("%H:%M"),
    "natureza": "Simulação de Alerta 🔥",
    "concelho": "Oliveira De Frades",
    "localidade": "Quartel BVOF"
}
enviar_alerta(ocorrencia_teste)

# Agendamento
schedule.every(2).minutes.do(verificar_ocorrencias)
schedule.every().day.at("09:30").do(verificar_e_enviar_pir)

print("🕒 Agendamentos ativos: Ocorrências a cada 2 min | PIR às 10h")

# Execução forçada para teste
verificar_e_enviar_pir()

while True:
    schedule.run_pending()
    print(f"⏳ A correr... {datetime.now()}")
    time.sleep(30)
