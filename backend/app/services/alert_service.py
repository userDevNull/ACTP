import json
from datetime import datetime, timedelta

FILE_PATH = "data/alert_state.json"

COOLDOWN_MINUTES = 30


def can_send_alert(symbol, signal):

    try:
        with open(FILE_PATH, "r") as file:
            state = json.load(file)
    except:
        state = {}

    key = f"{symbol}_{signal}"

    now = datetime.now()

    if key in state:

        last_sent = datetime.fromisoformat(
            state[key]
        )

        if now - last_sent < timedelta(
            minutes=COOLDOWN_MINUTES
        ):
            return False

    state[key] = now.isoformat()

    with open(FILE_PATH, "w") as file:
        json.dump(state, file, indent=4)

    return True