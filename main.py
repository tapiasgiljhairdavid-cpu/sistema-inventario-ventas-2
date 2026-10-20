import sqlite3
from datetime import datetime

DB_NAME = "inventario.db"


def conectar():
    """Abre la base de datos y activa las claves foráneas."""
    conexion = sqlite3.connect(DB_NAME)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def crear_tablas():
    with conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                precio REAL NOT NULL CHECK(precio >= 0),
                cantidad INTEGER NOT NULL CHECK(cantidad >= 0)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL,
                cantidad INTEGER NOT NULL CHECK(cantidad > 0),
                precio_unitario REAL NOT NULL CHECK(precio_unitario >= 0),
                total REAL NOT NULL CHECK(total >= 0),
                fecha TEXT NOT NULL,
                FOREIGN KEY (producto_id) REFERENCES productos(id)
                    ON DELETE RESTRICT
            )
        """)


def pedir_entero(mensaje, minimo=None):
    while True:
        try:
            valor = int(input(mensaje))
            if minimo is not None and valor < minimo:
                print(f"El valor debe ser como mínimo {minimo}.")
                continue
            return valor
        except ValueError:
            print("Ingresa un número entero válido.")


def pedir_decimal(mensaje, minimo=0):
    while True:
        try:
            valor = float(input(mensaje).replace(",", "."))
            if valor < minimo:
                print(f"El valor debe ser como mínimo {minimo}.")
                continue
            return valor
        except ValueError:
            print("Ingresa un número válido.")


def registrar_producto():
    nombre = input("Nombre del producto: ").strip()
    if not nombre:
        print("El nombre no puede estar vacío.")
        return
    precio = pedir_decimal("Precio: $")
    cantidad = pedir_entero("Cantidad disponible: ", 0)
    try:
        with conectar() as conn:
            conn.execute(
                "INSERT INTO productos (nombre, precio, cantidad) VALUES (?, ?, ?)",
                (nombre, precio, cantidad)
            )
        print("Producto registrado correctamente.")
    except sqlite3.IntegrityError as error:
        print(f"No se pudo registrar el producto: {error}")


def consultar_productos():
    with conectar() as conn:
        productos = conn.execute(
            "SELECT id, nombre, precio, cantidad FROM productos ORDER BY id"
        ).fetchall()
    if not productos:
        print("No hay productos registrados.")
        return
    print("\n--- INVENTARIO ---")
    print(f"{'ID':<5}{'NOMBRE':<28}{'PRECIO':>12}{'CANTIDAD':>12}")
    print("-" * 57)
    for id_producto, nombre, precio, cantidad in productos:
        print(f"{id_producto:<5}{nombre:<28}${precio:>11.2f}{cantidad:>12}")


def actualizar_producto():
    consultar_productos()
    id_producto = pedir_entero("\nID del producto a actualizar: ", 1)
    print("1. Actualizar precio")
    print("2. Actualizar cantidad")
    opcion = input("Opción: ").strip()

    if opcion == "1":
        valor = pedir_decimal("Nuevo precio: $")
        campo = "precio"
    elif opcion == "2":
        valor = pedir_entero("Nueva cantidad: ", 0)
        campo = "cantidad"
    else:
        print("Opción no válida.")
        return

    with conectar() as conn:
        cursor = conn.execute(
            f"UPDATE productos SET {campo} = ? WHERE id = ?",
            (valor, id_producto)
        )
    print("Producto actualizado." if cursor.rowcount else "No existe un producto con ese ID.")


def eliminar_producto():
    consultar_productos()
    id_producto = pedir_entero("\nID del producto a eliminar: ", 1)
    try:
        with conectar() as conn:
            cursor = conn.execute("DELETE FROM productos WHERE id = ?", (id_producto,))
        if cursor.rowcount:
            print("Producto eliminado.")
        else:
            print("No existe un producto con ese ID.")
    except sqlite3.IntegrityError:
        print("No se puede eliminar: el producto tiene ventas asociadas. Se conserva el historial.")


def registrar_venta(forzar_error=False):
    consultar_productos()
    id_producto = pedir_entero("\nID del producto vendido: ", 1)
    cantidad_vendida = pedir_entero("Cantidad vendida: ", 1)

    conn = conectar()
    try:
        # BEGIN IMMEDIATE inicia la transacción antes de leer y modificar datos.
        conn.execute("BEGIN IMMEDIATE")
        producto = conn.execute(
            "SELECT nombre, precio, cantidad FROM productos WHERE id = ?",
            (id_producto,)
        ).fetchone()

        if producto is None:
            raise ValueError("El producto no existe.")

        nombre, precio, existencia = producto
        if existencia < cantidad_vendida:
            raise ValueError(f"Existencias insuficientes. Disponibles: {existencia}.")

        total = precio * cantidad_vendida
        conn.execute(
            """INSERT INTO ventas
               (producto_id, cantidad, precio_unitario, total, fecha)
               VALUES (?, ?, ?, ?, ?)""",
            (id_producto, cantidad_vendida, precio, total,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

        # Opción de prueba: simula un fallo justo después de insertar la venta.
        if forzar_error:
            raise RuntimeError("Error controlado para demostrar rollback().")

        cursor = conn.execute(
            """UPDATE productos
               SET cantidad = cantidad - ?
               WHERE id = ? AND cantidad >= ?""",
            (cantidad_vendida, id_producto, cantidad_vendida)
        )
        if cursor.rowcount != 1:
            raise RuntimeError("No fue posible actualizar el inventario.")

        conn.commit()
        print(f"Venta registrada: {nombre} x {cantidad_vendida} = ${total:.2f}")
        print("Venta e inventario confirmados con commit().")
    except (ValueError, RuntimeError, sqlite3.Error) as error:
        conn.rollback()
        print(f"Venta cancelada: {error}")
        print("Se ejecutó rollback(); no se guardaron cambios parciales.")
    finally:
        conn.close()


def historial_ventas():
    with conectar() as conn:
        ventas = conn.execute("""
            SELECT v.id, p.nombre, v.cantidad, v.precio_unitario,
                   v.total, v.fecha
            FROM ventas AS v
            INNER JOIN productos AS p ON p.id = v.producto_id
            ORDER BY v.id DESC
        """).fetchall()

    if not ventas:
        print("Todavía no hay ventas registradas.")
        return
    print("\n--- HISTORIAL DE VENTAS ---")
    for id_venta, nombre, cantidad, precio, total, fecha in ventas:
        print(f"Venta #{id_venta} | {fecha} | {nombre} | "
              f"Cantidad: {cantidad} | Unitario: ${precio:.2f} | Total: ${total:.2f}")


def demostrar_rollback():
    """Provoca un error después del INSERT y comprueba que nada cambió."""
    consultar_productos()
    id_producto = pedir_entero("\nID del producto para la prueba: ", 1)

    with conectar() as conn:
        antes_producto = conn.execute(
            "SELECT cantidad FROM productos WHERE id = ?", (id_producto,)
        ).fetchone()
        antes_ventas = conn.execute(
            "SELECT COUNT(*) FROM ventas WHERE producto_id = ?", (id_producto,)
        ).fetchone()[0]

    if antes_producto is None:
        print("Ese producto no existe.")
        return
    if antes_producto[0] < 1:
        print("El producto no tiene existencias para realizar la prueba.")
        return

    print(f"Antes: inventario={antes_producto[0]}, ventas del producto={antes_ventas}")
    # Se pide cantidad 1 y se fuerza una excepción después de insertar la venta.
    registrar_venta_desde_prueba(id_producto)

    with conectar() as conn:
        despues_producto = conn.execute(
            "SELECT cantidad FROM productos WHERE id = ?", (id_producto,)
        ).fetchone()
        despues_ventas = conn.execute(
            "SELECT COUNT(*) FROM ventas WHERE producto_id = ?", (id_producto,)
        ).fetchone()[0]

    print(f"Después: inventario={despues_producto[0]}, ventas del producto={despues_ventas}")
    if antes_producto[0] == despues_producto[0] and antes_ventas == despues_ventas:
        print("PRUEBA EXITOSA: los datos permanecieron intactos tras rollback().")
    else:
        print("PRUEBA FALLIDA: los datos cambiaron inesperadamente.")


def registrar_venta_desde_prueba(id_producto):
    conn = conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        producto = conn.execute(
            "SELECT precio, cantidad FROM productos WHERE id = ?", (id_producto,)
        ).fetchone()
        if producto is None or producto[1] < 1:
            raise ValueError("No hay producto o existencias para probar.")
        precio = producto[0]
        conn.execute(
            """INSERT INTO ventas
               (producto_id, cantidad, precio_unitario, total, fecha)
               VALUES (?, ?, ?, ?, ?)""",
            (id_producto, 1, precio, precio,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        raise RuntimeError("Fallo simulado después del INSERT y antes del UPDATE.")
    except (ValueError, RuntimeError, sqlite3.Error) as error:
        conn.rollback()
        print(f"Error provocado intencionalmente: {error}")
        print("rollback() ejecutado.")
    finally:
        conn.close()


def menu():
    crear_tablas()
    while True:
        print("""
========== SISTEMA DE INVENTARIO Y VENTAS ==========
1. Registrar producto
2. Consultar productos
3. Actualizar precio o cantidad
4. Eliminar producto
5. Registrar venta
6. Historial de ventas
7. Demostrar rollback()
0. Salir
===================================================
""")
        opcion = input("Selecciona una opción: ").strip()
        if opcion == "1":
            registrar_producto()
        elif opcion == "2":
            consultar_productos()
        elif opcion == "3":
            actualizar_producto()
        elif opcion == "4":
            eliminar_producto()
        elif opcion == "5":
            registrar_venta()
        elif opcion == "6":
            historial_ventas()
        elif opcion == "7":
            demostrar_rollback()
        elif opcion == "0":
            print("Programa finalizado.")
            break
        else:
            print("Opción no válida. Intenta nuevamente.")


if __name__ == "__main__":
    menu()
