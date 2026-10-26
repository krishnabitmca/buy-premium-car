"""Real PostgreSQL contention and stale-claim fencing regression tests.

Runs only against the disposable localhost database fixture. No production
credentials, external inventory, or marketplace requests are used.
"""
from datetime import datetime, timezone
import pytest

from psycopg.rows import dict_row
from tests.test_inventory_postgres import db, disposable_database, add_source, psycopg
from src.inventory_refresh_worker import (
    _defer_ingestion_on_lock_contention, claim_jobs,
)

pytestmark = pytest.mark.integration


def _claim(db):
    source_id = add_source(db)
    db.execute("insert into public.inventory_refresh_queue(source_id) values(%s)", (source_id,))
    db.commit()
    jobs = claim_jobs(1)
    assert len(jobs) == 1
    return jobs[0]


def test_real_advisory_contention_defers_claim_without_inventory_writes(db, disposable_database):
    job = _claim(db)
    with psycopg.connect(disposable_database, row_factory=dict_row) as holder:
        assert holder.execute(
            "select pg_try_advisory_xact_lock(731912, 1) as acquired"
        ).fetchone()["acquired"] is True
        with psycopg.connect(disposable_database, row_factory=dict_row) as contender:
            with contender.cursor() as cur:
                assert cur.execute(
                    "select pg_try_advisory_xact_lock(731912, 1) as acquired"
                ).fetchone()["acquired"] is False
                assert _defer_ingestion_on_lock_contention(cur, contender, job) == {"deferred": 1}
        row = db.execute(
            "select status,attempt_count,metadata->>'next_attempt_at' as retry_at "
            "from public.inventory_refresh_queue where refresh_id=%s",
            (job["refresh_id"],),
        ).fetchone()
        assert row["status"] == "queued"
        assert row["attempt_count"] == job["attempt_count"] - 1
        assert row["retry_at"] is not None
        assert db.execute("select count(*) as n from public.vehicle_observations").fetchone()["n"] == 0
        assert db.execute("select count(*) as n from public.listings").fetchone()["n"] == 0
        holder.commit()


def test_real_postgres_stale_claim_cannot_defer_newer_claim(db, disposable_database):
    job = _claim(db)
    # A newer claim has the same job id but a distinct started_at.
    new_start = datetime(2026, 10, 26, tzinfo=timezone.utc)
    db.execute(
        "update public.inventory_refresh_queue set started_at=%s "
        "where refresh_id=%s", (new_start, job["refresh_id"])
    )
    db.commit()
    with psycopg.connect(disposable_database, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            assert _defer_ingestion_on_lock_contention(cur, conn, job) == {"superseded": 1}
    row = db.execute(
        "select status,attempt_count,started_at from public.inventory_refresh_queue "
        "where refresh_id=%s", (job["refresh_id"],)
    ).fetchone()
    assert row["status"] == "running"
    assert row["attempt_count"] == job["attempt_count"]
    assert row["started_at"] == new_start


def test_real_postgres_retry_budget_and_claim_fencing(db, disposable_database):
    job = _claim(db)
    with psycopg.connect(disposable_database, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            assert _defer_ingestion_on_lock_contention(cur, conn, job) == {"deferred": 1}
    db.execute(
        "update public.inventory_refresh_queue set metadata=metadata-'next_attempt_at' "
        "where refresh_id=%s", (job["refresh_id"],)
    )
    db.commit()
    newer = claim_jobs(1)
    assert len(newer) == 1
    assert newer[0]["refresh_id"] == job["refresh_id"]
    assert newer[0]["attempt_count"] == job["attempt_count"]
    with psycopg.connect(disposable_database, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            assert _defer_ingestion_on_lock_contention(cur, conn, job) == {"superseded": 1}
    row = db.execute(
        "select status,attempt_count,started_at from public.inventory_refresh_queue "
        "where refresh_id=%s", (job["refresh_id"],)
    ).fetchone()
    assert row["status"] == "running"
    assert row["started_at"] == newer[0]["started_at"]

def test_discovered_models_share_ingestion_transaction_and_rollback(db):
    from src.used_inventory_frontier import enqueue_models
    source_id = add_source(db)
    db.execute(
        "update public.sources set metadata=jsonb_build_object("
        "'parser_strategy','cardekho_cards',"
        "'query_url_template','https://fixture.invalid/{brand}/{model}') "
        "where source_id=%s", (source_id,),
    )
    db.commit()
    model = [{"model": "X1", "discovery_kind": "observed_model",
              "evidence_url": "https://fixture.invalid/x1"}]
    assert enqueue_models("BMW", model, _connection=db) >= 1
    # The helper must not commit the caller's inventory transaction.
    db.rollback()
    assert db.execute(
        "select count(*) as n from public.inventory_refresh_queue "
        "where source_id=%s and model='x1'", (source_id,),
    ).fetchone()["n"] == 0
    db.rollback()
    assert enqueue_models("BMW", model, _connection=db) >= 1
    db.commit()
    assert db.execute(
        "select count(*) as n from public.inventory_refresh_queue "
        "where source_id=%s and model='x1'", (source_id,),
    ).fetchone()["n"] == 1
