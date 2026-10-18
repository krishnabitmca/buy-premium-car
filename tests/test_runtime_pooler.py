import pytest
from src.source_registry_db import database_url


@pytest.mark.parametrize('host,port,expected',[
    ('aws-0-region.pooler.supabase.com',5432,6543),
    ('aws-0-region.pooler.supabase.com',6543,6543),
    ('db.project.supabase.co',5432,5432),
    ('localhost',5432,5432),
    ('pooler.supabase.com.attacker.invalid',5432,5432),
])
def test_runtime_transaction_pooling_preserves_credentials_database_and_options(monkeypatch,host,port,expected):
    prefix='postgresql://test.role:p%40ss%3Aword@'+host+':'
    suffix='/postgres?sslmode=require'
    monkeypatch.setenv('SOURCE_INTELLIGENCE_DATABASE_URL',prefix+str(port)+suffix)
    monkeypatch.delenv('CARSCANNER_SUPABASE_POOL_MODE',raising=False)
    assert database_url()==prefix+str(expected)+suffix
    monkeypatch.setenv('CARSCANNER_SUPABASE_POOL_MODE','session')
    assert database_url()==prefix+str(port)+suffix
