from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import uvicorn
import os
from config import UPLOAD_DIR, SECRET_KEY
from itsdangerous import URLSafeTimedSerializer
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="meowlib/app/templates")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

UPLOAD_DIR = "meowlib/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def set_session_login(request: Request, login: str):
    request.session['user_login'] = login


def get_session_login(request: Request):
    return request.session.get('user_login')


def clear_session(request: Request):
    request.session.clear()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user_login = get_session_login(request)
    if user_login:
        # Получаем список книг с API
        resp = requests.get(f"{API_BASE_URL}/books/")
        books = resp.json() if resp.status_code == 200 else []
        return templates.TemplateResponse("index.html", {"request": request, "user_login": user_login, "books": books})
    else:
        return templates.TemplateResponse("index.html", {"request": request, "user_login": None, "books": []})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_action(request: Request, login: str = Form(...), password: str = Form(...)):
    # Проверяем логин/пароль по БД (упростим, пока заглушка)
    # В реальном случае надо делать запрос к /users/ в API, пока примем условно:
    if login == "test" and password == "test":
        set_session_login(request, login)
        return RedirectResponse("/", status_code=303)
    else:
        return RedirectResponse("/login", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("reg.html", {"request": request})


@app.post("/register")
def register_action(request: Request, login: str = Form(...), email: str = Form(...), password: str = Form(...)):
    # Отправляем запрос на API для создания пользователя (пока опустим реализацию)
    # Если успех:
    set_session_login(request, login)
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    clear_session(request)
    return RedirectResponse("/", status_code=303)


@app.get("/add_book", response_class=HTMLResponse)
def add_book_page(request: Request):
    user_login = get_session_login(request)
    if not user_login:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("add_book.html", {"request": request, "user_login": user_login})


@app.post("/add_book")
def add_book_action(request: Request,
                    title: str = Form(...),
                    author: str = Form(...),
                    description: str = Form(...),
                    book_file: UploadFile = File(...),
                    cover_file: UploadFile = File(...)):
    user_login = get_session_login(request)
    if not user_login:
        return RedirectResponse("/login", status_code=303)

    book_file_path = os.path.join(UPLOAD_DIR, book_file.filename)
    cover_file_path = os.path.join(UPLOAD_DIR, cover_file.filename)

    with open(book_file_path, "wb") as f:
        f.write(book_file.file.read())

    with open(cover_file_path, "wb") as f:
        f.write(cover_file.file.read())

    data = {
        "title": title,
        "author": author,
        "description": description,
        "file_path": book_file_path,
        "cover_path": cover_file_path
    }
    resp = requests.post(f"{API_BASE_URL}/books/", json=data)
    if resp.status_code == 200:
        return RedirectResponse("/", status_code=303)
    else:
        return HTTPException(status_code=resp.status_code, detail="Error adding book")
