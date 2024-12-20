from fastapi import FastAPI, Request, Form, UploadFile, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware
from config import cfg
from database import engine, get_session, User, Book

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=f"{cfg.SECRET_KEY}")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="app/static/"), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, session: Session = Depends(get_session)):
    user_login = request.session.get("user_login")
    if not user_login:
        return templates.TemplateResponse(
            "index.html", {"request": request, "auth_required": True}
        )
    user = session.exec(select(User).where(
        User.username == user_login)).first()
    books = session.exec(select(Book).where(Book.user_id == user.id)).all()
    return templates.TemplateResponse(
        "index.html", {"request": request,
                       "user_login": user_login, "books": books}
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == login)).first()
    if user and user.password_hash == password:
        request.session["user_login"] = user.username
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Invalid credentials"}
    )


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("reg.html", {"request": request})


@app.post("/register")
async def register(
    login: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    db_user = session.exec(select(User).where(User.username == login)).first()
    if db_user:
        return templates.TemplateResponse(
            "reg.html",
            {"error": "Username already exists", "request": Request},
        )
    user = User(username=login, email=email, password_hash=password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return RedirectResponse("/login", status_code=302)


@app.get("/add_book", response_class=HTMLResponse)
async def add_book_page(request: Request):
    user_login = request.session.get("user_login")
    if not user_login:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("add_book.html", {"request": request})


@app.post("/add_book")
async def add_book(
    title: str = Form(...),
    author: str = Form(...),
    description: str = Form(None),
    book_file: UploadFile = Form(...),
    cover_file: UploadFile = Form(...),
    request: Request = Depends(get_session),
    session: Session = Depends(get_session),
):
    user_login = request.session.get("user_login")
    if not user_login:
        return RedirectResponse("/login", status_code=302)
    user = session.exec(select(User).where(
        User.username == user_login)).first()
    book = Book(
        title=title,
        description=description,
        file_path=book_file.filename,
        user_id=user.id,
    )
    session.add(book)
    session.commit()
    return RedirectResponse("/", status_code=302)


@app.get("/book/{book_id}", response_class=HTMLResponse)
async def book_detail(book_id: int, request: Request, session: Session = Depends(get_session)):
    book = session.get(Book, book_id)
    if not book:
        return HTMLResponse("Book not found", status_code=404)
    return templates.TemplateResponse("book.html", {"request": request, "book": book})


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)
