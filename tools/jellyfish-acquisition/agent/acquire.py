"""NUMARA JELLYFISH v0.4: bounded, auditable Space Force media acquisition.

Stage is not scientific validation. Images are admitted as RAW_OBSERVED_UNCALIBRATED
until camera geometry, UTC synchronization, rocket phase and holdout pass.
"""
from __future__ import annotations
import argparse, base64, datetime as dt, hashlib, io, json, os, pathlib, re, subprocess, tempfile, time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from PIL import Image, UnidentifiedImageError

API = 'https://commons.wikimedia.org/w/api.php'
API_HOSTS = {'commons.wikimedia.org'}
MEDIA_HOSTS = {'upload.wikimedia.org', 'd34w7g4gy10iej.cloudfront.net'}
MAX_BYTES = 40 * 1024 * 1024
USER_AGENT = 'NUMARA-Jellyfish-Acquisition/0.4 (scientific research; responsible bounded requests)'
EVENT = 'CRS-35_2026-10-13'

class GateError(Exception): pass

class SafeRedirect(HTTPRedirectHandler):
    def __init__(self, hosts): self.hosts = set(hosts)
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def validate_url(url, allowed):
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname not in allowed or p.username or p.password or p.port not in (None, 443):
        raise GateError('URL_NOT_ALLOWLISTED')

