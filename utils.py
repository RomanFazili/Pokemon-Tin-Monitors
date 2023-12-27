from constants import MARIA_DB_HOST, MARIA_DB_PASS, MARIA_DB_USER
from pymysqlpool import ConnectionPool
import pymysql.cursors


dictPool = ConnectionPool(
    host = MARIA_DB_HOST,
    user = MARIA_DB_USER,
    password = MARIA_DB_PASS,
    database= "tins",
    cursorclass = pymysql.cursors.DictCursor,
    maxsize=500,
    autocommit=True
)

def getMySQLConnection() -> pymysql.Connection:
    class MySQLConnection:
        def __init__(self, connection):
            self.connection: pymysql.Connection = connection

        def __enter__(self):
            return self.connection

        def __exit__(self, exc_type, exc_value, exc_traceback):
            self.connection.commit()
            self.connection.close()

    connection = dictPool.get_connection()
    return MySQLConnection(connection=connection)