# Import necessary modules and packages
from flask import redirect, render_template, session
import subprocess
import urllib
import csv
import datetime
from functools import wraps
import pytz
import uuid
import requests

# Function to format a value with two decimal places


def tru(value):
    """Format a value with two decimal places"""
    return f"{value:,.2f}"

# Function to format a value as USD (United States Dollar)


def usd(value):
    """Format a value as USD (United States Dollar)"""
    return f"${value:,.2f}"


# Function to look up stock information by symbol
def lookup(symbol):
    """Look up stock information by symbol"""

    # Prepare API request
    symbol = symbol.upper()
    end = datetime.datetime.now(pytz.timezone("US/Eastern"))
    start = end - datetime.timedelta(days=7)

    # Yahoo Finance API URL
    url = (
        f"https://query1.finance.yahoo.com/v7/finance/download/{urllib.parse.quote_plus(symbol)}"
        f"?period1={int(start.timestamp())}"
        f"&period2={int(end.timestamp())}"
        f"&interval=1d&events=history&includeAdjustedClose=true"
    )

    # Query the API for stock data
    try:
        response = requests.get(
            url,
            cookies={"session": str(uuid.uuid4())},
            headers={"User-Agent": "python-requests", "Accept": "*/*"},
        )
        response.raise_for_status()

        # Parse and retrieve stock data from the CSV response
        quotes = list(csv.DictReader(
            response.content.decode("utf-8").splitlines()))
        quotes.reverse()
        price = round(float(quotes[0]["Adj Close"]), 2)
        return {"name": symbol, "price": price, "symbol": symbol}
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None

# Decorator for login required routes


def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if a user is logged in based on the session
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function
