from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import workloads, configs, team

app = FastAPI(title="inf-hub")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(workloads.router)
app.include_router(configs.router)
app.include_router(team.router)
