# Библиотеки для общего функционала
import time  # Работа с временем
import os  # Работа с файлами

# Библиотеки для работы с FastAPI
from fastapi import FastAPI, HTTPException, Request, Form, UploadFile  # FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse  # HTML ответы и редиректы
from fastapi.templating import Jinja2Templates  # Jinja2 шаблонизатор
from fastapi.staticfiles import StaticFiles  # Статические файлы (CSS, JS)
from starlette.middleware.sessions import SessionMiddleware  # Работа с сессиями
from pathlib import Path  # Работа с путями
from dotenv import load_dotenv  # Загрузка переменных окружения

# Библиотеки для работы с книгами
import ebooklib  # Работа с EPUB-книгами
from pdf2image import convert_from_path  # Работа с PDF-книгами


# ===== Конфигурация =====


# Загрузка переменных окружения
load_dotenv()

# Определяем базовую директорию проекта
BASE_DIR = Path(__file__).resolve().parent

# Пути относительно app
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "data/uploads")
DB_DIRECTORY = BASE_DIR / os.getenv("DB_DIRECTORY", "data")
DB_FILE = os.getenv("DB_FILE", "database.sqlite")

# Конфигурация
URL = os.getenv("URL", "0.0.0.0")
SECRET_KEY = os.getenv("SECRET_KEY", "Cheese")
DB_SERVER_PORT = int(os.getenv("DB_SERVER_PORT", 8001))
MAIN_PORT = int(os.getenv("MAIN_PORT", 8000))

DB_URL = os.getenv("DB_URL", f"sqlite:///{DB_DIRECTORY}/{DB_FILE}")
DB_DOCKER_URL = f"http://database:{DB_SERVER_PORT}"
MAIN_DOCKER_URL = f"http://main:{MAIN_PORT}"

# Инициализация папок
for directory in [DB_DIRECTORY, UPLOAD_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Инициализация FastAPI
app = FastAPI()

# Инициализация middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Инициализация шаблонизатора
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


# ===== Функции =====


async def make_request(method: str, url: str, **kwargs):
    '''
    Функция для выполнения HTTP-запросов.
    '''
    import httpx

    # Пытаемся выполнить запрос 3 раза
    for _ in range(3):
        try:
            # Создаем асинхронный HTTP-клиент
            async with httpx.AsyncClient() as client:
                # Выполняем запрос с указанным методом, URL и параметрами
                response = await client.request(method, url, **kwargs)

                # Проверяем статус ответа, вызывает ошибку, если статус не 2xx
                response.raise_for_status()

                # Возвращаем успешный ответ
                return response
        except httpx.RequestError as e:
            # Обрабатываем ошибки, связанные с запросом (например, проблемы сети)
            print(f"Request error: {e}")
        except httpx.HTTPStatusError as e:
            # Обрабатываем ошибки HTTP-статусов (например, 4xx или 5xx)
            print(f"HTTP error: {e}")

    # Если все 3 попытки завершились неудачей, выбрасываем исключение
    raise HTTPException(status_code=500, detail="External API request failed")


async def generate_filename(user_id: str, original_name: str, extension: str = None) -> str:
    '''
    Функция для генерации уникального имени файла
    '''
    ext = extension if extension else Path(original_name).suffix
    return f"{user_id}_{int(time.time())}{ext}"


async def generate_cover_image(book_file_path: str, user_id: str) -> str:
    '''
    Функция для генерации обложки книги
    '''
    COVER_FILENAME = await generate_filename(
        user_id=user_id,
        original_name="cover",
        extension=".jpg"
    )

    # Пути относительно app
    STATIC_DIR = BASE_DIR / "static"
    COVERS_DIR = STATIC_DIR / "covers"

    # Генерация путей
    STATIC_COVER_PATH = COVERS_DIR / COVER_FILENAME
    RELATIVE_COVER_PATH = f"/static/covers/{COVER_FILENAME}"

    try:
        if ext := Path(book_file_path).suffix.lower():
            import asyncio
            if ext == ".pdf":
                images = await asyncio.to_thread(convert_from_path,
                                                 book_file_path, first_page=1, last_page=1)
                if images:
                    await asyncio.to_thread(images[0].save, STATIC_COVER_PATH, "JPEG")
                    return RELATIVE_COVER_PATH

            elif ext == ".epub":
                import aiofiles
                book = await asyncio.to_thread(ebooklib.epub.read_epub, book_file_path)
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_COVER:
                        async with aiofiles.open(STATIC_COVER_PATH, "wb") as f:
                            await f.write(item.get_content())
                            return RELATIVE_COVER_PATH

                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_IMAGE:
                        async with aiofiles.open(STATIC_COVER_PATH, "wb") as f:
                            await f.write(item.get_content())
                            return RELATIVE_COVER_PATH

    except Exception as e:
        print(f"[generate_cover_image] Error processing {ext}: {e}")
    return None


# ===== Маршруты сайта =====


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login_post(request: Request, login: str = Form(...), password: str = Form(...)):
    try:
        response = await make_request(
            "POST",
            f"{DB_DOCKER_URL}/users/authenticate/",
            json={"username": login, "password": password}
        )
        response_data = response.json()
        redirect_response = RedirectResponse(url="/", status_code=303)
        redirect_response.set_cookie(key="user_id", value=str(
            response_data.get("user_id")), httponly=True)
        redirect_response.set_cookie(
            key="username", value=response_data.get("username"), httponly=True)
        return redirect_response
    except HTTPException as e:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверное имя пользователя или пароль"
        })


