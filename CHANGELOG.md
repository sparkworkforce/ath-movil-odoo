# Changelog — payment_athmovil

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Odoo module versioning](https://www.odoo.com/documentation/17.0/developer/reference/backend/module.html): `{odoo_major}.{major}.{minor}.{patch}`.

---

## [17.0.1.0.0] — 2026-04-05

### Added
- Initial release of ATH Móvil Payment Provider for Odoo 17, 18, and 19
- `payment.provider` extension with `athmovil_public_token` and `athmovil_private_token` fields
- `payment.transaction` extension with `athmovil_ecommerce_id` field (SQL UNIQUE constraint for idempotency)
- Payment flow: POST /payment ticket creation → ATHM_Checkout modal → webhook confirmation
- Webhook controller (`POST /payment/athmovil/webhook`) with idempotency check and cross-integrity verification
- Return controller (`POST /payment/athmovil/return`) for frontend callback after modal completion
- Polling fallback controller (`GET /payment/athmovil/check_status`) — frontend JS polls every 5 seconds up to 600 seconds
- Pre-checkout banner (5 seconds) with App Store and Google Play download links
- Legal notice for end customers on the payment form
- Full refund support via `POST /refund` (partial refunds provisional — subject to ATH Móvil API capability)
- Automatic expiry of abandoned pending transactions via `ir.cron` every 15 minutes
- Cron verifies real ATH Móvil status before cancelling (recovers payments where webhook was lost)
- Transaction amount limit validation: `ATH_MAX_TRANSACTION_AMOUNT = 1500.00` USD
- Multi-company support: credentials isolated per `company_id`
- Sandbox mode: set `publicToken = "dummy"` for testing
- Admin UI: legal notice banner with link to ATH Business Terms
- Bilingual interface: English and Spanish (i18n with `.po` files)
- Compatible with Odoo 17, 18, and 19 using `hasattr()` compatibility guards
- `__manifest__.py` with all fields required for Odoo Apps Store publication

### Security
- `athmovil_private_token` protected with `groups="base.group_system"` at ORM level
- `password=True` in view XML for UI masking
- No tokens logged at any level
- Webhook integrity verified without HMAC (ATH Móvil API does not provide signatures):
  - JSON structure validation
  - ecommerceId lookup in database
  - Amount verification (±$0.01 tolerance)
  - Idempotency check (state in done/cancel → 200 without reprocessing)

---

*For support, contact: jvelez@sparkworkforcellc.com or call ATH Business support at 787-773-5466*
