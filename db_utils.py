# SQLite3/Flask utilities

# Flask.g is a global object provided by Flask which can be used to store data
# and it will be available throughout the lifespan of a single request
from flask import current_app, g
import re
import sqlite3
import time
from typing import Union


def dict_factory(cursor, row):
    """
    Custom `row_factory` that returns each row as a dict,
    with column names mapped to values.
    """
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


def get_db():
    """
    Open a new database connection and return a reference to it.
    """
    db = getattr(g, "_database", None)
    if db is None:
        # Open a new database connection
        db = g._database = sqlite3.connect(current_app.config["DATABASE"])
        # Use a custom row_factory (queries return a `dict` instead of a `tuple`)
        db.row_factory = dict_factory
    return db


def get_query_type(query: str) -> str:
    match = re.match(r"^\s*(\w+)", query)
    return match.group(1).upper() if match else ""


def init_db(app):
    """
    Initializes a database with a given schema.
    """

    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()


def execute(query: str, args: Union[tuple, list] = (), executemany: bool = False):
    """
    Execute one or many SQL queries.

    Returns:
        - For `DELETE`/`UPDATE`, the number of rows deleted/updated;
        - For `INSERT`, the primary key of a newly inserted row, or
            the number of inserted rows if executemany=True and args is a list;
        - For `SELECT`, a `list` of `dict` (dictionaries), each of which represents
            a row;
    """
    db = get_db()
    query_type = get_query_type(query)
    cur = db.cursor()

    duration = None
    rows_count = None
 
    if current_app.config.get("DEBUG_DB"):
        start = time.time()

    try:
        if query_type == "SELECT":
            # Prepare one query to execute
            cur.execute(query, args)

            # Fetch all rows
            rows = cur.fetchall()

            rows_count = len(rows)

            # The database connection is closed by close_connection in app.py

            # Return a list of rows (`dict`)
            return rows
        
        elif query_type == "INSERT":
            if executemany and isinstance(args, list):
                # Prepare many queries to execute (provide a list here)
                cur.executemany(query, args)

                # Commit the transaction
                db.commit()

                rows_count = cur.rowcount

                # The database connection is closed by close_connection in app.py

                return cur.rowcount
            
            else:
                # Prepare one query to execute
                cur.execute(query, args)

                # Commit the transaction
                db.commit()

                rows_count = 1

                # The database connection is closed by close_connection in app.py

                return cur.lastrowid
            
        elif query_type in ["UPDATE", "DELETE"]:
            if executemany and isinstance(args, list):
                # Prepare many queries to execute (provide a list here)
                cur.executemany(query, args)
            else:
                # Prepare one query to execute
                cur.execute(query, args)

            # Commit the transaction
            db.commit()

            rows_count = cur.rowcount

            # The database connection is closed by close_connection in app.py

            return cur.rowcount
        
        else:
            raise ValueError(f"Unhandled SQL query type: {query_type}")

    except sqlite3.Error as e:
        current_app.logger.error(f"DB Error: {e} | Query: {query} | Args: {args}")
        raise

    finally:
        cur.close()

        if current_app.config.get("DEBUG_DB"):
            duration = (time.time() - start) * 1000 # ms
            current_app.logger.debug(
                f"Executed {query_type} in {duration:.2f}ms | "
                f"Executemany: {executemany} | Rows: {rows_count} | "
                f"Query: {query} | Args: {args}"
            )
