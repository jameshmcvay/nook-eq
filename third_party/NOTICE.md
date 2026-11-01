# Third-party material

- `airpyrt-tools/acp/basebinary.py`: Vince Cali / x56, MIT; original licence alongside it. The local firmware reader uses its published model-key table. No Apple firmware is distributed here.
- `scripts/connection/package-lock.json` pins node-acp 0.7.0 and its dependencies for optional encrypted SSH setup. npm retrieves these separately, with their own licence files. They are not vendored into this repository or archive.
- NetBSD makefs is fetched only as an optional local build tool; its original copyright notices remain in the downloaded source. This project includes software developed by the NetBSD Foundation, Inc. and its contributors; by Christos Zoulas; by Manuel Bouyer; by the University of California, Berkeley and its contributors; and for the NetBSD Project by Wasabi Systems, Inc.
- The peaking filter equations follow the W3C Audio EQ Cookbook, by Robert Bristow-Johnson.
- `web/jhm.svg` is the author's existing logo from https://jhm.nz/logo.svg, optimized by removing editor metadata and its embedded ICC profile. It remains author branding rather than a grant to impersonate that identity.
