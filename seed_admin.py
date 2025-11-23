# seed_admin.py
"""
Cria automaticamente o utilizador principal caso ele não exista.
Utilizador principal: nicolauabel.consult@gmail.com / Qwerty080397
"""

from database import execute_query
from auth import get_password_hash


def seed_default_user():
    email = "nicolauabel.consult@gmail.com"
    username = "nicolauabel"
    plain_password = "Qwerty080397"

    # Gerar hash seguro
    hashed_password = get_password_hash(plain_password)

    # Verificar se já existe
    rows = execute_query(
        "SELECT id FROM users WHERE email = %s OR username = %s",
        (email, username),
    )

    if rows:
        print("[SEED] Utilizador principal já existe.")
        return

    # Criar novo utilizador principal
    execute_query(
        """
        INSERT INTO users (username, email, password_hash, role, is_active, created_at)
        VALUES (%s, %s, %s, 'ADMIN', true, NOW())
        """,
        (username, email, hashed_password),
    )

    print("[SEED] Utilizador principal criado com sucesso!")
