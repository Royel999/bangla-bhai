#!/usr/bin/env python3
"""বাংলা ভাই · Royal Link (Android/Termux + Shizuku rish)

Android uses the same client as desktop: royal_link.py, launched by
royal_link_termux.sh (see install_termux.sh and SHIZUKU_BN.md).
This wrapper simply runs royal_link.py from the same folder.
"""
import os, runpy, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
runpy.run_path(os.path.join(here, "royal_link.py"), run_name="__main__")
