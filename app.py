from ast import literal_eval
from datetime import datetime
import db_utils # SQLite3: Connect on demand
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from helpers import admin_login_required, allowed_file, login_required, usd
import logging
import os
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Initialize Flask application
app = Flask(__name__)

# Configure application (e.g., store session on disk)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["UPLOAD_FOLDER"] = "static/images"
app.config["MAX_FILE_SIZE"] = 4 * (1024 * 1024) # 4 MB limit
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

# A list of statuses an order can have
STATUSES = ["cancelled", "delivered", "pending", "sent"]

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


@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    flash("File too large. Max size is 4 MB.", "error")
    return redirect(url_for("admin_new_item"))


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

    return redirect(url_for("orders"))


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


@app.route("/item/<int:id>")
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

@app.route("/admin")
def admin():
    return redirect(url_for("admin_orders"))


@app.route("/admin/orders")
@admin_login_required
def admin_orders():
    """Display orders to admin (i.e., show admin panel)."""

    orders = {}

    for status in STATUSES:
        orders[status] = db_utils.execute(
            "SELECT * FROM orders WHERE orders.status = ?", (status,)
        )

    return render_template("admin/orders.html", orders=orders, statuses=STATUSES)


@app.route("/admin/delete-item", methods=["POST"])
@admin_login_required
def admin_delete_item():
    """Permanently delete an item from the database."""

    id = request.form.get("id")

    if id:
        rows = db_utils.execute("SELECT filename FROM items WHERE id = ?",
            (id,))
        db_utils.execute("DELETE FROM items WHERE id = ?", (id,))

        # Remove image from disk
        os.remove(os.path.join(app.config["UPLOAD_FOLDER"], rows[0]["filename"]))

        flash(f"Successfully deleted an item of id: {id}", "info")

    return redirect(url_for("admin_items"))


@app.route("/admin/edit-item/<int:id>", methods=["GET", "POST"])
@admin_login_required
def admin_edit_item(id):
    """Edit an item in the database."""

    if request.method == "POST":

        title = request.form.get("title")
        # image = request.form.get("image")
        price = request.form.get("price")
        description = request.form.get("description")

        try:
            price = float(price)
        except ValueError:
            flash("Price must be a real number.", "error")
            return redirect(url_for("admin_edit_item", id=id))

        if title and price and description:
            db_utils.execute("""
                UPDATE items SET title = ?, price = ?, description = ? WHERE id = ?
                """, (title, price, description, id))
        
        flash(f"Successfully updated an item of id: {id}", "info")
        return redirect(url_for("admin_items"))

    else:
        
        rows = db_utils.execute("SELECT * FROM items WHERE id = ?", (id,))
        return render_template("admin/edit-item.html", item=rows[0])


@app.route("/admin/items")
@admin_login_required
def admin_items():
    """Display a list of items in database."""

    items = db_utils.execute("SELECT * FROM items")

    return render_template("admin/items.html", items=items)


@app.route("/admin/new-item", methods=["GET", "POST"])
@admin_login_required
def admin_new_item():
    """Add a new item to the database."""

    if request.method == "POST":
        
        title = request.form.get("title")
        price = request.form.get("price")
        description = request.form.get("description")

        try:
            price = float(price)
        except ValueError:
            flash("Price must be a real number.", "error")
            return redirect(url_for("admin_new_item"))

        if title and price and description:

            # Check if the POST request has a file part
            if 'file' not in request.files:
                flash("No file part.", "error")
                return redirect(url_for("admin_new_item"))
            
            file = request.files['file']

            # Make sure user selects a file
            if file.filename == "":
                flash("No selected file.", "error")
                return redirect(url_for("admin_new_item"))
            
            if file and allowed_file(file.filename):

                filename = secure_filename(file.filename)
                _, extension = os.path.splitext(filename)

                current_top_id = db_utils.execute("SELECT MAX(id) as n FROM items")
                new_id = int(current_top_id[0]["n"]) + 1 if current_top_id[0]["n"] else 1
                
                new_name = str(new_id) + extension

                image_path = os.path.join(app.config["UPLOAD_FOLDER"], new_name)
                file.save(image_path)

                db_utils.execute(
                    """
                    INSERT INTO items (title, filename, price, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    (title, new_name, price, description)
                )
                
                flash(f"Successfully added a new item of id: {new_id}")
                return redirect(url_for("admin_items"))
        
        else:

            flash("Missing title, price or description.", "error")
            return redirect(url_for("admin_new_item"))
    
    else:
        return render_template("admin/new-item.html")


@app.route("/admin/update-status", methods=["POST"])
@admin_login_required
def admin_update_status():
    """Update the status of an item.
    A status can be: pending, sent, delivered, cancelled."""

    order_id = request.form.get("order_id")
    status = request.form.get("status")

    if status and status in STATUSES and order_id:
        db_utils.execute("UPDATE orders SET status = ? WHERE id = ?",
            (status, order_id))
    
    return redirect(url_for("admin_orders"))

# --- Admin: Auth ---

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Log admin in."""

    # Forget any admin_id
    session.pop("admin_id", None)

    # User reached route via POST (by submitting a form via POST)
    if request.method == "POST":
        
        username = request.form.get("username")
        password = request.form.get("password")

        # Ensure values for fields were provided
        if not username:
            flash("Username is required.", "error")
            return redirect(url_for("admin_login"))
        elif not password:
            flash("Password is required.", "error")
            return redirect(url_for("admin_login"))
        
        # Query database for username
        rows = db_utils.execute("SELECT * FROM admins WHERE username = ?", (username,))

        # Ensure username exists in database and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            flash("Invalid username and/or password.", "error")
            return redirect(url_for("admin_login"))
        
        # Remember which user has logged in
        session["admin_id"] = rows[0]["id"]

        # Redirect to admin panel/index
        return redirect(url_for("admin_orders"))

    # User reached route via GET (by clicking on a link, typing in a URL, via redirect)
    else:
        return render_template("admin/auth/login.html")


@app.route("/admin/logout")
def admin_logout():
    """Log admin out."""

    # Forget any admin_id
    session.clear()

    # Redirect to login form
    return redirect(url_for("admin_login"))


@app.route("/admin/register", methods=["GET", "POST"])
@admin_login_required
def admin_register():
    """Register a new admin (only logged-in admins can do this)."""

    # User reached route via POST (by submitting a form via POST)
    if request.method == "POST":
        
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        # Ensure user provided username, password, confirm
        if not username:
            flash("Username is required.", "error")
            return redirect(url_for("admin_register"))
        
        elif not password:
            flash("Password is required", "error")
            return redirect(url_for("admin_register"))
        
        elif not confirm or password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("admin_register"))
        
        # TODO: Use regex to make sure user provides a "strong" password
        elif len(password) < 8:
            flash("Password needs to be at least 8 characters long.", "error")
            return redirect(url_for("admin_register"))
        
        # Query database for username
        rows = db_utils.execute("SELECT * FROM admins WHERE username = ?", (username,))

        # Ensure username is not taken
        if len(rows) == 1:
            flash("Username is taken", "error")
            return redirect(url_for("admin_register"))
        
        # Insert the new user into admins table, storing a hash of the password
        db_utils.execute("INSERT INTO admins (username, hash) VALUES (?, ?)",
            (username, generate_password_hash(password)))
        
        # Flash a message and redirect to login page
        flash("Successfully registered. Please log in.", "info")
        return redirect(url_for("admin_login"))

    # User reached route via GET (by clicking on a link, typing in a URL, via redirect)
    else:
        return render_template("admin/auth/register.html")
