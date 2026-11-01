"""Create a public-source/installer archive from an explicit allowlist."""
import hashlib,json,os,re,tarfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.0'
FILES=['README.md','LICENSE','CHANGELOG.md','SECURITY.md','Install.command','install.py','requirements-build.txt','requirements-test.txt','.gitignore','.gitattributes']
DIRS=['bin','src','web','scripts','docs','tests','third_party','.github']
DENIED={'node_modules','__pycache__','.git','private','recovery','firmware','work','build','dist','.venv'}
def members():
 paths=[ROOT/f for f in FILES]
 for folder in DIRS:
  if (ROOT/folder).exists():paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and not any(part in DENIED for part in p.relative_to(ROOT).parts) and p.suffix not in ['.pyc','.log'])
 return sorted(set(paths))
def main():
 paths=members();manifest={}
 for p in paths:
  rel=str(p.relative_to(ROOT));data=p.read_bytes()
  if p.is_symlink() or any(token in data for token in [b'/' + b'Users/',b'/' + b'home/',b'BEGIN ' + b'OPENSSH PRIVATE KEY',b'BEGIN ' + b'RSA PRIVATE KEY']):raise ValueError('Private path/key or unexpected symlink: '+rel)
  if p.suffix in ['.basebinary','.ffs'] or 'http_access_code' in rel or 'flash0' in rel:raise ValueError('Device material: '+rel)
  manifest[rel]=hashlib.sha256(data).hexdigest()
 out=ROOT/'dist';out.mkdir(exist_ok=True);name='nook-eq-'+VERSION
 with zipfile.ZipFile(out/(name+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
  for p in paths:z.write(p,name+'/'+str(p.relative_to(ROOT)))
  z.writestr(name+'/SHA256SUMS',''.join(h+'  '+p+'\n' for p,h in sorted(manifest.items())))
 artifact=out/(name+'.zip');(out/'SHA256SUMS').write_text(hashlib.sha256(artifact.read_bytes()).hexdigest()+'  '+artifact.name+'\n')
 (out/'audit.json').write_text(json.dumps(dict(files=len(paths),archive_bytes=artifact.stat().st_size,excluded=list(sorted(DENIED)),apple_firmware_included=False,device_backups_included=False),indent=2)+'\n')
 print(artifact);print(f'{len(paths)} allowlisted files; no firmware or device backups.')
if __name__=='__main__':main()
