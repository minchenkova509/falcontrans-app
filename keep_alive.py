import requests
import time
import os

def ping_app():
    """Пингует приложение каждые 10 минут для поддержания активности"""
    url = os.environ.get('APP_URL', 'https://falcontrans-app.onrender.com')
    
    try:
        response = requests.get(url, timeout=30)
        print(f"✅ Пинг успешен: {response.status_code} - {time.strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"❌ Ошибка пинга: {e} - {time.strftime('%H:%M:%S')}")

if __name__ == "__main__":
    print("🚀 Запуск keep-alive скрипта...")
    print(f"📡 URL: {os.environ.get('APP_URL', 'https://falcontrans-app.onrender.com')}")
    
    while True:
        ping_app()
        # Ждем 10 минут (600 секунд)
        time.sleep(600) 