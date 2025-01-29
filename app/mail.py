import os
import smtplib
import redis
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Настройки Redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_CHANNEL = os.getenv("REDIS_CHANNEL", "mail_queue")

# Настройки SMTP
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")

# Подключение к Redis
redis_client = redis.StrictRedis(
    host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def send_email(to_email, subject, message):
    """Функция отправки письма через SMTP"""
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, to_email, msg.as_string())
        print(f"✅ Письмо отправлено {to_email}")
    except Exception as e:
        print(f"❌ Ошибка при отправке письма: {e}")


def process_mail_queue():
    """Ожидание сообщений в канале Redis"""
    print("📬 Сервис почты запущен и слушает канал Redis...")
    pubsub = redis_client.pubsub()
    pubsub.subscribe(REDIS_CHANNEL)

    for message in pubsub.listen():
        if message["type"] == "message":
            try:
                email_data = json.loads(message["data"])
                send_email(
                    email_data["to"], email_data["subject"], email_data["message"])
            except Exception as e:
                print(f"❌ Ошибка обработки сообщения: {e}")


if __name__ == "__main__":
    process_mail_queue()
