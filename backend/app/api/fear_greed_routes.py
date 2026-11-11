from fastapi import APIRouter
from app.services.fear_greed_service import (
    get_fear_greed
)

router = APIRouter()


@router.get("/fear-greed")
def fear_greed():

    return get_fear_greed()