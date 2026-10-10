-- Queue IDs and other serial columns require sequence privileges.
grant usage, select on all sequences in schema public to carscanner_free_test_runtime;
