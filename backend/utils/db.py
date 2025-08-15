import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def conectar_db():
    try:
        db_host = os.getenv("DB_HOST")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")

        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except pymysql.Error as err:
        print(f"Error al conectar a la base de datos: {err}")
        raise Exception(f"No se pudo conectar a la base de datos: {err}")
    except Exception as e:
        print(f"Error inesperado en conectar_db: {e}")
        raise Exception(f"Error inesperado al conectar a la base de datos: {e}")

if __name__ == '__main__':
    try:
        print("Intentando conectar a la base de datos...")
        connection = conectar_db()
        if connection:
            print("¡Conexión exitosa a la base de datos!")
            connection.close()
            print("Conexión cerrada.")
    except Exception as e:
        print(f"Fallo la conexión: {e}")