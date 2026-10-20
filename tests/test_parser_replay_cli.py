"""Local operator file bounds and non-overwrite behavior."""
import json
from pathlib import Path

import pytest

from scripts.parser_replay import main

BASE='https://fusioncars.in/brand/mercedes-benz/'
FIXTURE=Path('tests/fixtures/reviewed_fusion.html')


def test_operator_capture_and_offline_replay(tmp_path,capsys):
    output=tmp_path/'sample.json'
    assert main(['capture','--input',str(FIXTURE),'--output',str(output),'--source-url',BASE])==0
    report=json.loads(capsys.readouterr().out)
    assert report['status']=='captured_sample' and not report['inventory_ingested']
    assert main(['replay','--input',str(output)])==0
    assert json.loads(capsys.readouterr().out)['status']=='matched'
    before=output.read_bytes()
    assert main(['capture','--input',str(FIXTURE),'--output',str(output),'--source-url',BASE])==2
    assert json.loads(capsys.readouterr().out)['status']=='output_exists'
    assert output.read_bytes()==before


def test_malformed_artifact_has_no_raw_error_or_input_text(tmp_path,capsys):
    path=tmp_path/'bad.json'
    path.write_text('private-token-not-json',encoding='utf-8')
    assert main(['replay','--input',str(path)])==2
    assert 'private-token' not in capsys.readouterr().out


def test_oversized_artifact_is_rejected_before_json(tmp_path,capsys):
    from src.parser_replay import MAX_ARTIFACT_BYTES
    path=tmp_path/'oversize.json'
    path.write_bytes(b' '*(MAX_ARTIFACT_BYTES+1))
    assert main(['replay','--input',str(path)])==2
    assert json.loads(capsys.readouterr().out)['status']=='replay_unavailable'


@pytest.mark.parametrize('command', ['capture', 'replay'])
@pytest.mark.parametrize('error', [RuntimeError, IndexError])
def test_unexpected_operator_errors_never_emit_raw_payload(command,error,tmp_path,capsys,monkeypatch):
    from scripts import parser_replay
    source=tmp_path/'input.txt'
    source.write_text('{}',encoding='utf-8')
    def fail(*args,**kwargs):
        raise error('token=private-parser-error')
    monkeypatch.setattr(parser_replay,command+'_sample',fail)
    args=[command,'--input',str(source)]
    if command=='capture':args+=['--output',str(tmp_path/'out.json'),'--source-url',BASE]
    assert main(args)==2
    output=capsys.readouterr()
    assert json.loads(output.out)['status']=='replay_unavailable'
    assert 'private-parser-error' not in output.out+output.err
