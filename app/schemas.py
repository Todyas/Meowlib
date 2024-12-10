# schemas.py

from pydantic import BaseModel
from typing import Optional


class BookBase(BaseModel):
    title: str
    author: str
    description: Optional[str] = None
    file_path: str
    cover_image: Optional[str] = None


class BookCreate(BookBase):
    pass


class Book(BookBase):
    id: int

    class Config:
        orm_mode = True
