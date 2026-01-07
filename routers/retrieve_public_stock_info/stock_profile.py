import requests as r
import json
import os
import yfinance as yf
from dotenv import load_dotenv
from datetime import datetime
import pytz

ENV_PATH = os.getenv("ENV_PATH")
load_dotenv(ENV_PATH)
api_key = os.getenv("FMP_API_KEY")

BASE_URL = "https://financialmodelingprep.com/stable/"


def response_to_json(data):
    try:
        json_response = data.json()
        # Check if the response is a list before trying to access index 0
        if isinstance(json_response, list) and len(json_response) > 0:
            json_data = json_response[
                0
            ]  # The api should returns a list of dictionaries
        else:
            json_data = json_response
    except (IndexError, ValueError):
        json_data = {}

    return json_data


def get_company_logo(profile_data):
    # Get the image separately since we have to check if the URL is valid
    try:
        image_url = profile_data.get("image", "N/A")
        image_valid = image_url != "N/A" and r.get(image_url).status_code == 200
        image = image_url if image_valid else None
    except:
        image = None

    return image


def get_earnings_date(yf_ticker: yf.Ticker, user_timezone_str: str):
    try:
        earnings_dates_df = yf_ticker.get_earnings_dates(limit=4)

        # Ensure the DataFrame is sorted by the earnings date
        earnings_dates_df.sort_index(ascending=True, inplace=True)

        next_earnings_date_utc = earnings_dates_df.index[0]

        # Convert Earnings date to user's timezone
        utc = pytz.utc
        user_tz = pytz.timezone(user_timezone_str)

        localized_date = next_earnings_date_utc.replace(tzinfo=utc).astimezone(user_tz)

        # Format output
        formatted_date = localized_date.strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        formatted_date = "N/A"

    return formatted_date


def get_stock_profile(ticker, user_timezone_str: str):
    # Get data from yahoo finance
    yf_ticker = yf.Ticker(ticker)
    yf_company_info = yf_ticker.info

    # Get additional data from FMP
    profile_response = r.get(
        url=f"{BASE_URL}profile?symbol={ticker}", params={"apikey": api_key}
    )
    dcf_response = r.get(
        url=f"{BASE_URL}discounted-cash-flow?symbol={ticker}",
        params={"apikey": api_key},
    )
    profile_data = response_to_json(profile_response)
    dcf_data = response_to_json(dcf_response)

    stock_info = {
        "symbol": profile_data.get("symbol", "N/A"),
        "companyName": profile_data.get("companyName", "N/A"),
        "logo": get_company_logo(profile_data),
        "website": profile_data.get("website", "N/A"),
        "description": profile_data.get("description", "N/A"),
        "price": profile_data.get("price", "N/A"),
        "exchangeShortName": profile_data.get("exchange", "N/A"),
        "mktCap": profile_data.get("marketCap", "N/A"),
        "industry": profile_data.get("industry", "N/A"),
        "earningsCallDate": get_earnings_date(yf_ticker, user_timezone_str),
        "analystRating": yf_company_info.get("recommendationKey", "N/A"),
        "forwardPE": yf_company_info.get("forwardPE", "N/A"),
        "dcf": dcf_data.get("dcf", "N/A"),
        "beta": profile_data.get("beta", "N/A"),
    }

    return stock_info


if __name__ == "__main__":
    ticker = input("Ticker: ")
    profile = get_stock_profile(ticker, "Europe/Berlin")

    print(json.dumps(profile, indent=4))

