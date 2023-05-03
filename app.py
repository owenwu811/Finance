
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    """The reason we do not want to cache responses is to ensure that the user is always presented with the most up-to-date information. If we were to cache responses, the user may see outdated information if the page has not been refreshed since the last time the information was updated. This can be particularly problematic in the context of a financial application like this, where accurate and current data is critical. By setting these headers, we ensure that the browser does not cache any content, forcing it to request fresh data from the server each time the user visits the page."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response
@app.route("/")
@login_required
def index():
    """Show user's portfolio of stocks"""
    #get the user's id - for the user currently logged in
    user_id = session["user_id"] #session stores the id of the currently logged in user
    #Retrieve user's stocks from the database - which stocks the user owns
    stocks = db.execute("SELECT symbol SUM(shares) AS total_shares FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0",
                  user_id=user_id)
    #retrieve user's cash balance from database using the values for a particular row
    #let's us access the cash value from the resulting dictionary by retrieving the first row from list of rows
    user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)[0] #retrieves first row from list of rows and returns as dictionary. keys correspond to column names while values corresponding to the database values
    cash = user["cash"]
    #initialize variables for the table
    rows = []
    total_value = cash
    #Loop through user's stocks and retrieve CURRENT PRICES OF EACH STOCK using lookup
    for stock in stocks:
        symbol = stock['symbol']
        shares = stock['total_shares']
        current_price = lookup(symbol)['price'] #the current price of each stock
        total_stock_value = current_price * shares #total value of each holding (share * price)
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
    else:
        symbol = request.form.get("symbol") #Require that a user input a stock’s symbol, implemented as a text field whose name is symbol.
        #Require that a user input a number of shares, implemented as a text field whose name is shares.
        shares = request.form.get("shares")
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
    stock = lookup(symbol) #calling lookup to lookup current stock's price
    price = stock["price"]
    total_cost = price * shares
    #check if user can afford the purchase by SELECTING how much cash the user has in users table
    user = db.execute("SELECT * FROM users WHERE id = :user_id", user_id=session["user_id"]).fetchone()
    if user["cash"] < total_cost:
        return apology ("Not enough cash to complete the purchase")
    #update the user's cash balance
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
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = :user_id ORDER BY timestamp DESC", user_id=session["user_id"])
    #Create HTML table header
    table = "<table><tr><th>Symbol</th><th>Type</th><th>Price</th><th>Shares</th><th>Timestamp</th></tr>"
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
    if request.method == "POST": #request.method is a built-in variable in flask that represents the http method used by the client when making a request to the server

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    # Complete the implementation of register in such a way that it allows a user to register for an account via a form.

#Require that a user input a username,
# implemented as a text field whose name is username.
# Render an apology if the user’s input is blank or the username already exists.
#Require that a user input a password,
# implemented as a text field whose name is password, and then that same password again,
# implemented as a text field whose name is confirmation. Render an apology if either input is blank or the passwords do not match.
#Submit the user’s input via POST to /register.
#INSERT the new user into users, storing a hash of the user’s password, not the password itself. Hash the user’s password with generate_password_hash Odds are you’ll want to create a new template (e.g., register.html) that’s quite similar to login.html.
#Once you’ve implemented register correctly, you should be able to register for an account and log in (since login and logout already work)! And you should be able to see your rows via phpLiteAdmin or sqlite3.
    username = request.form.get("username")
    if not username:
        return apology("please input a username", 400)
    #we are just comparing the inputted username from the user's form to the username in the database
    rows = db.execute("SELECT * FROM USERS WHERE username = :username", username=username) #This line is necessary to check if the username entered by the user during registration already exists in the database or not.
    #ensure a username dosen't already exist
    if len(rows) != 0:
        return apology("username already exists", 400)
    #ensure a password was submitted and confirmed
    password = request.get.form("password")
    confirmation = request.get.confirmation("confirmation")
    if not password or not confirmation:
        return apology("must provide password and confirmation", 400)
    elif password != confirmation:
        return apology("password's don't match", 400)
    #hash the password
    hashed_password = generate_password_hash(password)
    #insert the new user into the users database
    db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hashed_password)
    #redirect the user to the homepage
    return redirect("/")
#User reached route via GET (as by clicking a link or via redirect)

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
    else:
        #Get the stock symbol and number of shares from the form
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
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
        stock = lookup(symbol)
        price = stock["price"]
        #Calculate the total sale price
        total_sale = price * shares
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
