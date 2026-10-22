#!/usr/bin/env python3
"""Rotate the Royal Notebook capability URL. Writes it to ~/.secrets/notebook_url.txt (600) and republishes.
  nb_rotate.py          # new token
  nb_rotate.py show     # just refresh ~/.secrets/notebook_url.txt from KV"""
import os, sys; sys.path.insert(0, os.path.expanduser('~/bangla_bhai'))
import notebook as NB
p = os.path.expanduser('~/.secrets/notebook_url.txt')
u = NB.current_url() if sys.argv[1:] == ['show'] else NB.rotate()
fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f: f.write((u or '') + '\n')
os.system(os.path.expanduser('~/bangla_bhai/vault_tools/hook.sh'))
print('saved to', p)
