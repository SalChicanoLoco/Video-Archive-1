import hashlib, io, json, pathlib, tempfile, unittest, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from PIL import Image
from agent.acquire import validate_url,signature_and_image,basic_gate,run,GateError,write_local,MAX_BYTES,b36

def fake_jpg():
    x=io.BytesIO();Image.new('RGB',(520,530),(127,127,127)).save(x,'JPEG');return x.getvalue()

class Tests(unittest.TestCase):
  def setUp(self):
    self.c={'id':'TEST','mission':'CRS-35','date':'2026-10-13','dvids_id':'10009474','commons_title':'File:CRS-35 Launches from Cape Canaveral Space Force Station (10009474).jpg','exposure_s':1/800}
    self.b=fake_jpg();self.info={'url':'https://upload.wikimedia.org/x.jpg','size':len(self.b),'mime':'image/jpeg','sha1':b36(int.from_bytes(hashlib.sha1(self.b).digest(),'big')),'width':520,'height':530}
  def test_https_host(self):
    validate_url(self.info['url'],{'upload.wikimedia.org'})
  def test_bad_scheme(self):
    with self.assertRaises(GateError):validate_url('http://upload.wikimedia.org/x.jpg',{'upload.wikimedia.org'})
  def test_bad_redirect_host(self):
    with self.assertRaises(GateError):validate_url('https://localhost/x',{'upload.wikimedia.org'})
  def test_exfil_domain(self):
    with self.assertRaises(GateError):validate_url('https://upload.wikimedia.org.evil.invalid/x',{'upload.wikimedia.org'})
  def test_valid_photo(self):self.assertEqual(basic_gate(self.c,self.info,self.b),(520,530))
  def test_corrupt_pixel_file(self):
    with self.assertRaises(GateError):signature_and_image(self.b[:80])
  def test_wrong_mission(self):
    c=self.c|{'mission':'Starlink'}
    with self.assertRaises(GateError):basic_gate(c,self.info,self.b)
  def test_composite(self):
    c=self.c|{'exposure_s':600}
    with self.assertRaises(GateError):basic_gate(c,self.info,self.b)
  def test_upstream_hash_mismatch(self):
    with self.assertRaises(GateError):basic_gate(self.c,self.info|{'sha1':'abc'},self.b)
  def test_size_mismatch(self):
    with self.assertRaises(GateError):basic_gate(self.c,self.info|{'size':len(self.b)+1},self.b)
  def test_id_mismatch(self):
    with self.assertRaises(GateError):basic_gate(self.c|{'dvids_id':'10009473'},self.info,self.b)
  def test_immutable_by_sha(self):
    with tempfile.TemporaryDirectory() as d:
      mk,rk,m=write_local(pathlib.Path(d),self.c,self.info,self.b,520,530)
      self.assertTrue((pathlib.Path(d)/rk).exists())
      self.assertEqual(json.loads((pathlib.Path(d)/mk).read_text())['scientific_validation'],'BLOCKED')
      mk2,rk2,_=write_local(pathlib.Path(d),self.c,self.info,self.b,520,530)
      self.assertEqual(rk,rk2)
  def test_downstream_quarantine(self):
    with tempfile.TemporaryDirectory() as d:
      cfg={'candidates':[self.c|{'date':'2024-05-17'}]}
      r=run(cfg,d,fetcher=lambda *a:self.b,infogetter=lambda *a:self.info)
      self.assertEqual(r[0]['status'],'QUARANTINED_NOT_INGESTED')
      self.assertEqual(list((pathlib.Path(d)/'raw').glob('**/*')) if (pathlib.Path(d)/'raw').exists() else [],[])
  def test_success_local_fixture_not_real(self):
    with tempfile.TemporaryDirectory() as d:
      r=run({'candidates':[self.c]},d,fetcher=lambda *a:self.b,infogetter=lambda *a:self.info)
      self.assertEqual(r[0]['status'],'RAW_LOCAL_UNCALIBRATED')
      self.assertEqual(len(list((pathlib.Path(d)/'raw').glob('**/*.jpg'))),1)
  def test_no_remote_access_during_tests(self):
    self.assertEqual(MAX_BYTES,40*1024*1024)
if __name__=='__main__':unittest.main()
