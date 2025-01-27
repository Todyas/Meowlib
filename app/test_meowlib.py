import pytest
import httpx


@pytest.fixture
def client():
    with httpx.Client(base_url=BASE_URL, follow_redirects=True) as client:
        yield client  # Клиент автоматически обрабатывает редиректы


def test_full_flow(client):
    # 1. Создание пользователя
    user_data = {
        "username": "test_1",
        "email": "test_1@example.com",
        "password": "securepassword"
    }

    response = client.post("/registration/", json=user_data)
    if response.status_code != 400:  # Если пользователь ещё не существует
        assert response.status_code == 200

    # 2. Логин пользователя
    login_data = {"username": "test_1", "password": "securepassword"}
    response = client.post("/users/authenticate/", json=login_data)
    assert response.status_code == 200
    user_id = response.json()["user_id"]

    # Сохраняем куки после логина
    assert "set-cookie" in response.headers

    # 3. Добавление книги
    book_data = {
        "title": "Test Book",
        "author": "Test Author",
        "description": "Test Description",
        "file_path": "test_book.pdf",
        "user_id": user_id
    }
    response = client.post("/books/", json=book_data)
    assert response.status_code == 200
    book_id = response.json()["id"]

    # 4. Обновление книги
    updated_book_data = {
        "title": "Updated Test Book",
        "author": "Updated Test Author",
        "description": "Updated Test Description",
        "file_path": "updated_test_book.pdf"
    }
    response = client.patch(f"/books/{book_id}/", json=updated_book_data)
    assert response.status_code == 200

    # 5. Скачивание книги
    response = client.get(f"/download/{book_id}")
    assert response.status_code == 200

    # 6. Удаление книги
    response = client.delete(f"/books/{book_id}/")
    assert response.status_code == 200

    # 7. Очистка куков (симуляция выхода из аккаунта)
    client.cookies.clear()
    response = client.get("/logout")
    assert response.status_code == 303  # Редирект на главную страницу после выхода
