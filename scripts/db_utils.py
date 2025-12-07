#!/usr/bin/env python3
"""
Database utility scripts.

Provides command-line tools for database management, migrations,
and maintenance tasks.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from sqlalchemy import text

from src.config import settings
from src.database import (
    DatabaseManager,
    close_db,
    get_db_session,
    health_check,
    init_db,
)
from src.database.tables import Base


@click.group()
def cli():
    """Database utility commands."""
    pass


@cli.command()
def check():
    """Check database connectivity."""
    async def _check():
        await init_db()
        is_healthy = await health_check()
        if is_healthy:
            click.echo(click.style("✓ Database is healthy", fg="green"))
            return 0
        else:
            click.echo(click.style("✗ Database health check failed", fg="red"))
            return 1

    exit_code = asyncio.run(_check())
    sys.exit(exit_code)


@cli.command()
@click.option('--force', is_flag=True, help='Force creation without confirmation')
def create_all(force):
    """Create all database tables."""
    if not force:
        click.confirm(
            'This will create all tables. Continue?',
            abort=True,
        )

    async def _create():
        await init_db()
        engine = DatabaseManager.get_engine()

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        click.echo(click.style("✓ All tables created", fg="green"))
        await close_db()

    asyncio.run(_create())


@cli.command()
@click.option('--force', is_flag=True, help='Force drop without confirmation')
def drop_all(force):
    """Drop all database tables."""
    if not force:
        click.confirm(
            click.style(
                'WARNING: This will drop all tables and data. Are you sure?',
                fg='red',
            ),
            abort=True,
        )

    async def _drop():
        await init_db()
        engine = DatabaseManager.get_engine()

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        click.echo(click.style("✓ All tables dropped", fg="yellow"))
        await close_db()

    asyncio.run(_drop())


@cli.command()
def reset():
    """Reset database (drop and recreate all tables)."""
    click.confirm(
        click.style(
            'WARNING: This will delete all data. Are you sure?',
            fg='red',
        ),
        abort=True,
    )

    async def _reset():
        await init_db()
        engine = DatabaseManager.get_engine()

        click.echo("Dropping tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        click.echo("Creating tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        click.echo(click.style("✓ Database reset complete", fg="green"))
        await close_db()

    asyncio.run(_reset())


@cli.command()
def info():
    """Show database information."""
    async def _info():
        await init_db()

        click.echo(f"Database: {settings.postgres_db}")
        click.echo(f"Host: {settings.postgres_host}:{settings.postgres_port}")
        click.echo(f"User: {settings.postgres_user}")

        # Get table counts
        async with get_db_session() as session:
            tables = [
                'companies',
                'drug_candidates',
                'signals',
                'ma_scores',
                'acquirer_matches',
                'reports',
                'alerts',
                'webhooks',
                'clients',
            ]

            click.echo("\nTable Row Counts:")
            for table in tables:
                try:
                    result = await session.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    )
                    count = result.scalar()
                    click.echo(f"  {table:20s}: {count:,}")
                except Exception as e:
                    click.echo(f"  {table:20s}: N/A ({str(e)[:30]})")

        await close_db()

    asyncio.run(_info())


@cli.command()
@click.argument('query')
def query(query):
    """Execute a SQL query."""
    async def _query():
        await init_db()

        async with get_db_session() as session:
            result = await session.execute(text(query))

            if result.returns_rows:
                rows = result.fetchall()
                if rows:
                    # Print header
                    headers = result.keys()
                    click.echo(" | ".join(headers))
                    click.echo("-" * (sum(len(h) for h in headers) + 3 * len(headers)))

                    # Print rows
                    for row in rows:
                        click.echo(" | ".join(str(v) for v in row))

                    click.echo(f"\n{len(rows)} row(s)")
                else:
                    click.echo("No rows returned")
            else:
                click.echo("Query executed successfully")

        await close_db()

    asyncio.run(_query())


@cli.command()
def vacuum():
    """Run VACUUM ANALYZE on all tables."""
    async def _vacuum():
        await init_db()

        tables = [
            'companies',
            'drug_candidates',
            'signals',
            'ma_scores',
            'acquirer_matches',
            'reports',
            'alerts',
            'webhooks',
            'clients',
        ]

        async with get_db_session() as session:
            for table in tables:
                click.echo(f"Vacuuming {table}...")
                await session.execute(text(f"VACUUM ANALYZE {table}"))

        click.echo(click.style("✓ Vacuum complete", fg="green"))
        await close_db()

    asyncio.run(_vacuum())


@cli.command()
def indexes():
    """Show all indexes."""
    async def _indexes():
        await init_db()

        query = """
        SELECT
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
        """

        async with get_db_session() as session:
            result = await session.execute(text(query))
            rows = result.fetchall()

            current_table = None
            for row in rows:
                if row[0] != current_table:
                    current_table = row[0]
                    click.echo(f"\n{click.style(current_table, fg='cyan', bold=True)}")

                click.echo(f"  {row[1]}")
                if click.get_current_context().params.get('verbose'):
                    click.echo(f"    {row[2]}")

        await close_db()

    asyncio.run(_indexes())


@cli.command()
@click.option('--table', help='Specific table to analyze')
def stats(table):
    """Show table statistics."""
    async def _stats():
        await init_db()

        if table:
            tables = [table]
        else:
            tables = [
                'companies',
                'drug_candidates',
                'signals',
                'ma_scores',
                'acquirer_matches',
                'reports',
                'alerts',
                'webhooks',
                'clients',
            ]

        async with get_db_session() as session:
            for tbl in tables:
                click.echo(f"\n{click.style(tbl, fg='cyan', bold=True)}")

                # Row count
                result = await session.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                count = result.scalar()
                click.echo(f"  Rows: {count:,}")

                # Table size
                result = await session.execute(text(f"""
                    SELECT pg_size_pretty(pg_total_relation_size('{tbl}'))
                """))
                size = result.scalar()
                click.echo(f"  Size: {size}")

                # Index sizes
                result = await session.execute(text(f"""
                    SELECT
                        indexrelname,
                        pg_size_pretty(pg_relation_size(indexrelid))
                    FROM pg_stat_user_indexes
                    WHERE relname = '{tbl}'
                """))
                indexes = result.fetchall()
                if indexes:
                    click.echo("  Indexes:")
                    for idx_name, idx_size in indexes:
                        click.echo(f"    {idx_name}: {idx_size}")

        await close_db()

    asyncio.run(_stats())


@cli.command()
def connections():
    """Show active database connections."""
    async def _connections():
        await init_db()

        query = """
        SELECT
            pid,
            usename,
            application_name,
            client_addr,
            state,
            query_start,
            state_change
        FROM pg_stat_activity
        WHERE datname = current_database()
        ORDER BY query_start DESC
        """

        async with get_db_session() as session:
            result = await session.execute(text(query))
            rows = result.fetchall()

            click.echo(f"Active connections: {len(rows)}\n")

            for row in rows:
                click.echo(f"PID: {row[0]}")
                click.echo(f"  User: {row[1]}")
                click.echo(f"  App: {row[2]}")
                click.echo(f"  Client: {row[3]}")
                click.echo(f"  State: {row[4]}")
                click.echo(f"  Started: {row[5]}")
                click.echo()

        await close_db()

    asyncio.run(_connections())


if __name__ == '__main__':
    cli()
