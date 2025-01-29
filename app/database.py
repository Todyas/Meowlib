# ===== Библиотеки =====

from contextlib import asynccontextmanager
import os
import bcrypt
import logging
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Body, Depends, Path
from sqlmodel import Field, Relationship, SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator

from dotenv import load_dotenv
import pathlib

# ===== Конфигурация =====

# Логирование
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Загрузка переменных окружения
load_dotenv()

# Пути проекта
BASE_DIR = pathlib.Path(os.getcwd()).resolve()
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "data/uploads")
DB_DIRECTORY = BASE_DIR / os.getenv("DB_DIRECTORY", "data")
DB_FILE = os.getenv("DB_FILE", "database.sqlite")

# Подключение базы данных
DB_PATH = DB_DIRECTORY / DB_FILE
DB_URL = f"sqlite+aiosqlite:///{DB_PATH.resolve()}"

# Создание директорий
for directory in [DB_DIRECTORY, UPLOAD_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Создание асинхронного движка SQLAlchemy
engine = create_async_engine(DB_URL, echo=False, future=True)
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession)


# ===== Определение моделей =====


class UserBase(SQLModel):
    """Базовая модель пользователя"""
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)


class UserCreate(UserBase):
    """Модель для создания пользователя"""
    password: str


class UserRead(UserBase):
    """Модель для чтения пользователя"""
    id: int


class User(UserBase, table=True):
    """Модель пользователя в БД"""
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str
    books: List["Book"] = Relationship(back_populates="user")


class BookBase(SQLModel):
    """Базовая модель книги"""
    title: str = Field(index=True)
    author: Optional[str]
    description: Optional[str]
    file_path: str
    cover_path: Optional[str]


class BookCreate(BookBase):
    """Модель для создания книги"""
    user_id: int


class BookRead(BookBase):
    """Модель для чтения книги"""
    id: int
    user_id: int


class BookUpdate(SQLModel):
    """Модель для обновления книги"""
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    file_path: Optional[str] = None
    cover_path: Optional[str] = None
    user_id: Optional[int] = None


class Book(BookBase, table=True):
    """Модель книги в БД"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional[User] = Relationship(back_populates="books")


# ===== Управление БД =====

async def create_db_and_tables():
    """Создание таблиц в базе данных"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        logging.info("✅ Таблицы успешно созданы!")
    except Exception as e:
        logging.error(f"❌ Ошибка при создании таблиц: {str(e)}")
        raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Получение асинхронной сессии"""
    async with async_session() as session:
        yield session


# ===== Хеширование паролей =====


def hash_password(password: str) -> str:
    """Хеширует пароль с солью"""
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Проверяет соответствие пароля и хэша"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


# ===== FastAPI =====


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск FastAPI с инициализацией БД"""
    await create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


# ===== Маршруты =====


@app.post("/users/", response_model=UserRead)
async def create_user(user: UserCreate, session: AsyncSession = Depends(get_session)):
    """Создание нового пользователя"""
    existing_user = await session.execute(select(User).where(User.username == user.username))
    if existing_user.scalars().first():
        raise HTTPException(
            status_code=400, detail="Пользователь уже зарегистрирован")

    hashed_password = hash_password(user.password)
    new_user = User(username=user.username, email=user.email,
                    password_hash=hashed_password)

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return new_user


@app.post("/users/authenticate/")
async def authenticate_user(username: str = Body(...), password: str = Body(...), session: AsyncSession = Depends(get_session)):
    """Аутентификация пользователя"""
    query = await session.execute(select(User).where(User.username == username))
    db_user = query.scalars().first()

    if not db_user or not verify_password(password, db_user.password_hash):
        raise HTTPException(
            status_code=401, detail="Неверный логин или пароль")

    return {"message": "Аутентификация успешна", "user_id": db_user.id, "username": db_user.username}


@app.get("/users/{user_id}/", response_model=UserRead)
async def read_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """Получение информации о пользователе"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@app.post("/books/", response_model=BookRead)
async def create_book(book: BookCreate, session: AsyncSession = Depends(get_session)):
    """Добавление книги в базу"""
    user = await session.get(User, book.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    new_book = Book(**book.dict())

    session.add(new_book)
    await session.commit()
    await session.refresh(new_book)
    return new_book


@app.get("/books/", response_model=List[BookRead])
async def read_books(user_id: Optional[int] = None, session: AsyncSession = Depends(get_session)):
    """Получение списка книг (по пользователю или всех)"""
    query = select(Book)
    if user_id is not None:
        query = query.where(Book.user_id == user_id)

    result = await session.execute(query)
    books = result.scalars().all()
    return books


@app.get("/books/{book_id}/", response_model=BookRead)
async def read_book(book_id: int, session: AsyncSession = Depends(get_session)):
    """Получение информации о книге"""
    book = await session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Книга не найдена")
    return book


@app.patch("/books/{book_id}/", response_model=BookRead)
async def update_book(
    book_id: int = Path(title="ID книги"),  # Убрали `...`
    book: BookUpdate = Body(...),
    session: AsyncSession = Depends(get_session)
):
    """Обновление информации о книге"""
    db_book = await session.get(Book, book_id)
    if not db_book:
        raise HTTPException(status_code=404, detail="Книга не найдена")

    update_data = book.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_book, key, value)

    session.add(db_book)
    await session.commit()
    await session.refresh(db_book)

    return db_book
