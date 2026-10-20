from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest

from src import parser_capture as capture

HTML=Path('tests/fixtures/reviewed_fusion.html').read_bytes()
URL='https://fusioncars.in/collections/'


@pytest.fixture
def buffer(monkeypatch):
    monkeypatch.setenv('CARSCANNER_PARSER_CAPTURE_ENABLED','true')
    return capture.CaptureBuffer('Fusion Cars',uuid4())


def receipt(buffer,generation):
    now=datetime.now(timezone.utc)
    return dict(batch_id=str(uuid4()),generation_id=str(generation),source_id=buffer.source_id,
        refresh_id=1,attempt_count=1,claim_started_at=(now-timedelta(minutes=1)).isoformat(),
        batch_completed_at=now.isoformat(),accepted_observations=3,membership_count=3,inventory_commit='verified')


def test_gate_is_required_and_rechecked_after_construction(monkeypatch):
    monkeypatch.delenv('CARSCANNER_PARSER_CAPTURE_ENABLED',raising=False)
    with pytest.raises(ValueError):capture.CaptureBuffer('Fusion Cars',uuid4())
    monkeypatch.setenv('CARSCANNER_PARSER_CAPTURE_ENABLED','true')
    buffer=capture.CaptureBuffer('Fusion Cars',uuid4())
    monkeypatch.setenv('CARSCANNER_PARSER_CAPTURE_ENABLED','false')
    assert buffer.capture(HTML,source_url=URL,scan_generation=uuid4())['status']=='disabled'


def test_two_attempt_budget_and_export_receipt_hashes(buffer,tmp_path):
    generation=uuid4()
    for _ in range(2):assert buffer.capture(HTML,source_url=URL,scan_generation=generation)['status']=='captured_sample'
    assert buffer.capture(HTML,source_url=URL,scan_generation=generation)['status']=='attempt_budget_exhausted'
    directory=tmp_path/'samples'
    result=buffer.export(directory,receipt(buffer,generation))
    assert result['status']=='exported' and result['sample_count']==2
    manifest=json.loads((directory/'receipt.json').read_bytes())
    assert len(list(directory.iterdir()))==3
    assert result['bytes']<=capture.MAX_DIRECTORY_BYTES
    assert manifest['capture_attempts']==2 and not manifest['completeness_verified']
    assert not manifest['absence_reconciliation_permitted']
    for item in manifest['samples']:
        payload=(directory/item['file']).read_bytes()
        assert sha256(payload).hexdigest()==item['sha256'] and len(payload)==item['bytes']
    assert buffer.export(directory,receipt(buffer,generation))['status']=='export_failed'


def test_failed_capture_is_nonthrowing_does_not_keep_raw_html(buffer,monkeypatch,tmp_path):
    def fail(*args,**kwargs):raise ValueError('token=private raw html')
    monkeypatch.setattr(capture,'capture_sample',fail)
    generation=uuid4()
    assert buffer.capture('private raw html',source_url=URL,scan_generation=generation)['status']=='capture_failed'
    result=buffer.export(tmp_path/'missing',receipt(buffer,generation))
    assert result['status']=='missing' and result['sample_count']==0
    assert 'private' not in (tmp_path/'missing'/'receipt.json').read_text()
    assert not buffer._samples


def test_partial_capture_is_explicit(buffer,tmp_path):
    generation=uuid4()
    buffer.capture(HTML,source_url=URL,scan_generation=generation)
    buffer.capture(b'no supported cards',source_url=URL,scan_generation=generation)
    result=buffer.export(tmp_path/'partial',receipt(buffer,generation))
    assert result['status']=='partial' and result['sample_count']==1


@pytest.mark.parametrize('field,value',[
    ('inventory_commit','unverified'),('source_id',str(uuid4())),('generation_id',str(uuid4())),
    ('batch_id','invalid'),('attempt_count',True),('membership_count',1),('captured_raw','private'),
    ('claim_started_at','2026-10-20'),('batch_completed_at','')])
def test_invalid_receipt_never_writes(buffer,tmp_path,field,value):
    generation=uuid4()
    buffer.capture(HTML,source_url=URL,scan_generation=generation)
    invalid=receipt(buffer,generation);invalid[field]=value
    result=buffer.export(tmp_path/'invalid',invalid)
    assert result['status']=='export_failed' and result['reason']=='invalid_receipt'
    assert not (tmp_path/'invalid').exists() and 'private' not in json.dumps(result)


def test_source_generation_cannot_change_between_samples(buffer,tmp_path):
    generation=uuid4()
    buffer.capture(HTML,source_url=URL,scan_generation=generation)
    result=buffer.capture(HTML,source_url=URL,scan_generation=uuid4())
    assert result['status']=='generation_mismatch' and result['sample_count']==1


def test_artifact_tampering_and_oversize_block_export(buffer,tmp_path):
    generation=uuid4();buffer.capture(HTML,source_url=URL,scan_generation=generation)
    buffer._samples[0]=buffer._samples[0].replace(b'fusion_cards-v1',b'fusion_cards-v9')
    result=buffer.export(tmp_path/'tampered',receipt(buffer,generation))
    assert result['status']=='export_failed' and not (tmp_path/'tampered').exists()
    buffer._samples[0]=b'x'*(capture.MAX_ARTIFACT_BYTES+1)
    assert buffer.export(tmp_path/'large',receipt(buffer,generation))['status']=='export_failed'


def test_export_io_error_keeps_verified_inventory_and_no_error_echo(buffer,tmp_path,monkeypatch):
    generation=uuid4();buffer.capture(HTML,source_url=URL,scan_generation=generation)
    def fail(*args,**kwargs):raise PermissionError('secret user path')
    monkeypatch.setattr(Path,'mkdir',fail)
    result=buffer.export(tmp_path/'failed',receipt(buffer,generation))
    assert result['status']=='export_failed' and result['inventory_commit']=='verified'
    assert 'secret' not in json.dumps(result)


def test_symlink_destination_is_rejected(buffer,tmp_path):
    target=tmp_path/'real';target.mkdir()
    link=tmp_path/'link'
    try:link.symlink_to(target,target_is_directory=True)
    except OSError:pytest.skip('Symlink privilege unavailable')
    result=buffer.export(link/'samples',receipt(buffer,uuid4()))
    assert result['status']=='export_failed' and not (target/'samples').exists()
