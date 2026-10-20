"""Operator-only local sample capture/replay. Never fetch or ingest inventory."""
import argparse
import json
from pathlib import Path

from src.parser_replay import (
    capture_sample, replay_sample, MAX_INPUT_BYTES, MAX_ARTIFACT_BYTES,
)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    capture=commands.add_parser('capture')
    capture.add_argument('--input',required=True)
    capture.add_argument('--output',required=True)
    capture.add_argument('--source-url',required=True)
    capture.add_argument('--generation')
    replay=commands.add_parser('replay')
    replay.add_argument('--input',required=True)
    args=parser.parse_args(argv)
    limit=MAX_INPUT_BYTES if args.command=='capture' else MAX_ARTIFACT_BYTES
    try:
        with Path(args.input).open('rb') as handle:
            data=handle.read(limit+1)
        if args.command=='capture':
            # Keep the oversize sentinel; never turn truncated input into a sample.
            artifact=capture_sample(data,source_url=args.source_url,scan_generation=args.generation)
            payload=json.dumps(artifact,ensure_ascii=False,allow_nan=False)
            with Path(args.output).open('x',encoding='utf-8') as handle:
                handle.write(payload)
            report={'status':artifact.get('status'),'historical_sample':True,
                    'inventory_ingested':False}
            success=artifact.get('status')=='captured_sample'
        else:
            if len(data)>limit:
                raise ValueError('Oversized artifact')
            report=replay_sample(json.loads(data.decode('utf-8')))
            success=report.get('status')=='matched'
    except FileExistsError:
        report={'status':'output_exists','historical_sample':True,'inventory_ingested':False}
        success=False
    except (OSError,ValueError,TypeError,RecursionError):
        report={'status':'replay_unavailable','historical_sample':True,'inventory_ingested':False}
        success=False
    print(json.dumps(report,ensure_ascii=False,allow_nan=False))
    return 0 if success else 2


if __name__=='__main__':
    raise SystemExit(main())
