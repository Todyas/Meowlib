import time
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


# Configure directories
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
os.makedirs(config.UPLOAD_DIR, exist_ok=True)
# Ensure covers directory exists
os.makedirs("static/covers", exist_ok=True)

# Helper function for HTTP requests


async def make_request(method: str, url: str, **kwargs):
    import httpx

    for _ in range(3):
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


def generate_filename(user_id: str, book_id: str, original_name: str, extension: str = None) -> str:
    sanitized_name = "_".join(original_name.split()).replace(
        "/", "_").replace("\\", "_")
    ext = extension or Path(original_name).suffix
    return f"{user_id}_{book_id}_{sanitized_name}_{int(time.time())}{ext}"


def generate_cover_image(book_file_path: str, cover_file_path: str) -> str:
    """
    Generate a cover image from the first page of a PDF or the first image in an ePub.
    Save the cover image and return the path. If not successful, return None.
    """
    ext = Path(book_file_path).suffix.lower()
    try:
        if ext == ".pdf":
            images = convert_from_path(
                book_file_path, first_page=1, last_page=1)
            if images:
                images[0].save(cover_file_path, "JPEG")
                return cover_file_path
        elif ext == ".epub":
            book = epub.read_epub(book_file_path)
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE:
                    with open(cover_file_path, "wb") as f:
                        f.write(item.get_content())
                        print(f"Генерация обложки для файла {
                              book_file_path} завершена. Сохранено в: {cover_file_path}")

                    return cover_file_path
    except Exception as e:
        print(f"[generate_cover_image] Error processing {ext}: {e}")
    return None


# =================================== Рутинг ===================================


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login_post(request: Request, login: str = Form(...), password: str = Form(...)):
    try:
        response = await make_request(
            "POST",
            f"{config.DB_API_URL}/users/authenticate/",
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
        await make_request("POST", f"{config.DB_API_URL}/users/", json={
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
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authorization required")

    # Генерим пути
    book_path = os.path.join(
        config.UPLOAD_DIR,
        generate_filename(user_id, "new", book_file.filename)
    )
    cover_path = os.path.join(
        "app", "static", "covers",
        generate_filename(user_id, "new", "cover.jpg")
    )

    # Сохраняем файл книги
    from aiofiles import open as aio_open
    async with aio_open(book_path, "wb") as f:
        await f.write(await book_file.read())

    # Сохраняем или генерируем обложку
    if cover_file:
        async with aio_open(cover_path, "wb") as f:
            await f.write(await cover_file.read())
    else:
        generated_cover = generate_cover_image(book_path, cover_path)
        if generated_cover:
            cover_path = generated_cover
        else:
            cover_path = None

    # Сохраняем данные в базу
    await make_request("POST", f"{config.DB_API_URL}/books/", json={
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
    response = await make_request("GET", f"{config.DB_API_URL}/books/{book_id}/")
    book = response.json()

    file_path = book["file_path"]

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")

    return FileResponse(path=file_path, filename=os.path.basename(file_path), media_type="application/octet-stream")


@app.get("/edit/{book_id}", response_class=HTMLResponse)
async def edit_book_get(request: Request, book_id: int):
    user_login = request.cookies.get("username")
    response = await make_request("GET", f"{config.DB_API_URL}/books/{book_id}/")
    book = response.json()
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
    book_file: UploadFile = None
):
    user_login = request.cookies.get("username")
    if not user_login:
        raise HTTPException(status_code=401, detail="Authorization required")

    book_response = await make_request("GET", f"{config.DB_API_URL}/books/{book_id}/")
    book = book_response.json()

    book_path = book["file_path"]
    if book_file:
        book_path = os.path.join(
            config.UPLOAD_DIR,
            generate_filename(user_login, str(book_id), book_file.filename)
        )
        from aiofiles import open as aio_open
        async with aio_open(book_path, "wb") as f:
            await f.write(await book_file.read())

    cover_path = book["cover_path"] or os.path.join(
        "static", "covers",
        generate_filename(user_login, str(book_id), "cover.jpg")
    )
    if cover_file:
        from aiofiles import open as aio_open
        async with aio_open(cover_path, "wb") as f:
            await f.write(await cover_file.read())
    else:
        if book_file:
            generate_cover_image(book_path, cover_path)

    await make_request("PATCH", f"{config.DB_API_URL}/books/{book_id}/", json={
        "title": title,
        "author": author,
        "description": description,
        "file_path": book_path,
        "cover_path": cover_path
    })

    return RedirectResponse(url="/", status_code=303)


@app.get("/delete/{book_id}")
async def delete_book_route(book_id: int, request: Request):
    # Проверка авторизации пользователя
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Проверить, существует ли книга и принадлежит ли она пользователю
    response = await make_request("GET", f"{config.DB_API_URL}/books/{book_id}/")
    book = response.json()
    if book["user_id"] != int(user_id):
        raise HTTPException(
            status_code=403, detail="Удаление книги не разрешено")

    # Удалить книгу из базы данных
    await make_request("DELETE", f"{config.DB_API_URL}/books/{book_id}/")

    # Удалить файл книги и обложку
    if os.path.exists(book["file_path"]):
        os.remove(book["file_path"])
    if book["cover_path"] and os.path.exists(book["cover_path"]):
        os.remove(book["cover_path"])

    return RedirectResponse(url="/", status_code=303)


# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.URL, port=config.MAIN_PORT)