@app.get("/registration", response_class=HTMLResponse)
async def registration_get(request: Request):
    user_login = request.cookies.get("username")
    return templates.TemplateResponse("reg.html", {
        "request": request,
        "user_login": user_login})


@app.post("/registration")
async def registration_post(request: Request, login: str = Form(...), email: str = Form(...), password: str = Form(...)):
    try:
        await make_request("POST", f"{DB_DOCKER_URL}/users/", json={
            "username": login,
            "email": email,
            "password": password
        })
        return RedirectResponse(url="/login", status_code=303)
    except HTTPException as e:
        error_message = "Данный логин уже занят" if e.status_code != 400 else e.detail
        return templates.TemplateResponse("reg.html", {
            "request": request,
            "error": error_message
        })


# Декоратор для определения, какой метод и по какому URL эта функция обрабатывает
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user_login = request.cookies.get("username")
    user_id = request.cookies.get("user_id")  # Получаем user_id из cookies
    books = []

    # Отправляем запрос database.py для получения книг
    try:
        # Передаём user_id в запрос
        response = await make_request("GET", f"{DB_DOCKER_URL}/books/?user_id={user_id}")
        books = response.json()
    except HTTPException:
        pass

    # Передаём данные в шаблон
    return templates.TemplateResponse("index.html", {
        "request": request,
        "books": books,
        "user_login": user_login
    })


@app.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("username")
    response.delete_cookie("user_id")
    return response


@app.get("/add_book", response_class=HTMLResponse)
async def add_book_get(request: Request):
    user_login = request.cookies.get("username")
    return templates.TemplateResponse("add_book.html", {
        "request": request,
        "user_login": user_login})


@app.post("/add_book")
async def add_book_post(
    request: Request,
    title: str = Form(None),
    author: str = Form(...),
    description: str = Form(...),
    book_file: UploadFile = None
):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authorization required")

    if not book_file:
        raise HTTPException(status_code=400, detail="Book file is required")

    # Если название не указано, генерируем его из имени файла
    if not title:
        raw_filename = book_file.filename
        title = os.path.splitext(raw_filename)[0]

    filename = await generate_filename(user_id, book_file.filename)
    book_path = os.path.join(
        UPLOAD_DIR,
        filename
    )

    from aiofiles import open as aio_open
    async with aio_open(book_path, "wb") as f:
        await f.write(await book_file.read())

    cover_path = await generate_cover_image(book_path, user_id)

    await make_request("POST", f"{DB_DOCKER_URL}/books/", json={
        "title": title,
        "author": author,
        "description": description,
        "file_path": book_path,
        "cover_path": cover_path,
        "user_id": user_id
    })

    return RedirectResponse(url="/", status_code=303)


