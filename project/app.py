import os

# Import SQLAlchemy components for database operations
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Import Flask and related modules for building a web application
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from cs50 import SQL  # Import CS50 library for SQL operations
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3

# Import custom helper functions and filters
from helpers import login_required, tru, lookup, usd
import jinja2

# Configure the Flask application
app = Flask(__name__)
env = jinja2.Environment()
env.filters["tru"] = tru

# Define custom filters for the Jinja2 template engine
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["tru"] = tru

# Configure session to use the filesystem for storing session data
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQLite database using CS50 library
db = SQL("sqlite:///data.db")

# Ensure that responses are not cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Route to the "learn" page
@app.route("/learn")
def learn():
    return render_template("learn.html")

# Route to the "mission" page
@app.route("/mission")
def mission():
    return render_template("mission.html")

# Main route for the application, showing the portfolio of stocks
@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Retrieve the stocks and shares associated with the user
    values = db.execute("SELECT stock, shares FROM stocks WHERE user_id = ?", session["user_id"])

    # Retrieve the cash balance of the user
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

    current_prices = []
    holdings = 0

    # Calculate the current prices of the user's stocks and total holdings
    for i in values:
        price = lookup(i["stock"])["price"]
        current_prices.append(price)
        holdings += i["shares"] * price

    net = []
    roi = []

    # Calculate the net gain/loss and ROI for each stock
    for i in range(len(values)):
        hold = db.execute(
            "SELECT price FROM transactions WHERE (action = 'buy' OR action='short') AND (stock = ?) AND (user_id = ?) ORDER BY time DESC LIMIT 1",
            values[i]["stock"], session["user_id"]
        )
        roi.append(((current_prices[i] - hold[0]["price"]) / hold[0]["price"]) * 100)
        if values[i]["shares"] > 0:
            net.append((current_prices[i] - hold[0]["price"]) * values[i]["shares"])
        else:
            net.append(-(hold[0]["price"] - current_prices[i]) * values[i]["shares"])

    print(net, roi)
    
    # Render the "index.html" template with data for display
    return render_template("index.html", values=values, cash=cash, prices=current_prices, holdings=holdings, net=net, roi=roi)



# Route to buy shares of stock
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # Handle form submission when the HTTP method is POST
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Validate user input for the stock symbol
        if symbol == "":
            flash("Must provide a stock symbol")
            return redirect("/buy")

        # Validate user input for the number of shares
        if shares == "":
            flash("Must provide the number of shares")
            return redirect("/buy")

        symbol = symbol.upper()

        # Check if the entered stock symbol is valid
        current_price = lookup(symbol)
        if current_price is None:
            flash("Enter a valid stock symbol")
            return redirect("/buy")

        try:
            shares = int(shares)
        except:
            flash("Enter a valid number of shares")
            return redirect("/buy")
        if shares <= 0:
            flash("Enter a valid number of shares")
            return redirect("/buy")

        # Get the current balance of the user
        current_balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

        current_price = lookup(symbol)["price"]

        # Check if the user has sufficient funds to make the purchase
        if current_price * shares > current_balance:
            flash("Insufficient funds")
            return redirect("/buy")

        holdings = db.execute("SELECT * FROM stocks WHERE user_id = ?", session["user_id"])
        exist = False

        for i in range(len(holdings)):
            if symbol in holdings[i]["stock"]:
                if holdings[i]["shares"] > 0:
                    x = db.execute("SELECT shares FROM stocks WHERE user_id = ? AND stock = ?", session["user_id"], symbol)[0]["shares"]

                    db.execute("UPDATE stocks SET shares = ? WHERE user_id=? AND stock=?", x + shares, session["user_id"], symbol)
                    exist = True
                else:
                    flash("You can't short and own a stock at the same time")
                    return redirect("/buy")

        if exist == False:
            db.execute("INSERT INTO stocks (user_id, stock, shares) VALUES(?, ?, ?)", session["user_id"], symbol, shares)

        db.execute("INSERT INTO transactions (user_id, stock, shares, price, action) VALUES (?, ?, ?, ?, 'buy')", session["user_id"], symbol, shares, current_price)
        db.execute("UPDATE users SET cash = ? WHERE id=?", current_balance - (current_price * shares), session["user_id"])

        return redirect("/")
    else:
        # Render the "buy.html" template when the HTTP method is GET
        return render_template("buy.html")

