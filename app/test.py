from faker import Faker
import requests

fake = Faker()

API_URL = "http://127.0.0.1:8000"


def create_fake_users(count=10):
    for _ in range(count):
        user_data = {
            "username": fake.user_name(),
            "email": fake.email(),
            "password": fake.password()
        }
        response = requests.post(f"{API_URL}/users/", json=user_data)
        if response.status_code == 200:
            print(f"User created: {response.json()}")
        else:
            print(f"Failed to create user: {response.text}")


def create_fake_books(user_count, book_count_per_user=5):
    users_response = requests.get(f"{API_URL}/users/")
    if users_response.status_code != 200:
        print("Failed to fetch users")
        return

    users = users_response.json()
    for user in users[:user_count]:
        for _ in range(book_count_per_user):
            book_data = {
                "title": fake.sentence(nb_words=4),
                "description": fake.paragraph(),
                "file_path": fake.file_path(),
                "user_id": user["id"]
            }
            response = requests.post(f"{API_URL}/books/", json=book_data)
            if response.status_code == 200:
                print(f"Book created: {response.json()}")
            else:
                print(f"Failed to create book: {response.text}")


if __name__ == "__main__":
    create_fake_users(10)
    create_fake_books(user_count=10, book_count_per_user=5)