@app.get("/book/{book_id}", response_class=HTMLResponse)
async def book_details(request: Request, book_id: int):
    response = await make_request("GET", f"{DB_DOCKER_URL}/books/{book_id}/")
    book = response.json()
    user_login = request.cookies.get("username")
    return templates.TemplateResponse("book.html", {
        "request": request,
        "book": book,
        "user_login": user_login})


@app.get("/download/{book_id}")
async def download_file(book_id: int):
    from fastapi.responses import FileResponse
    response = await make_request("GET", f"{DB_DOCKER_URL}/books/{book_id}/")
    book = response.json()
    file_path = book["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path=file_path, filename=os.path.basename(file_path), media_type="application/octet-stream")


@app.get("/edit/{book_id}", response_class=HTMLResponse)
async def edit_book_get(request: Request, book_id: int):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    response = await make_request("GET", f"{DB_DOCKER_URL}/books/{book_id}/")
    book = response.json()
    if book["user_id"] != int(user_id):
        raise HTTPException(
            status_code=403, detail="Редактирование книги не разрешено")
    user_login = request.cookies.get("username")
    return templates.TemplateResponse("edit_book.html", {
        "request": request,
        "book": book,
        "user_login": user_login
    })


@app.post("/edit/{book_id}")
async def edit_book_post(
        request: Request,
        book_id: int,
        title: str = Form(...),
        author: str = Form(...),
        description: str = Form(...),
        book_file: UploadFile = None):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="authorization required")
    book_response = await make_request("GET", f"{DB_DOCKER_URL}/books/{book_id}/")
    book = book_response.json()
    if book["user_id"] != int(user_id):
        raise HTTPException(
            status_code=403, detail="Editing the book is not allowed")
    book_path = book["file_path"]
    if book_file:
        filename = await generate_filename(user_id, book_file.filename)
        book_path = os.path.join(UPLOAD_DIR, filename)
        from aiofiles import open as aio_open
        async with aio_open(book_path, "wb") as f:
            await f.write(await book_file.read())
    cover_path = book["cover_path"]
    if book_file:
        cover_path = await generate_cover_image(book_path, user_id)
    await make_request("PATCH", f"{DB_DOCKER_URL}/books/{book_id}/", json={
        "title": title,
        "author": author,
        "description": description,
        "file_path": book_path,
        "cover_path": cover_path
    })
    return RedirectResponse(url="/", status_code=303)


@app.get("/delete/{book_id}")
async def delete_book_route(book_id: int, request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="authorization required")
    response = await make_request("GET", f"{DB_DOCKER_URL}/books/{book_id}/")
    book = response.json()
    if book["user_id"] != int(user_id):
        raise HTTPException(
            status_code=403, detail="You don't have permission to delete this book")
    await make_request("DELETE", f"{DB_DOCKER_URL}/books/{book_id}/")
    try:
        if os.path.exists(book["file_path"]):
            os.remove(book["file_path"])
        if book["cover_path"]:
            cover_full_path = os.path.join(
                "app", book["cover_path"].lstrip('/'))
            if os.path.exists(cover_full_path):
                os.remove(cover_full_path)
    except OSError as e:
        print(f"Error deleting files: {e}")
    return RedirectResponse(url="/", status_code=303)

# Код для запуска
# if __name__ == '__main__':
#     import uvicorn
#     uvicorn.run(app, host=URL, port=MAIN_PORT)
