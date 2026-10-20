PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    precio REAL NOT NULL CHECK (precio >= 0),
    cantidad INTEGER NOT NULL CHECK (cantidad >= 0)
);

CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
    total REAL NOT NULL CHECK (total >= 0),
    fecha TEXT NOT NULL,
    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE RESTRICT
);
