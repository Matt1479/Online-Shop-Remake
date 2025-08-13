from flask import redirect, session
from functools import wraps

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'])


def login_required(f):
    """
    Decorate routes to require login.
    https://flask.palletsprojects.com/en/stable/patterns/viewdecorators/#login-required-decorator
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    
    return decorated_function


def admin_login_required(f):
    """Decorate admin routes to require login"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("admin_id") is None:
            return redirect("/admin/login")
        return f(*args, **kwargs)
    
    return decorated_function


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
