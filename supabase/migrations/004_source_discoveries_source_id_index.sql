-- Cover the source_id foreign key for source discovery lookups and cascades.
create index if not exists idx_source_discoveries_source_id on public.source_discoveries(source_id);
