# Persistent firmware preparation

**Prepared candidate, not boot-tested.** The simple installer never flashes it.

Install the build dependencies, then provide a NetBSD-compatible `makefs`:

```sh
.venv/bin/python scripts/prepare_stock.py
.venv/bin/python scripts/build.py --release-binaries
.venv/bin/python scripts/persistent.py --makefs /path/to/makefs
```

Output: `build/nook-persistent-7.8.1.basebinary` and `build/persistent_report.json`.

The builder checks the stock download SHA-256, nested envelopes and raw kernel hash. It preserves the original image size and boot stub, uses the audited code arena, rebuilds a big-endian UFS1 root at the same embedded offset and length, and compares every original regular file, owner/mode, symlink, device number and hardlink group. Both firmware envelopes and the gzip stream are revalidated. The result must fit the measured 7 MiB bank capacity.

A portable 2004 NetBSD `makefs` built from https://www.daemonology.net/makefs/ was used locally. Modern hosts need the small compatibility adjustments in `scripts/build_makefs.py`; this helper downloads and builds it locally. Its upstream copyright notices remain with the downloaded tool. It is not bundled into the public release.

The candidate starts a separate web service after AirPort startup and after bridge addressing is ready. Failure/timeouts must not block the stock startup sequence. Its private control node and service log live in RAM. Persistent mode stores the last valid UI program/profile in its own directory on the existing settings filesystem, then restores it at startup. A first boot with no profile starts in bypass.

Before an actual firmware boot test, retain the untouched stock image and private device flash backups and establish recovery appropriate to the unit. Never write the secondary bank, factory data or bootloader for this project. A checksum-valid kernel hang does not trigger automatic bank fallback. Serial recovery may require opening the device. No persistent candidate has been uploaded or flashed during development.

Rollback while the device still boots: reinstall the hash-verified stock image using AirPort Utility. A normal configuration reset is not a proven repair for a kernel that fails to boot. Factory/calibration backups must stay private and must never be committed to GitHub.
