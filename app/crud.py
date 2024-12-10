from sqlalchemy.orm import Session
from app.models import Book
from app.schemas import BookCreate


def create_book(db: Session, book: BookCreate):
    book_db = Book(
        title=book.title,
        author=book.author,
        description=book.description,
        file_path=book.file_path,
        cover_image=book.cover_image,
    )
    db.add(book_db)
    db.commit()
    db.refresh(book_db)
    return book_db


def get_books(db: Session, skip: int = 0, limit: int = 10):
    return db.query(Book).offset(skip).limit(limit).all()


def get_book_by_id(db: Session, book_id: int):
    return db.query(Book).filter(Book.id == book_id).first()


def update_book(db: Session, book_id: int, book_update: BookCreate):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        return None

    if book_update.title:
        book.title = book_update.title
    if book_update.author:
        book.author = book_update.author
    if book_update.description:
        book.description = book_update.description
    if book_update.file_path:
        book.file_path = book_update.file_path
    if book_update.cover_image:
        book.cover_image = book_update.cover_image

    db.commit()
    db.refresh(book)
    return book


def delete_book(db: Session, book_id: int):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        return False

    db.delete(book)
    db.commit()
    return True
