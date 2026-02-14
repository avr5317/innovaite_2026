from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routes.device import router as device_router
from app.routes.requests import router as requests_router
from app.routes.ai_routes import router as ai_router

app = FastAPI(title="Mutual Aid API", version="1.0")

origins_env = os.getenv("CORS_ORIGINS", "")
allow_origins = [o.strip() for o in origins_env.split(",") if o.strip()] or [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(device_router, prefix="/v1", tags=["device"])
app.include_router(ai_router, prefix="/v1", tags=["ai"])
app.include_router(requests_router, prefix="/v1", tags=["requests"])
