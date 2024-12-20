import random
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import User, Book, create_db_and_tables

# Инициализация Faker
faker = Faker()

# Настройка базы данных
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создание базы данных и таблиц
create_db_and_tables()


def populate_database():
    session = SessionLocal()
    try:
        # Генерация пользователей
        users = []
        for _ in range(10):
            username = faker.user_name()
            email = faker.email()
            password_hash = faker.password()
            user = User(username=username, email=email,
                        password_hash=password_hash)
            session.add(user)
            users.append(user)

        session.commit()

        # Генерация книг
        for _ in range(30):
            title = faker.sentence(nb_words=3)
            description = faker.text(max_nb_chars=200)
            file_path = faker.file_path(extension='pdf')
            user = random.choice(users)
            book = Book(title=title, description=description,
                        file_path=file_path, user_id=user.id)
            session.add(book)

        session.commit()
        print("Database populated successfully!")
    except Exception as e:
        session.rollback()
        print(f"An error occurred: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    populate_database()
