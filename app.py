from fastapi import FastAPI, HTTPException, Request
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
import os
import traceback

templates = Jinja2Templates(directory="templates")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse('groups.html', context={'request': request})