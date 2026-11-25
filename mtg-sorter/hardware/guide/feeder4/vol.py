import sys, numpy as np, struct
def load(p):
    d=open(p,'rb').read()
    if d[:5]==b'solid':
        v=[list(map(float,l.split()[1:])) for l in d.decode().splitlines() if l.strip().startswith('vertex')]
        return np.array(v).reshape(-1,3,3)
    n=struct.unpack('<I',d[80:84])[0]; a=np.frombuffer(d[84:84+n*50],dtype=np.dtype([('n','<3f4'),('v','<9f4'),('a','<u2')]))
    return a['v'].reshape(-1,3,3).astype(float)
for p in sys.argv[1:]:
    t=load(p); vol=np.sum(np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])))/6
    print(p, 'vol %.3f mm3'%vol, 'bbox', t.reshape(-1,3).min(0).round(2), t.reshape(-1,3).max(0).round(2))
