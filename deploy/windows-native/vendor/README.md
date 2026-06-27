# Vendor binaries for native Windows releases

Do not commit runtime binaries here. The release process must provide or copy these artifacts from controlled sources during packaging:

- Python runtime for Windows.
- PostgreSQL portable/runtime for Windows.
- Caddy for Windows.
- WinSW or equivalent service wrapper.

This repository only stores packaging scripts, templates and placeholders. Binary `.exe`, `.dll`, `.msi` and large `.zip` artifacts must stay outside Git.
