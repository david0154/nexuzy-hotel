import sys, os
src = os.path.join(os.getcwd(), '._nexuzy_hotel_management.py')
dst = os.path.join(os.getcwd(), 'recovered_from_hidden.py')
print('SRC:', src)
try:
    with open(src, 'rb') as fh:
        b = fh.read()
    print('Read bytes:', len(b))
    print('Sample bytes:', b[:128])
    s = b.decode('utf-8', 'replace')
    with open(dst, 'w', encoding='utf-8') as fh:
        fh.write(s)
    print('WROTE', dst, 'length', len(s))
except Exception as e:
    print('ERROR', e)
    sys.exit(1)
