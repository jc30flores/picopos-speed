# DTE transmission setup

## Required env vars

```env
MH_AMBIENTE=00
DTE_BASE_URL=https://factura.cheros.dev
DTE_API_TOKEN=xxxx
DTE_API_AUTH_HEADER=Authorization
DTE_API_AUTH_PREFIX=Bearer
DTE_TIMEOUT_SECONDS=30
DTE_DEBUG=0
```

## Notes

- DTE sending uses real HTTP by default (no internal mock by default).
- Change only `MH_AMBIENTE`, `DTE_BASE_URL`, and `DTE_API_TOKEN` to move environments.
- Every send persists a `DTETransmissionLog` row with request, status, response body and parsed key fields.
- Test command:

```bash
python manage.py dte_send_test --order-id 48
```
