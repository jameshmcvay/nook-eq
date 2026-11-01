# Development

Python build dependencies are pinned in `requirements-build.txt`; test dependencies are in `requirements-test.txt`. Native HTTP tests use clang and the same C parser with a fake-driver syscall shim. MIPS tests use Unicorn and require JIT permission on macOS.

```sh
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python scripts/prepare_stock.py
.venv/bin/python scripts/build.py --release-binaries
clang -std=c99 -O2 -dynamiclib -Isrc src/eq.c -o build/libeq.dylib
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

On Linux, build the native DSP reference with `-shared -fPIC` instead of `-dynamiclib`; the current ctypes test filename remains `build/libeq.dylib`.

`tests/test_http_device.py` covers assets, binary status, program readback, LAN access without a code, host/origin checks, bounded bodies, duplicate headers and path confinement. `tests/test_persistence.py` checks atomic profile save/restart/restore and invalid-profile rejection in a temporary host directory. DSP tests compare against double precision and cover bypass, clipping, channel isolation and chunk/state behavior. Loader tests check exact-build guards, cache/write ordering, partial failures and the stock aligned-word copy implementation.

`bin/` contains only this project's compiled tools and manifests. `build/`, `firmware/` image inputs, `private/`, `.venv/` and release archives are ignored. Do not copy your research workspace into this repo. The release packager uses an allowlist and audits paths/content before archiving.

The UI is static HTML/CSS/JS with no package manager or web build step. The jhm SVG is the existing mark from jhm.nz, with only editor metadata and the embedded ICC profile removed. Design tokens follow the author's Kestrel/Concordski palette.
