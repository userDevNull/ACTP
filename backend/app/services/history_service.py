import json
from datetime import datetime

FILE_PATH = "data/trade_history.json"


def save_trade(signal_data):

    try:

        with open(FILE_PATH, "r") as file:
            history = json.load(file)

    except:
        history = []

    signal_data["timestamp"] = str(datetime.now())

    history.append(signal_data)

    with open(FILE_PATH, "w") as file:
        json.dump(history, file, indent=4)