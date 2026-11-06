import sys, os, shutil
src, outdir = sys.argv[1], sys.argv[2]
hooks = sys.argv[3:]
s = open(src, encoding='utf-8').read()
s = s.replace('<head>', '<head><script>window.onerror=(m,u,l,c)=>{document.documentElement.setAttribute("data-err",m+" @"+l+":"+c)};</script>', 1)
for h in hooks:
    s = s.replace('</body>', open(h, encoding='utf-8').read() + '\n</body>', 1)
os.makedirs(os.path.join(outdir, 'assets'), exist_ok=True)
shutil.copyfile(os.path.join(os.path.dirname(src), 'assets', 'karnataka-emblem.png'), os.path.join(outdir, 'assets', 'karnataka-emblem.png'))
open(os.path.join(outdir, 'index.html'), 'w', encoding='utf-8').write(s)
print('debug build ok')
