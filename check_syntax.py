import py_compile
import traceback
import sys

path = r"f:/book/soft/nex/nexuzy hotel/nexuzy_hotel_management.py"
try:
    py_compile.compile(path, doraise=True)
    print('COMPILE_OK')
except Exception:
    traceback.print_exc()
    sys.exit(1)