def read_bounded(url, allowed, max_bytes=MAX_BYTES):
    validate_url(url, allowed)
    opener = build_opener(SafeRedirect(allowed))
    req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json,image/jpeg,image/png,image/webp,*/*;q=0.5'})
    with opener.open(req, timeout=40) as resp:
        if resp.status != 200: raise GateError('HTTP_'+str(resp.status))
        if int(resp.headers.get('Content-Length', '0') or 0) > max_bytes: raise GateError('TOO_LARGE')
        buf=bytearray()
        while True:
            chunk=resp.read(min(1048576, max_bytes+1-len(buf)))
            if not chunk: break
            buf.extend(chunk)
            if len(buf)>max_bytes: raise GateError('TOO_LARGE')
    return bytes(buf)

def commons_info(title):
    if not title.startswith('File:') or len(title)>400: raise GateError('INVALID_FILE_TITLE')
    q={'action':'query','format':'json','formatversion':'2','prop':'imageinfo','titles':title,
       'iiprop':'url|size|mime|sha1|timestamp|metadata'}
    blob=read_bounded(API+'?'+urlencode(q),API_HOSTS,2_000_000)
    pages=json.loads(blob).get('query',{}).get('pages',[])
    if len(pages)!=1 or not pages[0].get('imageinfo'): raise GateError('SOURCE_FILE_NOT_FOUND')
    return pages[0]['imageinfo'][0]

def b36(n):
    digits='0123456789abcdefghijklmnopqrstuvwxyz'; out=''
    while n: out=digits[n%36]+out;n//=36
    return out or '0'

def signature_and_image(blob):
    if not blob.startswith(b'\xff\xd8\xff'): raise GateError('NOT_JPEG_SIGNATURE')
    try:
        with Image.open(io.BytesIO(blob)) as im:
            if im.format!='JPEG' or im.width<500 or im.height<500: raise GateError('BAD_IMAGE_GEOMETRY')
            width,height=im.size
            im.verify()
    except (OSError,UnidentifiedImageError) as err: raise GateError('JPEG_DECODE_FAILED') from err
    return width,height

def basic_gate(candidate, info, blob):
    if candidate['mission']!='CRS-35' or candidate['date']!='2026-10-13': raise GateError('WRONG_MISSION_OR_DATE')
    if candidate.get('exposure_s',0) >= 30: raise GateError('LONG_EXPOSURE')
    if not re.fullmatch(r'10009\d{3}', str(candidate['dvids_id'])): raise GateError('ID_MISMATCH')
    src=info.get('url','')
    validate_url(src,MEDIA_HOSTS)
    if str(candidate['dvids_id']) not in str(candidate['commons_title']): raise GateError('TITLE_ID_MISMATCH')
    if info.get('mime') != 'image/jpeg': raise GateError('MIME_MISMATCH')
    if int(info.get('size',-1)) != len(blob): raise GateError('SIZE_MISMATCH')
    digest=hashlib.sha1(blob).digest()
    expected=str(info.get('sha1','')).lower().lstrip('0') or '0'
    if b36(int.from_bytes(digest,'big')) != expected: raise GateError('UPSTREAM_SHA1_MISMATCH')
    dims=signature_and_image(blob)
    if info.get('width') and int(info['width'])!=dims[0]: raise GateError('WIDTH_MISMATCH')
    if info.get('height') and int(info['height'])!=dims[1]: raise GateError('HEIGHT_MISMATCH')
    return dims

def canonical(data): return json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()

def write_local(out, candidate, info, blob, width, height):
    sha=hashlib.sha256(blob).hexdigest()
    raw_name=f'raw/sha256/{sha[:2]}/{sha}.jpg'
    file=out/raw_name
    file.parent.mkdir(parents=True,exist_ok=True)
    if file.exists() and hashlib.sha256(file.read_bytes()).hexdigest()!=sha: raise GateError('LOCAL_HASH_CONFLICT')
    if not file.exists(): file.write_bytes(blob)
    manifest={'schema':'numara-jellyfish-evidence-v0.4','event':EVENT,'candidate_id':candidate['id'],
     'provider':'Wikimedia Commons mirror of DVIDS U.S. Space Force',
     'source_title':candidate['commons_title'],'dvids_id':candidate['dvids_id'],
     'source_page':'https://www.dvidshub.net/image/'+str(candidate['dvids_id']),
     'download_url':info['url'],'upstream_file_sha1_base36':info['sha1'],
     'sha256':sha,'size_bytes':len(blob),'width_px':width,'height_px':height,
     'storage_key':raw_name,'capture_time_reported':candidate.get('reported_time'),
     'time_basis':'CAMERA_EXIF_UNSYNCHRONIZED','location':'NOT_CALIBRATED',
     'provenance':'PUBLIC_SPACE_FORCE_RELEASE','license':'US-GOVERNMENT-PUBLIC-DOMAIN_VERIFY_BY_ITEM',
     'classification':'RAW_OBSERVED_UNCALIBRATED',
     'scientific_validation':'BLOCKED','validation_missing':['utc_camera_calibration','camera_pose',
       'rocket_ephemeris_and_phase','solar_geometry','independent_holdout','error_budget'],
     'acquired_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    m_bytes=canonical(manifest)
    m_key=f'manifests/{EVENT}/{candidate["id"]}-{sha}.json'
    p=out/m_key;p.parent.mkdir(parents=True,exist_ok=True)
    if not p.exists():p.write_bytes(m_bytes)
    return m_key,raw_name,manifest

def github_release_upload(files, tag, repo):
    # GitHub Releases is durable cloud blob storage for *public-domain images only*;
    # release assets are content-addressed and never clobbered.
    if not repo or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo): raise GateError('INVALID_REPO')
    r=subprocess.run(['gh','release','view',tag,'-R',repo,'--json','assets'],capture_output=True,text=True)
    if r.returncode:
        x=subprocess.run(['gh','release','create',tag,'-R',repo,'--title',tag,'--notes',
                          'Original publicly released Space Force media; uncalibrated observations. Provenance manifests attached.'],capture_output=True,text=True)
        if x.returncode: raise GateError('CLOUD_RELEASE_CREATE_FAILED: '+x.stderr[:100])
        existing=set()
    else: existing={a['name'] for a in json.loads(r.stdout).get('assets',[])}
    for path, name in files:
        if name in existing: continue
        x=subprocess.run(['gh','release','upload',tag,'-R',repo,str(path)+'#'+name],capture_output=True,text=True)
        if x.returncode: raise GateError('CLOUD_UPLOAD_FAILED: '+x.stderr[:150])

def gcs_upload(files, bucket):
    if not bucket or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,220}',bucket): raise GateError('INVALID_BUCKET')
    from google.cloud import storage
    b=storage.Client().bucket(bucket)
    for path,name in files:
        blob=b.blob('numara-jellyfish/'+name)
        try: blob.upload_from_filename(str(path),if_generation_match=0)
        except Exception as ex:
            if ex.__class__.__name__!='PreconditionFailed': raise
            # Repeated content-hash names are idempotent; compare remote vs local SHA256.
            blob.reload()
            if blob.size != path.stat().st_size: raise GateError('GCS_COLLISION')
            if hashlib.sha256(blob.download_as_bytes()).digest()!=hashlib.sha256(path.read_bytes()).digest():
                raise GateError('GCS_COLLISION')

def store(out, manifest_key, raw_key, mode, repo, bucket):
    if mode=='local':return
    if mode=='github-release':
        sha=pathlib.Path(raw_key).stem
        files=[(out/raw_key,f'{sha}.jpg'),(out/manifest_key,pathlib.Path(manifest_key).name)]
        github_release_upload(files,EVENT,repo)
    elif mode=='gcs':gcs_upload([(out/raw_key,raw_key),(out/manifest_key,manifest_key)],bucket)
    else:raise GateError('BAD_STORAGE_MODE')

def run(config,out,mode='local',repo=None,bucket=None,fetcher=read_bounded,infogetter=commons_info):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    results=[]
    for c in config['candidates']:
        result={'id':c['id'],'event':EVENT,'ingest_attempt_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            if c['mission']!='CRS-35' or c['date']!='2026-10-13' or c.get('exposure_s',0)>=30:
                raise GateError('PRECHECK_REJECT')
            info=infogetter(c['commons_title'])
            validate_url(info['url'],MEDIA_HOSTS)
            blob=fetcher(info['url'],MEDIA_HOSTS)
            w,h=basic_gate(c,info,blob)
            mk,rk,m=write_local(out,c,info,blob,w,h)
            store(out,mk,rk,mode,repo,bucket)
            result.update(status='RAW_CLOUD_ARCHIVED_UNCALIBRATED' if mode!='local' else 'RAW_LOCAL_UNCALIBRATED',
                          sha256=m['sha256'], storage_backend=mode, manifest_key=mk)
        except Exception as err:
            result.update(status='QUARANTINED_NOT_INGESTED',reason=f'{type(err).__name__}:{str(err)[:220]}')
        results.append(result)
        # Per-source journal is independent of blob cloud upload and stores no fake measurements.
        with (out/'acquisition_journal.jsonl').open('a') as f:f.write(json.dumps(result,sort_keys=True)+'\n')
    return results

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default='config/crs35.json');p.add_argument('--out',default='runtime');p.add_argument('--storage',choices=['local','github-release','gcs'],default=os.getenv('JELLYFISH_STORAGE','local'));p.add_argument('--repo',default=os.getenv('GITHUB_REPOSITORY'));p.add_argument('--bucket',default=os.getenv('GCS_BUCKET'));a=p.parse_args()
    r=run(json.loads(pathlib.Path(a.config).read_text()),a.out,a.storage,a.repo,a.bucket)
    print(json.dumps(r,indent=2))
    if any(x['status'].startswith('QUARANTINED') for x in r):raise SystemExit(2)
if __name__=='__main__':main()
