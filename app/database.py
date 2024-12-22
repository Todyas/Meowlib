from contextlib import asynccontextmanager
import os
import bcrypt
from fastapi import Depends, FastAPI, HTTPException, Body
from fastapi.responses import FileResponse
from sqlmodel import Field, Relationship, create_engine, SQLModel, Session, select
from typing import Annotated, List, Optional
from config import config


# ================================== Модели ===========================================


class UserBase(SQLModel):
    """
    Базовая модель пользователя
    """
    username: str = Field(index=True, unique=True)  # Имя пользователя
    email: str = Field(index=True, unique=True)  # Электронная почта


class UserCreate(UserBase):
    """
    Модель для создания пользователя
    """
    password: str  # Пароль


class UserRead(UserBase):
    """
    Модель для чтения пользователя
    """
    id: int  # Идентификатор пользователя


class User(UserBase, table=True):
    """
    Модель пользователя
    """
    id: Optional[int] = Field(
        default=None, primary_key=True)  # Идентификатор пользователя
    password_hash: str  # Хэш пароля
    books: List["Book"] = Relationship(
        back_populates="user")  # Связь с книгами


class BookBase(SQLModel):
    """
    Базовая модель книги
    """
    title: str = Field(index=True)  # Название книги
    author: Optional[str] = None  # Автор
    description: Optional[str] = None  # Описание книги
    file_path: str  # Путь к файлу
    cover_path: Optional[str] = None  # Путь к обложке


class BookCreate(BookBase):
    """
    Модель для создания книги
    """
    user_id: int  # Идентификатор пользователя


class BookRead(BookBase):
    """
    Модель для чтения книги
    """
    # Идентификатор книги
    id: int
    # Идентификатор пользователя
    user_id: int


class BookUpdate(BookBase):
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    file_path: Optional[str] = None


class Book(BookBase, table=True):
    """
    Модель книги
    """
    # Идентификатор книги
    id: Optional[int] = Field(
        default=None, primary_key=True)

    # Идентификатор пользователя
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    # Связь с пользователем
    user: Optional[User] = Relationship(
        back_populates="books")


# ================================== Инициализация ===========================================


sqlite_url = config.DB_URL

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Обработчик события запуска приложения
    """
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)


# ================================== Функции ===========================================


def hash_password(password: str) -> str:
    """
    Хэширование пароля
    """
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Проверка пароля
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


# ================================== Рутинг ===========================================


@app.post("/users/", response_model=UserRead)
def create_user(*, session: Session = Depends(get_session), user: UserCreate):
    """
    Создание нового пользователя
    """
    db_user = session.exec(select(User).where(
        User.username == user.username)).first()
    if db_user:
        raise HTTPException(
            status_code=400, detail="Имя пользователя уже зарегистрировано"
        )
    hashed_password = hash_password(user.password)  # Хэширование пароля
    user_obj = User(username=user.username, email=user.email,
                    password_hash=hashed_password)
    session.add(user_obj)
    session.commit()
    session.refresh(user_obj)
    return user_obj


@app.post("/users/authenticate/")
async def authenticate_user(
    *,
    session: Session = Depends(get_session),
    username: str = Body(..., embed=True),
    password: str = Body(..., embed=True)
):
    """
    Аутентификация пользователя
    """
    # Проверяем, существует ли пользователь
    db_user = session.exec(select(User).where(
        User.username == username)).first()
    if not db_user:
        raise HTTPException(
            status_code=401, detail="Неверное имя пользователя или пароль"
        )

    # Проверяем пароль
    if not verify_password(password, db_user.password_hash):
        raise HTTPException(
            status_code=401, detail="Неверное имя пользователя или пароль"
        )

    # Возвращаем результат успешной аутентификации
    return {
        "message": "Аутентификация успешна",
        "user_id": db_user.id,
        "username": db_user.username
    }


@app.get("/users/", response_model=List[UserRead])
def read_users(*, session: Session = Depends(get_session)):
    """
    Получение всех пользователей
    """
    users = session.exec(select(User)).all()
    return users


@app.get("/users/{user_id}/", response_model=UserRead)
def read_user(*, session: Session = Depends(get_session), user_id: int):
    """
    Получение информации о пользователе по идентификатору
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@app.patch("/users/{user_id}/", response_model=UserRead)
def update_user(*, session: Session = Depends(get_session), user_id: int, user: UserCreate):
    """
    Обновление информации о пользователе
    """
    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    db_user.username = user.username  # Обновление имени пользователя
    db_user.email = user.email  # Обновление электронной почты
    db_user.password_hash = user.password  # Обновление хэша пароля
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.delete("/users/{user_id}/")
def delete_user(*, session: Session = Depends(get_session), user_id: int):
    """
    Удаление пользователя
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    session.delete(user)
    session.commit()
    return {"ok": True}


@app.post("/books/", response_model=BookRead)
def create_book(*, session: Session = Depends(get_session), book: BookCreate):
    """
    Создание новой книги
    """
    allowed_extensions = {".pdf", ".epub", ".mobi", ".txt",
                          ".doc", ".docx", ".rtf"}  # Разрешённые форматы
    file_extension = book.file_path.split(".")[-1].lower()

    if f".{file_extension}" not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Неверный формат файла. Допустимые форматы: {
                ', '.join(allowed_extensions)}"
        )

    user = session.get(User, book.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    book_obj = Book(
        title=book.title,
        author=book.author,
        description=book.description,
        file_path=book.file_path,
        user_id=book.user_id
    )
    session.add(book_obj)
    session.commit()
    session.refresh(book_obj)
    return book_obj


@app.get("/books/", response_model=List[BookRead])
def read_books(*, session: Session = Depends(get_session)):
    """
    Получение всех книг
    """
    books = session.exec(select(Book)).all()
    return books


@app.get("/books/{book_id}/", response_model=BookRead)
def read_book(*, session: Session = Depends(get_session), book_id: int):
    """
    Получение информации о книге по идентификатору
    """
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Книга не найдена")
    return book


@app.patch("/books/{book_id}/", response_model=BookRead)
def update_book(*, session: Session = Depends(get_session), book_id: int, book: BookUpdate):
    """
    Обновление информации о книге
    """
    db_book = session.get(Book, book_id)
    if not db_book:
        raise HTTPException(status_code=404, detail="Книга не найдена")

    # Обновляем только переданные поля
    if book.title is not None:
        db_book.title = book.title
    if book.author is not None:
        db_book.author = book.author
    if book.description is not None:
        db_book.description = book.description
    if book.file_path is not None:
        db_book.file_path = book.file_path

    session.add(db_book)
    session.commit()
    session.refresh(db_book)
    return db_book


@app.delete("/books/{book_id}/")
def delete_book(*, session: Session = Depends(get_session), book_id: int):
    """
    Удаление книги
    """
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Книга не найдена")
    session.delete(book)
    session.commit()
    return {"ok": True}


@app.get("/users/{user_id}/books/", response_model=List[BookRead])
def read_books_by_user(*, session: Session = Depends(get_session), user_id: int):
    """
    Получение всех книг пользователя
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    books = session.exec(select(Book).where(Book.user_id == user_id)).all()
    return books


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.URL, port=config.DB_SERVER_PORT)
