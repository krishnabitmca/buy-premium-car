# Free testing

Use the existing CarScanner Supabase project with a local Python web server. The
organization currently uses the Free plan with its spend cap enabled. Its project
is in Seoul; this testing setup does not relocate it or create a paid resource.

## Local preview

The ignored `.env` holds the server database URI and Supabase service key. Never
commit this file. No credential is sent to the frontend. The dedicated
`carscanner_free_test_runtime` login can read/write the named CarScanner tables
through policies granted specifically to that backend role. It cannot create
databases or roles and is not a superuser. The existing administrator password
was not changed. Watch API calls use the existing server key.

From the repository root, with Python runtime dependencies installed:

```powershell
python -m scripts.run_local
```

Open http://127.0.0.1:8000. The server stays on localhost; source files, migrations,
Git metadata and `.env` return 404. `/health` is a process health check, not proof
of database readiness. Search uses current database observations and reports
partial coverage honestly. An empty inventory never starts request-time crawling
when fallback is disabled. Live brand/model catalog lookups can still request
the source website.

## Crawler and alerts

To run one small cloud refresh using the local settings:

```powershell
python -c "from scripts.run_local import load_env; load_env(); from src.inventory_service import run_cycle; print(run_cycle(10))"
```

To run hourly batches while this computer remains running:

```powershell
python -c "from scripts.run_local import load_env; load_env(); from src.inventory_service import main; import sys; sys.argv=['inventory_service','--limit','10','--interval-seconds','3600']; main()"
```

Alerts are tested without provider delivery:

```powershell
python -c "from scripts.run_local import load_env; load_env(); from scripts.process_alerts import process_alerts; process_alerts(dry_run=True)"
```

The refresh workflow is configured for minute 17 of each UTC hour, up to ten
executed jobs per run and three requested pages per source. The planner can queue
more work than the worker consumes. Source discovery keeps its existing
three-hour schedule but limits each batch to five candidates. Daily acquisition
uses ten jobs. Both scheduled alert steps explicitly use `--dry-run`.
Free limits do not provide a national coverage or continuous uptime guarantee.

Three separate repository secrets were saved with the user's approval:

- `CARSCANNER_FREE_TEST_DATABASE_URL`
- `CARSCANNER_FREE_TEST_SUPABASE_URL`
- `CARSCANNER_FREE_TEST_SUPABASE_SERVICE_ROLE_KEY`

The workflows prefer these secrets, with the original production secret names
as a compatibility fallback. New secret names are not consumed by older code on
main. GitHub schedules execute workflow code on the default branch: the updated
hourly schedule becomes active after the reviewed changes are merged. A manual
run can test the feature branch before merging. No production merge is implied
by database setup or a passing local preview.

## Database setup and verification

Previously missing watch migrations and vehicle identity migration 015 were
applied to the existing project. Forward migrations enable queue RLS, create the
backend role/policies, grant watch server privileges and grant runtime sequence
usage. The generated login password was provisioned separately and is absent
from SQL migrations. Anonymous/authenticated clients cannot access the queue.
The backend policies do not grant those frontend roles access to customer data.

First verification: cloud SQL connection succeeded, the watch REST endpoint
responded successfully and the alert dry-run reported zero sends. An initial
three-job cloud refresh completed without errors but discovered no vehicle rows.
That proves pipeline execution only; it does not establish marketplace coverage
or absence of available cars. Real source coverage must be expanded and verified
before a PAN India launch.

The test setup is web-accessible locally. A shareable hosted URL, native mobile
app, production alert delivery, storage retention and nationwide load validation
remain separate launch work.
