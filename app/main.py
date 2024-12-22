import ebooklib
import epub
from pdf2image import convert_from_path
from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, Depends
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from config import config
from pathlib import Path
from pdf2image import convert_from_path  # For extracting pages from PDFs

# Initialize FastAPI app
app = FastAPI()

# Add middleware
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)


class StaticFileFallbackMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 404 and request.url.path.startswith("/static/covers/"):
            return FileResponse("app/static/covers/default.jpg")
        return response


app.add_middleware(StaticFileFallbackMiddleware)


# Configure directories
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
os.makedirs(config.UPLOAD_DIR, exist_ok=True)
# Ensure covers directory exists
os.makedirs("app/static/covers", exist_ok=True)

# Helper function for HTTP requests


async def make_request(method: str, url: str, **kwargs):
    """Wrapper for making HTTP requests with retry logic."""
    import httpx

    for _ in range(3):  # Retry up to 3 times
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
        except httpx.RequestError as e:
            print(f"Request error: {e}")
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e}")
    raise HTTPException(status_code=500, detail="External API request failed")


# Helper function to generate filenames


def generate_filename(user_id: str, book_id: str, name: str) -> str:
    """Generate a standardized filename."""
    sanitized_name = "_".join(name.split()).replace(
        "/", "_").replace("\\", "_")
    return f"{user_id}_{book_id}_{sanitized_name}"

# Helper function to extract cover image


def generate_cover_image(book_file_path: str, cover_file_path: str) -> bool:
    """
    Генерирует обложку для PDF/ePub, сохраняет в `cover_file_path`.
    Возвращает True, если получилось сделать обложку, иначе False.
    """
    ext = Path(book_file_path).suffix.lower()

    try:
        if ext == ".pdf":
            # Берём первую страницу из PDF и сохраняем как JPEG
            images = convert_from_path(
                book_file_path, first_page=1, last_page=1)
            if images:
                images[0].save(cover_file_path, "JPEG")
                return True
            else:
                return False

        elif ext == ".epub":
            # Ищем первый image-item (обычно это обложка)
            book = epub.read_epub(book_file_path)
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE:
                    with open(cover_file_path, "wb") as f:
                        f.write(item.get_content())
                    return True
            return False

        else:
            # Никаких MOBI и прочих форматов. Только PDF/ePub.
            return False

    except Exception as e:
        print(f"[generate_cover_image] Ошибка при обработке {ext}: {e}")
        return False


# =================================== Рутинг ===================================


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login_post(request: Request, login: str = Form(...), password: str = Form(...)):
    try:
        # Отправляем запрос на аутентификацию
        response = await make_request(
            "POST",
            f"{config.DB_API_URL}/users/authenticate/",
            json={"username": login, "password": password}
        )
        response_data = response.json()

        # Создаём редирект на главную страницу
        redirect_response = RedirectResponse(url="/", status_code=303)

        # Устанавливаем cookies для хранения user_id и username
        redirect_response.set_cookie(
            key="user_id",
            value=str(response_data.get("user_id")),
            httponly=True,
            secure=False  # Установите True при использовании HTTPS
        )
        redirect_response.set_cookie(
            key="username",
            value=response_data.get("username"),
            httponly=True,
            secure=False  # Установите True при использовании HTTPS
        )
        return redirect_response
    except HTTPException as e:
        # Возвращаем страницу с ошибкой аутентификации
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": str(e.detail)}
        )


@app.get("/registration", response_class=HTMLResponse)
async def registration_get(request: Request):
    user_login = request.cookies.get("username")
    return templates.TemplateResponse("reg.html", {
        "request": request,
        "user_login": user_login})


@app.post("/registration")
async def registration_post(request: Request, login: str = Form(...), email: str = Form(...), password: str = Form(...)):
    try:
        await make_request("POST", f"{config.DB_API_URL}/users/", json={
            "username": login,
            "email": email,
            "password": password})
        return RedirectResponse(url="/login", status_code=303)
    except HTTPException as e:
        return templates.TemplateResponse("reg.html", {
            "request": request,
            "error": str(e.detail)})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user_login = request.cookies.get("username")  # Получаем логин из куки
    books = []  # По умолчанию пустой список книг

    try:
        # Попытка получить список книг
        response = await make_request("GET", f"{config.DB_API_URL}/books/")
        books = response.json()
    except HTTPException:
        # Если произошла ошибка — книги остаются пустыми
        pass

    # Передаем в шаблон логин пользователя и книги
    return templates.TemplateResponse("index.html", {
        "request": request,
        "books": books,
        "user_login": user_login
    })


@app.get("/logout")
async def logout(request: Request):
    # Перенаправляем на главную
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("username")  # Удаляем куки с именем пользователя
    response.delete_cookie("user_id")  # Удаляем куки с ID пользователя
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
    title: str = Form(...),
    author: str = Form(...),
    description: str = Form(...),
    book_file: UploadFile = None,
    cover_file: UploadFile = None
):
    user_login = request.cookies.get("username")
    if not user_login:
        raise HTTPException(status_code=401, detail="Authorization required")

    # Генерим пути
    book_path = os.path.join(
        config.UPLOAD_DIR,
        generate_filename(user_login, "new", book_file.filename)
    )
    cover_path = os.path.join(
        "app", "static", "covers",
        generate_filename(user_login, "new", "cover.jpg")
    )

    # Сохраняем файл книги
    from aiofiles import open as aio_open
    async with aio_open(book_path, "wb") as f:
        await f.write(await book_file.read())

    # Если пользователь прислал обложку
    if cover_file:
        async with aio_open(cover_path, "wb") as f:
            await f.write(await cover_file.read())
    else:
        # Пытаемся сгенерировать обложку
        generate_cover_image(book_path, cover_path)
        # Если генерация не удалась или формат неизвестный —
        # при отображении сработает наш fallback через мидлвэйр.

    # Отправляем метаданные книги в нашу БД
    await make_request("POST", f"{config.DB_API_URL}/books/", json={
        "title": title,
        "author": author,
        "description": description,
        "file_path": book_path,
        "cover_path": cover_path,
        "user_id": request.cookies.get("user_id")
    })

    return RedirectResponse(url="/", status_code=303)


@app.get("/book/{book_id}", response_class=HTMLResponse)
async def book_details(request: Request, book_id: int):
    response = await make_request("GET", f"{config.DB_API_URL}/books/{book_id}/")
    book = response.json()
    user_login = request.cookies.get("username")
    return templates.TemplateResponse("book.html", {
        "request": request,
        "book": book,
        "user_login": user_login})


@app.get("/download/{book_id}")
async def download_file(book_id: int):
    from fastapi.responses import FileResponse
    # Получите информацию о книге из базы данных
    response = await make_request("GET", f"{config.DB_API_URL}/books/{book_id}/")
    book = response.json()

    # Путь к файлу книги
    file_path = book["file_path"]

    # Проверьте, существует ли файл
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")

    # Возвращайте файл для скачивания
    return FileResponse(path=file_path, filename=os.path.basename(file_path), media_type="application/octet-stream")

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.URL, port=config.MAIN_PORT)
