#!/usr/bin/env python3
"""Pin title boot files (logo1/2 + backgrnd) and host title/menu selftest.

Read-only vs PS.EXE. Ghidra HTTP was down this pass — strings only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.ps_le import DEFAULT_EXE

NEEDLES = (
    b"logo1.pl8",
    b"logo1.256",
    b"logo2.pl8",
    b"logo2.256",
    b"backgrnd.pl8",
    b"backgrnd.256",
    b"forum1.xmi",
    b"intro.smk",
)


def main() -> int:
    exe = DEFAULT_EXE if DEFAULT_EXE.is_file() else None
    if exe is None:
        print("PS.EXE not at tools.ps_le.DEFAULT_EXE — skip string pin")
    else:
        blob = exe.read_bytes()
        print(f"exe {exe} {len(blob)} B")
        for needle in NEEDLES:
            print(f"  {needle.decode('ascii'):16}  {'ok' if needle in blob else 'MISSING'}")

    from app.title import selftest

    print("\n==== host title selftest ====")
    failed = 0
    for line in selftest():
        print(f"  {line}")
        if "FAIL" in line:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
