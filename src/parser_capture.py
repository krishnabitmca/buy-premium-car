"""Explicit controlled-job sanitized sample buffer and post-commit exporter.

No database, network, ingestion or raw-response storage. A verified receipt is
attested by the caller after its exact-claim database check, not by this module.
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import UUID

from .parser_replay import capture_sample, replay_sample, MAX_ARTIFACT_BYTES

MAX_ATTEMPTS=2
MAX_BUFFER_BYTES=128*1024
MAX_RECEIPT_BYTES=8*1024
MAX_DIRECTORY_BYTES=136*1024
_RECEIPT_FIELDS={'batch_id','generation_id','source_id','refresh_id','attempt_count',
    'claim_started_at','batch_completed_at','accepted_observations','membership_count','inventory_commit'}


def _enabled():
    return os.getenv('CARSCANNER_PARSER_CAPTURE_ENABLED','false').lower()=='true'


def _bytes(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def _uuid(value):
    return str(UUID(str(value)))


def _stamp(value):
    if not isinstance(value,(str,datetime)):
        raise ValueError('Invalid receipt timestamp')
    stamp=datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('Invalid receipt timestamp')
    return stamp.astimezone(timezone.utc)


class CaptureBuffer:
    def __init__(self,source_name,source_id):
        if not _enabled():raise ValueError('Parser capture is disabled')
        if source_name not in ('Fusion Cars','Fusion','Fusion Cars India'):
            raise ValueError('Unsupported capture source')
        self.source_name=source_name
        self.source_id=_uuid(source_id)
        self._generation=None
        self._attempts=0
        self._outcomes=Counter()
        self._samples=[]
        self._size=0

    def capture(self,html,*,source_url,scan_generation):
        """Attempt bounded sanitization; source/parser errors never escape."""
        if not _enabled():return {'status':'disabled'}
        if self._attempts>=MAX_ATTEMPTS:return {'status':'attempt_budget_exhausted'}
        self._attempts+=1
        status='capture_failed'
        try:
            generation=_uuid(scan_generation)
            if self._generation is not None and generation!=self._generation:
                status='generation_mismatch'
            else:
                self._generation=generation
                artifact=capture_sample(html,source_name=self.source_name,source_url=source_url,
                                        scan_generation=generation)
                status=artifact.get('status','capture_failed')
                allowed={'captured_sample','unsupported_strategy','input_oversized','sample_oversized','no_supported_cards'}
                if status not in allowed:status='capture_failed'
                if status=='captured_sample':
                    payload=_bytes(artifact)
                    if len(payload)>MAX_ARTIFACT_BYTES or self._size+len(payload)>MAX_BUFFER_BYTES:
                        status='sample_oversized'
                    elif replay_sample(artifact).get('status')!='matched':
                        status='replay_unavailable'
                    else:
                        self._samples.append(payload)
                        self._size+=len(payload)
                        self._generation=generation
        except Exception:
            status='capture_failed'
        self._outcomes[status]+=1
        return {'status':status,'sample_count':len(self._samples),'capture_attempts':self._attempts}

    def _receipt(self,receipt):
        if not isinstance(receipt,dict) or set(receipt)!=_RECEIPT_FIELDS or receipt['inventory_commit']!='verified':
            raise ValueError('Invalid receipt')
        result={key:_uuid(receipt[key]) for key in ('batch_id','generation_id','source_id')}
        if result['source_id']!=self.source_id or (self._generation is not None and result['generation_id']!=self._generation):
            raise ValueError('Receipt source/generation mismatch')
        for key in ('refresh_id','attempt_count','accepted_observations','membership_count'):
            value=receipt[key]
            if type(value) is not int or value<(1 if key in ('refresh_id','attempt_count') else 0):
                raise ValueError('Invalid receipt count')
            result[key]=value
        if result['accepted_observations']!=result['membership_count']:
            raise ValueError('Receipt membership mismatch')
        claim,completed=(_stamp(receipt[key]) for key in ('claim_started_at','batch_completed_at'))
        if completed<claim:raise ValueError('Receipt timestamp order')
        result.update(inventory_commit='verified',claim_started_at=claim.isoformat(),batch_completed_at=completed.isoformat())
        return result

    def export(self,directory,receipt):
        """Export after commit; failures cannot affect canonical job state.

        Destination must be a new child directory of an existing real parent.
        Interrupted/failed writes may leave an incomplete diagnostic directory;
        never automatically overwrite, delete, retry acquisition or claim upload.
        """
        failure={'status':'export_failed','sample_count':0,'historical_sample':True,
                 'inventory_commit':'unverified','remote_upload_verified':False}
        if not _enabled():return {**failure,'reason':'disabled'}
        try:
            manifest=self._receipt(receipt)
        except Exception:
            return {**failure,'reason':'invalid_receipt'}
        failure['inventory_commit']='verified'
        try:
            sample_files=[]
            for index,payload in enumerate(self._samples,1):
                if len(payload)>MAX_ARTIFACT_BYTES:raise ValueError('Artifact oversized')
                artifact=json.loads(payload)
                if (artifact.get('source_name')!=self.source_name
                        or artifact.get('scan_generation')!=manifest['generation_id']
                        or replay_sample(artifact).get('status')!='matched'):
                    raise ValueError('Artifact validation failed')
                sample_files.append({'file':f'sample-{index:02d}.json','bytes':len(payload),
                    'sha256':sha256(payload).hexdigest(),'parser_version':artifact['parser_version'],
                    'sanitizer_version':artifact['sanitizer_version']})
            status=('missing' if not sample_files else 'exported' if len(sample_files)==self._attempts else 'partial')
            manifest.update(receipt_version=1,capture_status=status,capture_attempts=self._attempts,
                capture_outcomes=dict(self._outcomes),samples=sample_files,historical_sample=True,
                sampled_only=True,completeness_verified=False,absence_reconciliation_permitted=False)
            receipt_payload=_bytes(manifest)
            if (len(receipt_payload)>MAX_RECEIPT_BYTES or len(self._samples)>MAX_ATTEMPTS
                    or sum(map(len,self._samples))>MAX_BUFFER_BYTES
                    or sum(map(len,self._samples))+len(receipt_payload)>MAX_DIRECTORY_BYTES):
                raise ValueError('Export budget exceeded')
            target=Path(directory).absolute()
            if target.exists() or target.is_symlink() or not target.parent.is_dir():
                raise ValueError('Destination unavailable')
            if any(path.is_symlink() or getattr(path,'is_junction',lambda:False)()
                   for path in (target.parent,*target.parents)):
                raise ValueError('Symlink destination forbidden')
            parent=target.parent.resolve(strict=True)
            if target.resolve(strict=False).parent!=parent:
                raise ValueError('Destination escaped parent')
            target.mkdir(mode=0o700)
            for item,payload in zip(sample_files,self._samples):
                with (target/item['file']).open('xb') as handle:
                    if handle.write(payload)!=len(payload):raise OSError('Incomplete sample write')
            # The manifest is last; absent/invalid manifest means incomplete export.
            with (target/'receipt.json').open('xb') as handle:
                if handle.write(receipt_payload)!=len(receipt_payload):raise OSError('Incomplete receipt write')
            return {'status':status,'sample_count':len(sample_files),'capture_attempts':self._attempts,
                'historical_sample':True,'inventory_commit':'verified','remote_upload_verified':False,
                'bytes':sum(map(len,self._samples))+len(receipt_payload)}
        except Exception:
            return {**failure,'reason':'export_unavailable'}
