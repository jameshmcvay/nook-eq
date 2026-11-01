# Network scope

The UI is intentionally a no-login, private-LAN EQ control surface. Anyone on that LAN can adjust EQ. It is not an internet-facing administration service. Do not expose port 8080 through your router.

The service runs as UID/GID 65534 and holds a narrow validated EQ descriptor. It does not offer shell, flash, memory access or arbitrary request-controlled file paths. Diagnostic SSH is a separate root service using your AirPort admin password.

Please avoid posting firmware dumps, configuration exports, passwords, device keys, serial numbers or calibration data in public issues. Describe the model/firmware and redact personal data.
