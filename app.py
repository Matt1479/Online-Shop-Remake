from ast import literal_eval
from datetime import datetime
import db_utils # SQLite3: Connect on demand
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from helpers import admin_login_required, login_required, usd
import logging
from werkzeug.security import check_password_hash, generate_password_hash

# Initialize Flask application
app = Flask(__name__)

# Configure application (e.g., store session on disk)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["TEMPLATES_AUTO_RELOAD"] = True
Session(app)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Set up the database
app.config["DATABASE"] = "_store.db"
app.config["DEBUG_DB"] = True

# Configure logging
if app.config["DEBUG_DB"]:
    app.logger.setLevel(logging.DEBUG)

# Initialize the database
db_utils.init_db(app)


@app.after_request
def after_request(response):
    """Ensure responses aren't cached."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.teardown_appcontext
def close_connection(exception):
    """
    Close database connection after every request.
    """
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# --- Error handlers ---

@app.errorhandler(404)
def not_found(e):
    return "TODO"


# --- API ---

@app.route("/api/search")
@login_required
def api_search():
    """Search for an item by title."""

    q = request.args.get("q")

    if q:
        items = db_utils.execute("SELECT * FROM items WHERE title LIKE ? LIMIT 15",
            ("%" + q + "%",))
    else:
        items = []

    # Return list of items in JSON format
    return jsonify(items)

# --- User ---

@app.route("/")
@login_required
def index():
    """Show all items."""

    # Query database for items
    rows = db_utils.execute("SELECT * FROM items")

    return render_template("user/index.html", items=rows)


@app.route("/cart", methods=["GET", "POST"])
@login_required
def cart():
    """Show items in cart."""

    # User reached route via POST (submitted a form)
    if request.method == "POST":

        """Add item to cart."""

        # Validate id and qty
        try:
            id = int(request.form.get("id"))
            qty = int(request.form.get("qty"))
            print(id, qty)
        except ValueError:
            flash("Invalid value(s).", "error")
            return redirect(url_for("cart"))
        
        if id and qty:
            rows = db_utils.execute("SELECT * from cart WHERE item_id = ? AND user_id = ?",
                (id, session["user_id"]))
            
            if len(rows) > 0:
                current_qty = int(rows[0]["quantity"])

                db_utils.execute("UPDATE cart SET quantity = ? WHERE item_id = ? AND user_id = ?",
                    (current_qty + qty, id, session["user_id"]))
                
            else:
                db_utils.execute("INSERT INTO cart (quantity, item_id, user_id) VALUES (?, ?, ?)",
                    (qty, id, session["user_id"]))
    
    """Select items from cart."""

    cart = db_utils.execute(
        "SELECT * FROM cart JOIN items ON items.id = cart.item_id WHERE cart.user_id = ?",
        (session["user_id"],))
    
    total = 0.00
    for item in cart:
        total += int(item["price"]) * int(item["quantity"])
    
    # Render cart.html to the user, passing in cart and total
    return render_template("user/cart.html", cart=cart, total=total)


@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    """Check user out."""

    items = request.form.get("cart")

    if items:
        flash("Thank you for your purchase.", "info")
        items = literal_eval(items)

        for item in items:
            db_utils.execute(
                "INSERT INTO orders (user_id, item_id, quantity, date) VALUES (?, ?, ?, ?)",
                (
                    session["user_id"],
                    item["item_id"],
                    item["quantity"],
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        db_utils.execute("DELETE FROM cart where user_id = ?", (session["user_id"],))

    return redirect(url_for("index"))


@app.route("/delete", methods=["POST"])
@login_required
def delete():
    """Delete an item from cart."""

    try:
        id = int(request.form.get("id"))
    except ValueError:
        flash("Invalid value(s).", "error")
        return redirect(url_for("cart"))
    
    if id:
        db_utils.execute("DELETE FROM cart WHERE item_id = ? AND user_id = ?",
            (id, session["user_id"]))
    
    return redirect(url_for("cart"))


@app.route("/item/<id>")
@login_required
def item(id):
    """Show an individual item."""

    rows = db_utils.execute("SELECT * FROM items WHERE id = ?", (id,))
    
    return render_template("user/item.html", item=rows[0])


@app.route("/orders")
@login_required
def orders():
    """Show orders to the user."""

    rows = db_utils.execute("""
        SELECT * FROM orders
        JOIN items on items.id = orders.item_id
        WHERE orders.user_id = ?""",
        (session["user_id"],))
    
    return render_template("user/orders.html", orders=rows)


@app.route("/update-qty", methods=["POST"])
@login_required
def update_qty():
    """Update an item's quantity."""

    # Validate item id and quantity
    try:
        id = int(request.form.get("id"))
        qty = int(request.form.get("qty"))
    except ValueError:
        flash("Invalid value(s)", "error")
        return redirect(url_for("cart"))
    
    if id and qty:
        db_utils.execute("UPDATE cart SET quantity = ? WHERE item_id = ? AND user_id = ?",
            (qty, id, session["user_id"]))
        
    return redirect(url_for("cart"))

