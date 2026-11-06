"""Create an allowlisted GitHub source folder/ZIP without local data or archives."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
FILES=['README.md','DEMO.md','.gitignore','app.py','config.py','database_tools.py','manage.py','menu_catalog.py','preview.py','preview_access.py','qr.py','restaurant_profile.py','service.py','start-demo.command','start-preview.command','start-presentation.command']
TREES=['models','controllers','views','static','migrations','assets','tests','.github','examples']
FILES += ['tools/build_release.py','tools/build_image_credits.py','tools/export_sql_catalog.py']
FILES += ['tools/export_readable_demo.py']
FILES += ['docs/'+n for n in ['ARCHITECTURE.md','DATABASE.md','QA_REPORT.md','QA_TEST_CASES.md','MVC.md','ORDER_STATUS.md','RESTAURANT_PROFILE.md','REMOTE_PREVIEW.md','CLEANUP.md','RELEASE_CHECKS.md']]

def selected_files():
    paths=[ROOT/f for f in FILES]
    for name in TREES:paths.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name not in {'.DS_Store','Thumbs.db'})
    for p in paths:
        if not p.is_file() or p.is_symlink():raise SystemExit('Missing or unsafe release file: '+str(p.relative_to(ROOT)))
    return sorted(set(paths))

def main():
    paths=selected_files();forbidden=re.compile(r'/Users/|/private/var/|/var/folders/|https://[a-z0-9-]+\.trycloudflare\.com|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}')
    for p in paths:
        if p.suffix in ('.py','.md','.json','.html','.js','.yml','.txt'):
            text=p.read_text()
            if p.name!='build_release.py' and forbidden.search(text):raise SystemExit('Review private-machine path / secret / temporary URL: '+str(p.relative_to(ROOT)))
    target=ROOT/'dist/sa-restaurant-github';target.parent.mkdir(exist_ok=True)
    if target.exists():
        if not (target/'release-manifest.json').is_file():raise SystemExit('Will not replace an unrecognized output folder')
        shutil.rmtree(target)
    manifest=[]
    for p in paths:
        relative=p.relative_to(ROOT);dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        manifest.append(dict(path=relative.as_posix(),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),bytes=dest.stat().st_size))
    (target/'release-manifest.json').write_text(json.dumps(dict(files=manifest,excluded=['data','sessions and per-bill tokens','preview-access.json','.local-archive','.tools','tmp','report sources and old screenshots']),indent=2))
    archive=ROOT/'dist/sa-restaurant-github.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(target.rglob('*')):
            if p.is_file():z.write(p,Path(target.name)/p.relative_to(target))
    print('Source folder:',target);print('ZIP:',archive);print('Files:',len(manifest)+1,'size:',archive.stat().st_size)

if __name__=='__main__':main()
