# Vendor binaries for native Windows releases

Do not commit runtime binaries here. The release process must provide or copy these artifacts from controlled sources during packaging:

- Python runtime for Windows.
- PostgreSQL portable/runtime for Windows.
- Caddy for Windows.
- WinSW or equivalent service wrapper.
- Inno Setup compiler for CI builds.

## Runtime manifest

`runtime-manifest.example.json` is only a schema/example. It intentionally contains placeholders and must not be used for a commercial release.

Use one of these safe options:

1. Commit `deploy/windows-native/vendor/runtime-manifest.json` only if every URL is public, HTTPS, version-specific and every SHA256 was verified from a trusted source.
2. Configure `WINDOWS_RUNTIME_MANIFEST_JSON` as a GitHub repository variable or secret when URLs are private, temporary or controlled outside the repo.

The workflow rejects placeholders, non-HTTPS URLs, `latest`, shortened URLs and invalid/missing SHA256 values. Do not relax those checks. Binary `.exe`, `.dll`, `.msi` and large `.zip` artifacts must stay outside Git.
