# Architecture

AirPlay decoder → packed PCM → `ath_i2s_write` → fixed-point EQ → DMA → stereo peripheral → AK4430 DAC.

The payload wraps the original `uiomove` call in the write path, filters only after a successful copy, and retains original failure behavior. Other wrappers track nominal 44.1/48 kHz rates and output initialization. Unsupported sample formats pass through.

Coefficients are Q29; sample/state arithmetic is fixed-point with 64-bit accumulation, fractional error retention and saturation counters. The kernel validates coefficient bounds and stability. Settings queue at a buffer boundary; requested/applied generations distinguish queued changes.

The guarded RAM loader requires the exact expected nine hook words and delay slots, symbol-size/cache guards, and an empty symbol-table tail arena. It writes the payload before exposing hooks, verifies readback, and synchronizes caches around aligned hook updates. A private memory-device node is removed afterwards. A partial load must not be retried blindly; reboot restores stock RAM.

The HTTP service embeds all assets. Coefficients and previews are calculated in the browser. The service opens only the private control descriptor, drops supplementary groups and UID/GID to 65534, and binds a private IPv4 address. There is no request-controlled filesystem access, shell command execution, arbitrary memory API or firmware upload API. POSTs require the correct Host, same Origin, content type and bounded body. The kernel remains the authority for valid programs, and readback is checked.

The persistent candidate embeds the payload, service, utility and a bounded asynchronous startup script into the stock root filesystem. Only persistent mode saves a validated program and its edit metadata by atomic rename in `/mnt/Flash/nook-eq/`. The initial preset is bypassed. RAM mode never writes that storage.
