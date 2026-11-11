from fastapi import APIRouter
from app.services.coingecko_service import get_market_data

router = APIRouter()


@router.get("/market")
def market_data():
    data = get_market_data()
    return data