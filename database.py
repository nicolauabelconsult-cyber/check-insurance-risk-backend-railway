import os
import psycopg2
import psycopg2.extras


# Railway fornece APENAS esta variável
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não está definida!")


def get_connection():
    """
    Cria ligação ao PostgreSQL usando a DATABASE_URL do Railway.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    except Exception as e:
        print("[DB] Erro ao conectar ao Postgres:", e)
        raise


def execute_query(query, params=None):
    """
    Executa SELECT ou INSERT/UPDATE com RETURNING.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        rows = cur.fetchall() if cur.description else []
        conn.commit()
        cur.close()
        return rows
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB] Erro em execute_query: {e} | SQL={query} | params={params}")
        raise
    finally:
        if conn:
            conn.close()


def execute_transaction(queries):
    """
    Executa várias queries numa transacção.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        for sql, params in queries:
            cur.execute(sql, params or ())
        conn.commit()
        cur.close()
    except Exception as e:
        if conn:
            conn.rollback()
        print("[DB] Erro em execute_transaction:", e)
        raise
    finally:
        if conn:
            conn.close()
