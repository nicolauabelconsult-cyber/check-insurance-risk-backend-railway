import os
from typing import List, Tuple, Any

import psycopg2
import psycopg2.extras

# 👉 Lê a variável DATABASE_URL (se existir)
DB_URL = os.getenv("DATABASE_URL")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "railway")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def get_connection():
    try:
        if DB_URL:
            print("[DB] A usar DATABASE_URL para conexão.")
            conn = psycopg2.connect(DB_URL)
        else:
            print(
                f"[DB] A usar variáveis individuais: "
                f"host={DB_HOST} db={DB_NAME} user={DB_USER}"
            )
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
            )
        return conn
    except Exception as e:
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
            if cur.description:  # SELECT ou RETURNING
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


# ---------------------------------------------
# Criação automática das tabelas necessárias
# ---------------------------------------------

def init_db_schema():
    """
    Cria as tabelas necessárias caso ainda não existam.
    Isto evita o erro 'relation "users" does not exist'.
    """
    ddl_statements = [
        # Tabela de utilizadores
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username      VARCHAR(100) UNIQUE NOT NULL,
            email         VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT         NOT NULL,
            role          VARCHAR(20)  NOT NULL DEFAULT 'analyst',
            is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
            last_login    TIMESTAMP    NULL,
            created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
        );
        """,

        # Registos de risco
        """
        CREATE TABLE IF NOT EXISTS risk_records (
            id SERIAL PRIMARY KEY,
            full_name     TEXT,
            nif           TEXT,
            passport      TEXT,
            resident_card TEXT,
            notes         TEXT,
            risk_score    NUMERIC,
            risk_level    VARCHAR(20),
            matches       JSONB,
            risk_factors  JSONB,
            analyzed_by   INTEGER REFERENCES users(id),
            analyzed_at   TIMESTAMP,
            decision      VARCHAR(30),
            analyst_notes TEXT
        );
        """,

        # Fontes de informação
        """
        CREATE TABLE IF NOT EXISTS info_sources (
            id SERIAL PRIMARY KEY,
            name        TEXT         NOT NULL,
            source_type VARCHAR(50)  NOT NULL,
            file_type   VARCHAR(20)  NOT NULL,
            num_records INTEGER      NOT NULL,
            uploaded_at TIMESTAMP    NOT NULL,
            uploaded_by INTEGER      REFERENCES users(id),
            is_active   BOOLEAN      NOT NULL DEFAULT TRUE
        );
        """,

        # Entidades normalizadas para pesquisa
        """
        CREATE TABLE IF NOT EXISTS normalized_entities (
            id SERIAL PRIMARY KEY,
            full_name      TEXT,
            nif            TEXT,
            passport       TEXT,
            resident_card  TEXT,
            position       TEXT,
            country        TEXT,
            additional_info JSONB,
            source_id      INTEGER REFERENCES info_sources(id)
        );
        """,

        # Índices úteis
        "CREATE INDEX IF NOT EXISTS idx_normalized_entities_name ON normalized_entities (LOWER(full_name));",
        "CREATE INDEX IF NOT EXISTS idx_normalized_entities_nif  ON normalized_entities (nif);",
        "CREATE INDEX IF NOT EXISTS idx_risk_records_nif         ON risk_records (nif);",
        "CREATE INDEX IF NOT EXISTS idx_risk_records_name        ON risk_records (LOWER(full_name));",
    ]

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            for ddl in ddl_statements:
                cur.execute(ddl)
        conn.commit()
        print("[DB] Esquema verificado/criado com sucesso.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB] Erro ao inicializar o esquema da BD: {e}")
        raise
    finally:
        if conn:
            conn.close()
