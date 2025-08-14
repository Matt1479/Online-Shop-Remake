import db_utils # SQLite3: Connect on demand
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from helpers import admin_login_required, login_required
import logging
from werkzeug.security import check_password_hash, generate_password_hash

# Initialize Flask application
app = Flask(__name__)

# Configure application (e.g., store session on disk)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["TEMPLATES_AUTO_RELOAD"] = True
Session(app)

# Set up the database
app.config["DATABASE"] = "store.db"
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

# --- User ---

@app.route("/")
@login_required
def index():
    """Show all items."""

    # TODO: Query database for items

    return render_template("user/index.html")


@app.route("/cart")
@login_required
def cart():
    """Show items in cart."""

    return "TODO"


@app.route("/checkout")
@login_required
def checkout():
    """Check user out."""

    return "TODO"


@app.route("/delete")
@login_required
def delete():
    """Delete an item from cart."""

    return "TODO"


@app.route("/item/<id>")
@login_required
def item():
    """Show an individual item."""

    return "TODO"


@app.route("/orders")
@login_required
def orders():
    """Show orders to the user."""
    
    return "TODO"


@app.route("/search")
@login_required
def search():
    """Search for an item by title."""

    return "TODO"


@app.route("/update-qty")
@login_required
def update_qty():
    """Update an item's quantity."""

    return "TODO"

# --- User: Auth ---

@app.route("/change-password")
@login_required
def change_password():
    """Change user's password."""

    return "TODO"


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
