# database.py
import os
from typing import Any, List, Tuple

import psycopg2
import psycopg2.extras

# Lê o DSN completo do Railway (postgres://user:pass@host:port/dbname)
DATABASE_URL = os.getenv("DATABASE_URL")


if not DATABASE_URL:
    # Falha logo ao arrancar se a variável não existir
    raise RuntimeError(
        "DATABASE_URL não está definido. "
        "No Railway, cria a variável DATABASE_URL = ${{ Postgres.DATABASE_URL }}."
    )


def get_connection():
    """
    Cria uma nova ligação à base de dados PostgreSQL usando o DSN completo.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"[DB] Erro ao conectar ao Postgres: {e}")
        print(f"[DB] DATABASE_URL (oculto) está definido? "
              f"{'SIM' if DATABASE_URL else 'NÃO'}")
        raise


def execute_query(query: str, params: Tuple[Any, ...] | None = None):
    """
    Executa SELECT ou INSERT/UPDATE com RETURNING.
    Devolve sempre uma lista de dicts (coluna -> valor).
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            rows = cur.fetchall() if cur.description else []
        conn.commit()
        return rows
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB] Erro em execute_query: {e} | SQL={query} | params={params}")
        raise
    finally:
        if conn:
            conn.close()


def execute_transaction(queries: List[Tuple[str, Tuple[Any, ...]]]):
    """
    Executa vários comandos numa única transacção.
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            for sql, params in queries:
                cur.execute(sql, params or ())
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB] Erro em execute_transaction: {e}")
        raise
    finally:
        if conn:
            conn.close()
