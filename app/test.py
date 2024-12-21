import asyncio
from main import make_request
from config import config


async def main():
    response = await make_request(
        "POST",
        f"{config.DB_API_URL}/users/authenticate/",
        json={"username": "asd", "password": "asd"},
        headers={"Content-Type": "application/json"}
    )

    print(response.status_code, response.text)


asyncio.run(main())
