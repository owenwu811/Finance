
import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

# Configure session to use filesystem (instead of signed cookies)
app, app.jinja_env.filters["usd"], app.config["SESSION_PERMANENT"], app.config["SESSION_TYPE"], db = Flask(__name__), usd, False, "filesystem", SQL("sqlite:///finance.db")
Session(app)

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    """The reason we do not want to cache responses is to ensure that the user is always presented with the most up-to-date information. If we were to cache responses, the user may see outdated information if the page has not been refreshed since the last time the information was updated. This can be particularly problematic in the context of a financial application like this, where accurate and current data is critical. By setting these headers, we ensure that the browser does not cache any content, forcing it to request fresh data from the server each time the user visits the page."""
    response.headers["Cache-Control"], response.headers["Expires"], response.headers["Pragma"] = "no-cache, no-store, must-revalidate", 0, "no-cache"
    return response
@app.route("/")
@login_required
def index():
    """Show user's portfolio of stocks"""
    #get the user's id for the user that is currently logged in
    user_id = session["user_id"] #session stores the id of the currently logged in user
    #Retrieve user's stocks from the database - which stocks the user owns
    stocks = db.execute("SELECT symbol SUM(shares) AS total_shares FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0",
                  user_id=user_id)
    #retrieve user's cash balance from database using the values for a particular row
    #let's us access the cash value from the resulting dictionary by retrieving the first row from list of rows
    user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)[0] #retrieves first row from list of rows and returns as dictionary. keys correspond to column names while values corresponding to the database values
    cash, rows, total_value = user["cash"], [], cash
    for stock in stocks:
        symbol, shares, current_price, total_stock_value = stock['symbol'], stock['total_shares'], lookup(symbol)['price'], current_price * shares #total value of each holding (share * price)
        total_value += total_stock_value
        rows.append((symbol, shares, current_price, total_stock_value))
    #return the template with the table and variables
    return render_template("index.html", rows=rows, cash=cash, total_value=total_value)
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """allows user to Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else: #post
        symbol, shares = request.form.get("symbol"), request.form.get("shares") #Require that a user input a stock’s symbol, implemented as a text field whose name is symbol.
        #Require that a user input a number of shares, implemented as a text field whose name is shares.
    #valid symbol
    if not symbol or lookup(symbol) is None: # #Render an apology if the input is blank or the symbol does not exist (as per the return value of lookup).
        return apology("Invalid Symbol")
    #validate shares
    try:
        shares = int(shares)
    except ValueError:  #Render an apology if the input is not a positive integer.
        return apology("Shares must be a positive integer")
    if shares < 1:
        return apology("Shares must be a positive integer")
    #Get stock info
    #lookup import comes from line 10
    stock, price, total_cost = lookup(symbol), stock["price"], price * shares  #calling lookup to lookup current stock's price
    #check if user can afford the purchase by SELECTING how much cash the user has in users table using the id of that user
    user = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"]).fetchone()
    if user["cash"] < total_cost:
        return apology ("Not enough cash to complete the purchase")
    #update the user's cash balance if the transaction does go through successfully
    db.execute("UPDATE users SET cash = cash  - :total_cost WHERE id = :user_id",
               total_cost=total_cost, user_id=session["user_id"])
    #insert purchase into purchases table
    db.execute("INSERT INTO purchases (user_id, symbol, shares, price, timestamp) VALUES (:user_id, :symbol, :shares, :price, DATETIME('now;'))",
               user_id=session["user_id"], symbol=symbol, shares=shares, price=price)
    #Upon completion, redirect the user to the home page
    flash("Purchase completed successfully")
    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show user's history of transactions"""
    #Query database for all transactions for current user
    transactions, table = db.execute("SELECT * FROM transactions WHERE user_id = :user_id ORDER BY timestamp DESC", user_id=session["user_id"]), "<table><tr><th>Symbol</th><th>Type</th><th>Price</th><th>Shares</th><th>Timestamp</th></tr>"
    #Create HTML table header
    #loop over transactions and generate table rows
    for transaction in transactions:
        if transaction["shares"] > 0:
            #This is a buy transaction
            type = "Buy"
        else:
            #This is a sell transaction
            type = "Sell"
        #Generate table row for transactions
        row = f"<tr><td>{transaction['symbol']}</td><td>{type}</td><td>${transaction['price']:,.2f}</td><td>{abs(transaction['shares'])}</td><td>{transaction['timestamp']}</td></tr>"
        #row = f"<tr><td>{transaction['symbol']}</td><td>{type?</td><td>${transaction['price']:,.2f}</td><td>{abs(transaction['shares']}</td><td>{transaction['timestamp']}</td></tr>"}}
        #add row to table
        table += row
    #close the HTML table
    #table variable is used to build a string that represents an HTML table so that we can concatenate strings with += operator
    #we are adding the closing "</table>" tag to the end of the table string, effectively closing the HTML table
    table += "</table>" #enclosed in quotation marks because it the "</table> text is a string that represents an HTML tag that closes the table.

    #Return HTML table with table
    return render_template("history.html", table=table)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("login.html", error="Invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        #handle form submission
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please enter a symbol", 400)
        #lookup the stock symbol using the lookup function
        stock = lookup(symbol)
        if not stock:
            return apology("Invalid symbol", 400)
        #return the quoted template with the stock information
        return render_template("quoted.html", stock=stock)
    else:
        #render the quote template with the form
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        # Ensure password confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)
        # Ensure password and confirmation match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)
        # Check if username already exists
        existing_user = db.execute("SELECT * FROM users WHERE username = :username",
                                   username=request.form.get("username"))
        if len(existing_user) > 0:
            return apology("username already exists", 400)
        # Insert new user into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                   username=request.form.get("username"),
                   hash=generate_password_hash(request.form.get("password")))
        # Commit changes to the database
        db.commit()
        # Redirect user to login page
        return redirect("/login")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        #GET THE USER'S STOCKS FROM THE DATABASE
        stocks = db.execute("SELECT symbol FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING SUM(shares) > 0",
                            user_id=session["user_id"] #session is imported in line 2
        )
        #Render the form to sell stocks
        return render_template("sell.html", stocks=stocks)
    else: #post method condition
        #retrieve the stock symbol and number of shares from the form
        symbol, shares = request.form.get("symbol"), int(request.form.get("shares"))
        #Check that the symbol and number of shares are valid
        if not symbol or not lookup(symbol):
            return apology("Invalid Symbol")
        if shares < 1:
            return apoplogy("Invalid number of shares")
        #Get the user's stocks from the database
        rows = db.execute("SELECT SUM(shares) AS total_shares FROM transactions WHERE user_id = :user_id AND symbol = :symbol",
                          user_id=session["user_id"],
                          symbol=symbol)
        #Check that the user has enough shares to sell
        if len(rows) != 1 or rows[0]["total_shares"] < shares:
            return apology("Not enough shares")
        #Get the current price of the stock
        stock, price, total_sale = lookup(symbol), stock["price"], price * shares
        #Calculate the total sale price
        #Update the user's cash balance
        db.execute("UPDATE users SET cash = cash + :total_sale WHERE id = :user_id",
                   total_sale=total_sale,
                   user_id=session["user_id"]
        )
        #Insert a new transaction into the database
        db.execute("INSERT INTO transactions(user_id, symbol, shares, price) VALUES (:user_id, :symbol, :shares, :price)",
        user_id=session["user_id"])
        symbol=symbol,
        shares=shares,
        price=price

    #Flash a success message, and redirect to main page
        flash("Sold")
        return redirect("/")
