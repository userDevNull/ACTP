from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.history_routes import router as history_router
from app.api.market_routes import router as market_router
from app.api.signal_routes import router as signal_router
from app.api.fear_greed_routes import (
    router as fear_greed_router
)

app = FastAPI(title="Crypto AI Platform")

app.include_router(
    fear_greed_router
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ROUTES
app.include_router(market_router)
app.include_router(signal_router)
app.include_router(history_router)


@app.get("/")
def home():
    return {
        "message": "Crypto AI Platform Backend Running"
    }