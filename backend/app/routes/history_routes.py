from fastapi import APIRouter
import json

router = APIRouter()

FILE_PATH = "data/trade_history.json"


@router.get("/history")
def get_history():

    try:

        with open(FILE_PATH, "r") as file:
            history = json.load(file)

        return history[::-1]

    except:

        return []