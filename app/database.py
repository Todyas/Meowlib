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
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int


class User(UserBase, table=True):
    id: Optional[int] = Field(
        default=None, primary_key=True)
    password_hash: str
    books: List["Book"] = Relationship(
        back_populates="user")


class BookBase(SQLModel):
    title: str = Field(index=True)
    author: Optional[str]
    description: Optional[str]
    file_path: str
    cover_path: Optional[str]


class BookCreate(BookBase):
    user_id: int


class BookRead(BookBase):
    id: int
    user_id: int


class BookUpdate(BookBase):
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    file_path: Optional[str] = None


class Book(BookBase, table=True):
    id: Optional[int] = Field(
        default=None, primary_key=True)

    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
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
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


# ================================== Функции ===========================================


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


# ================================== Рутинг ===========================================


@app.post("/users/", response_model=UserRead)
def create_user(*, session: Session = Depends(get_session), user: UserCreate):
    db_user = session.exec(select(User).where(
        User.username == user.username)).first()
    if db_user:
        raise HTTPException(
            status_code=400, detail="Username already registered"
        )
    hashed_password = hash_password(user.password)
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
    db_user = session.exec(select(User).where(
        User.username == username)).first()
    if not db_user:
        raise HTTPException(
            status_code=401, detail="Incorrect username or password"
        )

    if not verify_password(password, db_user.password_hash):
        raise HTTPException(
            status_code=401, detail="Incorrect username or password"
        )

    return {
        "message": "Authentication successful",
        "user_id": db_user.id,
        "username": db_user.username
    }


@app.get("/users/", response_model=List[UserRead])
def read_users(*, session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return users


@app.get("/users/{user_id}/", response_model=UserRead)
def read_user(*, session: Session = Depends(get_session), user_id: int):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@app.patch("/users/{user_id}/", response_model=UserRead)
def update_user(*, session: Session = Depends(get_session), user_id: int, user: UserCreate):
    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    db_user.username = user.username
    db_user.email = user.email
    db_user.password_hash = user.password
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.delete("/users/{user_id}/")
def delete_user(*, session: Session = Depends(get_session), user_id: int):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найдет")
    session.delete(user)
    session.commit()
    return {"ok": True}


@app.post("/books/", response_model=BookRead)
def create_book(*, session: Session = Depends(get_session), book: BookCreate):
    allowed_extensions = {".pdf", ".epub", ".mobi", ".txt",
                          ".doc", ".docx", ".rtf"}
    file_extension = book.file_path.split(".")[-1].lower()

    if f".{file_extension}" not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Неверное расширение файла. Поддерживаемые расширения: {
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
        user_id=book.user_id,
        cover_path=book.cover_path
    )

    session.add(book_obj)
    session.commit()
    session.refresh(book_obj)
    return book_obj


@app.get("/books/", response_model=List[BookRead])
def read_books(*, session: Session = Depends(get_session)):
    books = session.exec(select(Book)).all()
    return books


@app.get("/books/{book_id}/", response_model=BookRead)
def read_book(*, session: Session = Depends(get_session), book_id: int):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.patch("/books/{book_id}/", response_model=BookRead)
def update_book(*, session: Session = Depends(get_session), book_id: int, book: BookUpdate):
    db_book = session.get(Book, book_id)
    if not db_book:
        raise HTTPException(status_code=404, detail="Book not found")

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
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    session.delete(book)
    session.commit()
    return {"ok": True}


@app.get("/users/{user_id}/books/", response_model=List[BookRead])
def read_books_by_user(*, session: Session = Depends(get_session), user_id: int):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    books = session.exec(select(Book).where(Book.user_id == user_id)).all()
    return books


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.URL, port=config.DB_SERVER_PORT)
