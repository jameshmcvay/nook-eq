"""Validate distributable SVGs and browser/Python coefficient compatibility."""
import json,random,subprocess,sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from configure import make_program,blob
class AssetTests(unittest.TestCase):
 def test_actual_logo_is_valid_svg(self):
  root=ET.parse(ROOT/'web/jhm.svg').getroot();self.assertEqual(root.tag,'{http://www.w3.org/2000/svg}svg');self.assertGreater(len(list(root.iter())),3)
 def test_browser_coefficients_match_reference(self):
  rng=random.Random(41);configs=[dict(enabled=True,preamp_db=0,bands=[])]
  for _ in range(200):configs.append(dict(enabled=rng.choice([True,False]),preamp_db=rng.uniform(-24,0),bands=[dict(type='peaking',frequency_hz=10**rng.uniform(1,4.3),gain_db=rng.uniform(-8,8),q=rng.uniform(.2,5)) for i in range(rng.randrange(9))]))
  script="const fs=require('node:fs'),eq=require('./web/coeff.js');console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(c=>Buffer.from(eq.program(c)).toString('hex'))));"
  r=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps(configs),text=True,capture_output=True,check=True)
  self.assertEqual(json.loads(r.stdout),[blob(make_program(c)).hex() for c in configs])
if __name__=='__main__':unittest.main(verbosity=2)
