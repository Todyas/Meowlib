from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import create_db_and_tables, Books, SessionDep
from typing import List

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles


app = FastAPI()

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