# Route to short shares of stock
@app.route("/short", methods=["GET", "POST"])
@login_required
def short():
    """Short shares of stock"""

    # Handle form submission when the HTTP method is POST
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Validate user input for the stock symbol
        if symbol == "":
            flash("Must provide a stock symbol")
            return redirect("/short")

        # Validate user input for the number of shares
        if shares == "":
            flash("Must provide the number of shares")
            return redirect("/short")

        symbol = symbol.upper()

        # Check if the entered stock symbol is valid
        current_price = lookup(symbol)
        if current_price is None:
            flash("Enter a valid stock symbol")
            return redirect("/short")

        try:
            shares = int(shares)
        except:
            flash("Enter a valid number of shares")
            return redirect("/short")
        if shares <= 0:
            flash("Enter a valid number of shares")
            return redirect("/short")

        # Get the current balance of the user
        current_balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

        current_price = lookup(symbol)["price"]

        holdings = db.execute("SELECT * FROM stocks WHERE user_id = ?", session["user_id"])
        exist = False

        for i in range(len(holdings)):
            if symbol in holdings[i]["stock"]:
                if holdings[i]["shares"] < 0:
                    x = db.execute("SELECT shares FROM stocks WHERE user_id = ? AND stock = ?", session["user_id"], symbol)[0]["shares"]

                    db.execute("UPDATE stocks SET shares = ? WHERE user_id=? AND stock=?", x - shares, session["user_id"], symbol)
                    exist = True
                else:
                    flash("You can't short and own a stock at the same time")
                    return redirect("/short")

        if exist == False:
            db.execute("INSERT INTO stocks (user_id, stock, shares) VALUES(?, ?, ?)", session["user_id"], symbol, -shares)

        db.execute("UPDATE users SET cash = ? WHERE id=?", current_balance + (current_price * shares), session["user_id"])
        db.execute("INSERT INTO transactions (user_id, stock, shares, price, action) VALUES (?, ?, ?, ?, 'short')", session["user_id"], symbol, shares, current_price)

        return redirect("/")
    else:
        # Render the "short.html" template when the HTTP method is GET
        return render_template("short.html")
    

# Route to display transaction history
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Retrieve transaction history for the user from the database
    values = db.execute(
        "SELECT stock, shares, time, action, price FROM transactions WHERE user_id = ? ORDER BY id DESC",
        session["user_id"],
    )
    
    # Render the "history.html" template with transaction history data
    return render_template("history.html", values=values)


# Route for user login
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id (clear the session)
    session.clear()

    # Handle user login request via both GET and POST methods
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide a username")
            return redirect("/login")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide a password")
            return redirect("/login")

        # Query the database for the provided username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and the provided password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            flash("Invalid username and/or password")
            return redirect("/login")

        # Remember the user who has logged in by storing their user_id in the session
        session["user_id"] = rows[0]["id"]

        # Redirect the user to the home page
        return redirect("/")
    
    # Handle GET request by rendering the "login.html" template
    else:
        return render_template("login.html")

# Route to log the user out
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id (clear the session)
    session.clear()

    # Redirect the user to the login form
    return redirect("/")

# Route to get a stock quote
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")

        # Retrieve stock information for the provided symbol
        values = lookup(symbol)

        if values is None:
            flash("Enter a valid stock symbol")
            return redirect("/quote")
        
        # Render the "quoted.html" template with stock information
        return render_template("quoted.html", values=values)
    else:
        # Render the "quote.html" template for the GET request
        return render_template("quote.html")

# Route for user registration
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if username == "":
            flash("Must provide a username")
            return redirect("/register")
        
        # Check if the username already exists in the database
        for i in db.execute("SELECT username FROM users"):
            if username == i["username"]:
                flash("Username already exists")
                return redirect("/register")

        if password == "":
            flash("Must provide a password")
            return redirect("/register")

        if confirmation == "":
            flash("Must confirm the password")
            return redirect("/register")

        if password != confirmation:
            flash("Passwords do not match")
            return redirect("/register")

        if len(password) < 8:
            flash("Password must be at least 8 characters")
            return redirect("/register")

        check1 = False
        check2 = False

        for i in range(len(password)):
            if password[i].isdigit():
                check1 = True
            if password[i].isalpha():
                check2 = True

        if check1 != True:
            flash("Password must include a number")
            return redirect("/register")

        if check2 != True:
            flash("Password must include a letter")
            return redirect("/register")

        # Insert the new user into the database
        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            username,
            generate_password_hash(password),
        )
        return redirect("/")
    
    else:
        # Render the "register.html" template for the GET request
        return render_template("register.html")

