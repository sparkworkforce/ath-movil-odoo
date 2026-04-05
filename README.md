# ATH Móvil Payment Provider for Odoo

Integrate [ATH Móvil Business](https://athbusiness.com) as a native payment method in Odoo 17, 18, and 19. ATH Móvil is Puerto Rico's dominant mobile payment network, operated by EVERTEC Group, LLC.

## Features

- Accept ATH Móvil payments in eCommerce, Invoicing, Sales, and Customer Portal
- Webhook + polling fallback for reliable payment confirmation
- Multi-company support — each company uses its own ATH Business credentials
- Full and partial refund support
- Automatic expiry of abandoned pending transactions (cron every 15 min)
- Sandbox mode using `publicToken = "dummy"`
- Bilingual interface (English / Spanish)

## Requirements

- Odoo 17, 18, or 19 (Community or Enterprise)
- An active [ATH Business](https://ath.business) merchant account
- Your own ATH Business Public Token and Private Key

## Installation

1. Clone this repository into your Odoo addons directory
2. Update the apps list: **Settings → Apps → Update Apps List**
3. Search for "ATH Móvil" and install
4. Configure your credentials under **Invoicing → Configuration → Payment Providers → ATH Móvil**

## Configuration

1. Enter your ATH Business **Public Token** and **Private Key**
2. Set the environment to **Test** (sandbox) or **Enabled** (production)
3. (Recommended) Configure the webhook URL in your ATH Business app under **Settings → Development → Webhooks** pointing to `https://yourdomain.com/payment/athmovil/webhook`

## Legal Notice

ATH Móvil® is a registered trademark of EVERTEC Group, LLC. This module is an independent integration and is not affiliated with or endorsed by EVERTEC.

Each merchant must have their own active ATH Business account. You must accept the ATH Business Terms at https://ath.business/terminos before using this provider.

ATH Business support: 787-773-5466

## License

[LGPL-3.0](LICENSE) — GNU Lesser General Public License v3.0

## Author

**Spark Workforce LLC** — [sparkworkforcellc.com](https://www.sparkworkforcellc.com)
