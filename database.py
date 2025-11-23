import os
from typing import List, Tuple, Any

import psycopg2
import psycopg2.extras


# Lê as variáveis de ambiente vindas do Railway
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "railway")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def get_connection():
    """
    Cria uma nova ligação à base de dados PostgreSQL.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        return conn
    except Exception as e:
        # Log simples para debug no Railway
        print(
            "[DB] Erro ao conectar ao Postgres:",
            f"host={DB_HOST} db={DB_NAME} user={DB_USER}",
            f"erro={e}",
        )
        raise


def execute_query(query: str, params: Tuple[Any, ...] | None = None):
    """
    Executa um SELECT ou um INSERT/UPDATE com RETURNING,
    devolvendo sempre uma lista de dicts (coluna -> valor).
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            if cur.description:  # se for SELECT ou RETURNING
                rows = cur.fetchall()
            else:
                rows = []
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
    Executa uma lista de comandos (query, params) numa única transacção.
    Se der erro, faz rollback de tudo.
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
