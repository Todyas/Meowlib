from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str
    password_hash: str


class BookBase(SQLModel):
    title: str = Field(index=True)
    author: str
    description: str | None = None
    file_path: str
    cover_image: str | None = None
    user_id: int = Field(foreign_key="user.id")


class Book(BookBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class BookPublic(BookBase):
    id: int


class BookCreate(BookBase):
    pass


class BookUpdate(SQLModel):
    title: str | None = None
    author: str | None = None
    description: str | None = None
    file_path: str | None = None
    cover_image: str | None = None
    user_id: int | None = None


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(bind=engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.post("/books/", response_model=BookPublic)
async def create_book(book: BookCreate, session: SessionDep):
    db_book = Book.model_validate(book)
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@app.get("/books/", response_model=list[BookPublic])
async def read_books(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[Book]:
    books = session.exec(select(Book).offset(offset).limit(limit)).all()
    return books


@app.get("/books/{book_id}")
async def read_book(book_id: int, session: SessionDep) -> Book:
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.delete("/heroes/{hero_id}")
async def delete_book(hero_id: int, session: SessionDep):
    book = session.get(Book, hero_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    session.delete(book)
    session.commit()
    return {"ok": True}


@app.patch("/books/{book_id}", response_model=BookPublic)
def update_book(book_id: int, book: BookUpdate, session: SessionDep):
    book_db = session.get(Book, book_id)
    if not book_db:
        raise HTTPException(status_code=404, detail="Book not found")
    book_data = book.model_dump(exclude_unset=True)
    book_db.sqlmodel_update(book_data)
    session.add(book_db)
    session.commit()
    session.refresh(book_db)
    return book_db
