"""
Kulinda tables za Django zilizoko kwenye Supabase.

Supabase inaweka schema `public` wazi kupitia Data API (REST). Django
inaunganishwa kama mmiliki wa tables, kwa hiyo haihitaji Data API kabisa.
Baada ya kila `migrate`, tunawasha RLS kwenye kila table ya `public` bila
policy yoyote, na kunyang'anya ruhusa za `anon` na `authenticated`. Hivyo
hakuna anayeweza kusoma malipo, vocha au RADIUS secrets kwa kutumia anon key.
Django yenyewe haiathiriki kwa sababu mmiliki wa table hapitii RLS.
"""

from django.db import connections

API_ROLES = ("anon", "authenticated")


def lock_down_public_tables(using="default", **kwargs):
    connection = connections[using]
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity"
        )
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(
                f"ALTER TABLE public.{connection.ops.quote_name(table)} ENABLE ROW LEVEL SECURITY"
            )

        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", [list(API_ROLES)])
        roles = [row[0] for row in cursor.fetchall()]
        if roles:
            role_list = ", ".join(connection.ops.quote_name(role) for role in roles)
            cursor.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role_list}")
            cursor.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role_list}")