# --- User: Auth ---

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change user's password."""
    
    # User reached route via POST (by submitting a form via POST)
    if request.method == "POST":
        
        current = request.form.get("current")
        new = request.form.get("new")
        confirm = request.form.get("confirm")

        # Ensure fields have values
        if not current or not new or not confirm:
            flash("Field(s) can't be empty.", "error")
            return redirect(url_for("change_password"))
        
        # Ensure current password is correct
        rows = db_utils.execute("SELECT hash FROM users WHERE id = ?",
            (session["user_id"],))
        if not check_password_hash(rows[0]["hash"], current):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("change_password"))
        
        # Ensure passwords match
        if new != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("change_password"))
        
        # Ensure new password is different than the current one
        if new == current:
            flash("Your new password can't be the same as the current password.", "error")
            return redirect(url_for("change_password"))
        
        # Ensure new password is at least 8 characters long (TODO: Use RegEx)
        if len(new) < 8:
            flash("Password needs to be at least 8 characters.", "error")
            return redirect(url_for("change_password"))
        
        # Update old hash with new
        db_utils.execute("UPDATE users SET hash = ? WHERE id = ?",
            (generate_password_hash(new), session["user_id"],))
        
        flash("Password changed successfully.", "info")
        return redirect(url_for("change_password"))
    
    # User reached route via GET (by clicking on a link, typing in a URL, via redirect)
    else:
        return render_template("user/auth/changepw.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """ Log user in."""

    # Forget any user_id
    session.pop("user_id", None)

    # User reached route via POST (by submitting a form via POST)
    if request.method == "POST":
        
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure user provided values for username and password
        if not username:
            flash("Username is required.", "error")
            return redirect(url_for("login"))
        
        elif not password:
            flash("Password is required", "error")
            return redirect(url_for("login"))
        
        # Query database for username
        rows = db_utils.execute("SELECT * FROM users WHERE username = ?", (username,))

        # Ensure username exists in database and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            flash("Invalid username and/or password.", "error")
            return redirect(url_for("login"))
        
        # Remember which user logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to index
        return redirect(url_for("index"))
    
    # User reached route via GET (by clicking on a link, typing in a URL, via redirect)
    else:
        return render_template("user/auth/login.html")


@app.route("/logout")
def logout():
    "Log user out."

    # Forget any user_id
    session.clear()

    # Redirect user to login route
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register a user."""

    # User reached route via POST (by submitting a form via POST)
    if request.method == "POST":
        
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        # Ensure user provided username, password, confirm
        if not username:
            flash("Username is required.", "error")
            return redirect(url_for("register"))
        
        elif not password:
            flash("Password is required", "error")
            return redirect(url_for("register"))
        
        elif not confirm or password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))
        
        # TODO: Use regex to make sure user provides a "strong" password
        elif len(password) < 8:
            flash("Password needs to be at least 8 characters long.", "error")
            return redirect(url_for("register"))
        
        # Query database for username
        rows = db_utils.execute("SELECT * FROM users WHERE username = ?", (username,))

        # Ensure username is not taken
        if len(rows) == 1:
            flash("Username is taken", "error")
            return redirect(url_for("register"))
        
        # Insert the new user into users table, storing a hash of the password
        db_utils.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
            (username, generate_password_hash(password)))
        
        # Redirect to login page
        return redirect(url_for("login"))

    # User reached route via GET (by clicking on a link, typing in a URL, via redirect)
    else:
        return render_template("user/auth/register.html")

# --- Admin ---

@app.route("/admin/orders")
@admin_login_required
def admin_orders():
    """Display orders to admin."""

    return "TODO"


@app.route("/admin/delete-item")
@admin_login_required
def admin_delete_item():
    """Permanently delete an item from the database."""

    return "TODO"


@app.route("/admin/edit-item")
@admin_login_required
def admin_edit_item():
    """Edit an item in the database."""

    return "TODO"


@app.route("/admin/items")
@admin_login_required
def admin_items():
    return "TODO"


@app.route("/admin/new-item")
@admin_login_required
def admin_new_item():
    """Add a new item to the database."""

    return "TODO"


@app.route("/admin/update-status")
@admin_login_required
def admin_update_status():
    """Update the status of an item.
    A status can be: pending, sent', delivered, cancelled."""

    return "TODO"

# --- Admin: Auth ---

@app.route("/admin/login")
def admin_login():
    """Log admin in."""

    return "TODO"


@app.route("/admin/logout")
def admin_logout():
    """Log admin out."""

    return "TODO"
