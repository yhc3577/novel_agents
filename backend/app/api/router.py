from fastapi import APIRouter

from app.api import analysis, auth, projects, writing

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(writing.router)
api_router.include_router(analysis.router)
