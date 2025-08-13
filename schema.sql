CREATE TABLE users (
    id INTEGER NOT NULL,
    username TEXT NOT NULL,
    hash TEXT NOT NULL,

    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX username ON users (username);

CREATE TABLE items (
    id INTEGER NOT NULL,
    title TEXT NOT NULL,
    image_path TEXT NOT NULL,
    price NUMERIC NOT NULL DEFAULT 0.00,
    description TEXT,

    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX title ON items (title);

CREATE TABLE cart (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,

    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (item_id) REFERENCES items(id),

    PRIMARY KEY (id)
);

CREATE TABLE orders (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    date NUMERIC NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',

    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (item_id) REFERENCES items(id),

    PRIMARY KEY (id)
);

CREATE TABLE admins (
    id INTEGER NOT NULL,
    username TEXT NOT NULL,
    hash TEXT NOT NULL,
    
    PRIMARY KEY (id)
);
