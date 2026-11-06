import sys, os
src, dst = sys.argv[1], sys.argv[2]
with open(src, 'rb') as f:      # read-only access to the source
    data = f.read()
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, 'wb') as f:
    f.write(data)
print('copied', len(data), 'bytes ->', dst)
