import pytest
import httpx
from faker import Faker

# Загружаем URL из окружения
from dotenv import load_dotenv
import os

load_dotenv()
TEST_URL = os.getenv("TEST_URL", 'http://localhost:8000')

faker = Faker()


def test_user_flow():
    """Тест полного цикла пользователя: регистрация, операции с книгой, выход."""
    # Регистрация пользователя
    login = faker.user_name()
    email = faker.email()
    password = faker.password()
    registration_payload = {
        "login": login,
        "email": email,
        "password": password
    }
    reg_response = httpx.post(
        f"{TEST_URL}/registration", data=registration_payload)
    assert reg_response.status_code == 303, "Ошибка при регистрации пользователя"
    print("Registration response HTML:", reg_response.text)

    # Логин
    login_payload = {
        "login": login,
        "password": password
    }
    login_response = httpx.post(
        f"{TEST_URL}/login", data=login_payload, follow_redirects=False)
    assert login_response.status_code == 303, "Ошибка при логине"
    assert "user_id" in login_response.cookies, "Куки user_id отсутствуют после логина"
    cookies = login_response.cookies
    print("Login response HTML:", login_response.text)

    # Загрузка книги
    files = {
        "title": (None, "Test Book"),
        "author": (None, "Test Author"),
        "description": (None, "Test Description"),
        "book_file": ("test_book.txt", b"This is a test book content.")
    }
    upload_response = httpx.post(
        f"{TEST_URL}/add_book", files=files, cookies=cookies)
    assert upload_response.status_code == 303, "Ошибка при загрузке книги"
    print("Upload book response HTML:", upload_response.text)

    # Получение списка книг
    list_response = httpx.get(f"{TEST_URL}/", cookies=cookies)
    assert list_response.status_code == 200, "Ошибка при получении списка книг"
    print("List books response HTML:", list_response.text)

    # Проверка списка книг
    books = []
    if "json" in list_response.headers.get("Content-Type", "").lower():
        books = list_response.json()
    else:
        print("HTML вместо JSON для списка книг")
    assert len(books) > 0, "Нет доступных книг"
    book_id = books[0]["id"] if books else None

    if book_id:
        # Детальная информация о книге
        detail_response = httpx.get(
            f"{TEST_URL}/book/{book_id}", cookies=cookies)
        assert detail_response.status_code == 200, "Ошибка при получении информации о книге"
        print("Book details response HTML:", detail_response.text)

        # Удаление книги
        delete_response = httpx.post(
            f"{TEST_URL}/delete_book/{book_id}", cookies=cookies)
        assert delete_response.status_code == 303, "Ошибка при удалении книги"
        print("Delete book response HTML:", delete_response.text)

    # Выход
    logout_response = httpx.post(f"{TEST_URL}/logout", cookies=cookies)
    assert logout_response.status_code == 303, "Ошибка при выходе пользователя"
    assert "user_id" not in logout_response.cookies, "Куки user_id не были удалены при выходе"
    print("Logout response HTML:", logout_response.text)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
