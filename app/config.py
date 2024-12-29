class Config:
    """
    Класс конфигурации
    """
    URL = "127.0.0.1"  # Адрес сервера в Uvicorn
    SECRET_KEY = "Cheese"  # Ключ для шифрования сессии
    UPLOAD_DIR = "uploads"  # Папка для загрузки книг
    DB_URL = "sqlite:///./database.db"  # URL базы данных
    DB_SERVER_PORT = 8001  # Порт сервера базы данных
    DB_API_URL = f"http://{URL}:{DB_SERVER_PORT}"  # URL API базы данных
    MAIN_PORT = 8000  # Порт сервера


config = Config
