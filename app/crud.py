from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from .models import User, Book


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user: User) -> User:
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_book(db: AsyncSession, book: Book) -> Book:
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def get_books_by_user(db: AsyncSession, user_id: int) -> List[Book]:
    result = await db.execute(select(Book).where(Book.owner_id == user_id))
    return result.scalars().all()