# Route to sell shares of stock
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if symbol == "":
            flash("Must provide a stock symbol")
            return redirect("/sell")

        if shares == "":
            flash("Must provide the number of shares")
            return redirect("/sell")

        symbol = symbol.upper()
        shares = int(shares)

        current_price = lookup(symbol)

        if current_price is None:
            flash("Enter a valid stock symbol")
            return redirect("/sell")

        if shares <= 0:
            flash("Enter a valid number of shares")
            return redirect("/sell")

        current_shares = db.execute(
            "SELECT shares FROM stocks WHERE user_id=? AND stock=?",
            session["user_id"],
            symbol,
        )

        if len(current_shares) == 0:
            flash("You don't own that stock")
            return redirect("/sell")

        current_shares = current_shares[0]["shares"]

        if shares > current_shares:
            flash("You don't own that many shares")
            return redirect("/sell")

        current_balance = db.execute(
            "SELECT cash FROM users WHERE id=?", session["user_id"]
        )[0]["cash"]

        current_price = lookup(symbol)["price"]

        if current_shares - shares == 0:
            db.execute(
                "DELETE FROM stocks WHERE stock=? AND user_id=?",
                symbol,
                session["user_id"],
            )

        else:
            db.execute(
                "UPDATE stocks SET shares = ? WHERE user_id=? AND stock=?",
                current_shares - shares,
                session["user_id"],
                symbol,
            )

        db.execute(
            "UPDATE users SET cash = ? WHERE id=?",
            current_balance + (current_price * shares),
            session["user_id"],
        )

        db.execute(
            "INSERT INTO transactions (user_id, stock, shares, price, action) VALUES (?, ?, ?, ?, 'sell')",
            session["user_id"],
            symbol,
            shares,
            current_price,
        )
        return redirect("/")
    else:
        # Retrieve the stocks owned by the user for display
        current_stocks = db.execute(
            "SELECT stock FROM stocks WHERE user_id=? AND shares>0",
            session["user_id"]
        )

        # Render the "sell.html" template with the list of stocks
        return render_template("sell.html", stocks=current_stocks)

# Route to cover (buy back) short shares of stock
@app.route("/cover", methods=["GET", "POST"])
@login_required
def cover():
    """Cover (buy back) short shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if symbol == "":
            flash("Must provide a stock symbol")
            return redirect("/cover")

        if shares == "":
            flash("Must provide the number of shares")
            return redirect("/cover")

        symbol = symbol.upper()
        shares = int(shares)

        current_price = lookup(symbol)

        if current_price is None:
            flash("Enter a valid stock symbol")
            return redirect("/cover")

        if shares <= 0:
            flash("Enter a valid number of shares")
            return redirect("/cover")

        current_shares = db.execute(
            "SELECT shares FROM stocks WHERE user_id=? AND stock=?",
            session["user_id"],
            symbol,
        )

        if len(current_shares) == 0:
            flash("You aren't shorting that stock")
            return redirect("/cover")

        current_shares = current_shares[0]["shares"]

        if -shares < current_shares:
            flash("You aren't shorting that many shares")
            return redirect("/cover")

        current_balance = db.execute(
            "SELECT cash FROM users WHERE id=?", session["user_id"]
        )[0]["cash"]

        current_price = lookup(symbol)["price"]

        if current_shares + shares == 0:
            db.execute(
                "DELETE FROM stocks WHERE stock=? AND user_id=?",
                symbol,
                session["user_id"],
            )

        else:
            db.execute(
                "UPDATE stocks SET shares = ? WHERE user_id=? AND stock=?",
                current_shares + shares,
                session["user_id"],
                symbol,
            )

        db.execute(
            "UPDATE users SET cash = ? WHERE id=?",
            current_balance - (current_price * shares),
            session["user_id"],
        )

        db.execute(
            "INSERT INTO transactions (user_id, stock, shares, price, action) VALUES (?, ?, ?, ?, 'cover')",
            session["user_id"],
            symbol,
            shares,
            current_price,
        )
        return redirect("/")
    else:
        # Retrieve the short positions held by the user for display
        current_stocks = db.execute(
            "SELECT stock FROM stocks WHERE user_id=? AND shares<0",
            session["user_id"]
        )

        # Render the "cover.html" template with the list of short positions
        return render_template("cover.html", stocks=current_stocks)