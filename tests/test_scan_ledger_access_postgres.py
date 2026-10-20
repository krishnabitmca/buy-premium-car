"""Actual limited worker-role ledger access; browser roles stay denied."""
import pytest
from tests.test_inventory_postgres import db, disposable_database, psycopg
from tests.test_scan_ledger_postgres import setup_claim, finish_with_observations

pytestmark = pytest.mark.integration


def test_existing_runtime_role_can_write_ledger_but_cannot_delete(db):
    source_id, job, evidence = setup_claim(db)
    with db.transaction():
        db.execute('set local role carscanner_free_test_runtime')
        batch, accepted = finish_with_observations(db, source_id, job, evidence)
        assert accepted
        assert db.execute('select accepted_count from inventory_scan_batches where batch_id=%s',
                          (batch['batch_id'],)).fetchone()['accepted_count'] == 1
        for table in ('inventory_scan_generations','inventory_scan_batches','inventory_scan_memberships'):
            assert not db.execute("select has_table_privilege(current_user,%s,'DELETE') as allowed",
                                  ('public.'+table,)).fetchone()['allowed']
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with db.transaction():
                    db.execute('delete from '+table)


@pytest.mark.parametrize('role',['anon','authenticated'])
def test_runtime_policies_do_not_authorize_browser_roles(db,role):
    source_id, job, evidence = setup_claim(db)
    finish_with_observations(db,source_id,job,evidence)
    for table in ('inventory_scan_generations','inventory_scan_batches','inventory_scan_memberships'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():
                db.execute('set local role '+role)
                db.execute('select * from '+table)
