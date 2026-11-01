# Diagnostic SSH prerequisite

The RAM installer needs an existing diagnostic root SSH login. Enabling that login is separate from modifying firmware. The known `dbug` value `0x3000` enables the stock SSH daemon after a reboot; root uses the AirPort admin password.

Reference: https://github.com/TDSOJohn/airport-express-tools/blob/main/docs/dbug.md

This repository's installer never asks you to paste the admin password into chat, a command argument or an environment variable. `Install.command` / `install.py` use the local OpenSSH password and host-key prompts. Older AirPort SSH algorithms are enabled only for this connection.

If SSH is not enabled, use the encrypted, interactive helper:

```sh
npm ci --prefix scripts/connection --ignore-scripts --no-audit --no-fund
NOOK_HOST=your-airport.local python3 scripts/setup_ssh.py --enable
```

This first setup requires Node/npm and one reboot. It checks model 115 and firmware 7.8.1, preserves unrelated debug flags and records the prior value under ignored `private/`. It does not upload firmware. If the connection closes after a write, inspect first; do not repeatedly write or reboot. `--finish-enable` verifies the saved target flags before requesting a reboot without repeating the write.

Then run the normal installer. During a RAM-only session, diagnostic SSH remains enabled after reboot, but the EQ patch and web service do not.
