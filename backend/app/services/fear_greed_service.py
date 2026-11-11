import requests


def get_fear_greed():

    try:

        url = "https://api.alternative.me/fng/"

        response = requests.get(url)

        data = response.json()

        latest = data["data"][0]

        return {
            "value": latest["value"],
            "classification":
                latest["value_classification"]
        }

    except:

        return {
            "value": "N/A",
            "classification": "Unknown"
        }