from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import create_engine, SQLModel, Session, select
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel


class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str
    books: List["Book"] = Relationship(back_populates="user")


class BookBase(SQLModel):
    title: str = Field(index=True)
    description: Optional[str] = None
    file_path: str


class BookCreate(BookBase):
    user_id: int


class BookRead(BookBase):
    id: int
    user_id: int


class Book(BookBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional[User] = Relationship(back_populates="books")


# ================================================================================


DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL, echo=True)


def get_session():
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


# ================================================================================


@app.post("/users/", response_model=UserRead)
def create_user(*, session: Session = Depends(get_session), user: UserCreate):
    db_user = session.exec(select(User).where(
        User.username == user.username)).first()
    if db_user:
        raise HTTPException(
            status_code=400, detail="Username already registered")
    user_obj = User(username=user.username, email=user.email,
                    password_hash=user.password)
    session.add(user_obj)
    session.commit()
    session.refresh(user_obj)
    return user_obj


@app.get("/users/", response_model=List[UserRead])
def read_users(*, session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return users


@app.get("/users/{user_id}/", response_model=UserRead)
def read_user(*, session: Session = Depends(get_session), user_id: int):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/users/{user_id}/", response_model=UserRead)
def update_user(*, session: Session = Depends(get_session), user_id: int, user: UserCreate):
    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
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
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(user)
    session.commit()
    return {"ok": True}


@app.post("/books/", response_model=BookRead)
def create_book(*, session: Session = Depends(get_session), book: BookCreate):
    user = session.get(User, book.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    book_obj = Book(title=book.title, description=book.description,
                    file_path=book.file_path, user_id=book.user_id)
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
def update_book(*, session: Session = Depends(get_session), book_id: int, book: BookCreate):
    db_book = session.get(Book, book_id)
    if not db_book:
        raise HTTPException(status_code=404, detail="Book not found")
    db_book.title = book.title
    db_book.description = book.description
    db_book.file_path = book.file_path
    db_book.user_id = book.user_id
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
