# ATH Móvil Payment Provider for Odoo

**English** | [Español](#español)

Integrate [ATH Móvil Business](https://ath.business) as a native payment method in Odoo 17, 18, and 19. ATH Móvil is Puerto Rico's dominant mobile payment network, operated by EVERTEC Group, LLC.

> **ATH Móvil® is a registered trademark of EVERTEC Group, LLC. This module is an independent integration and is not affiliated with or endorsed by EVERTEC.**

---

## Features

- Accept ATH Móvil payments in eCommerce, Invoicing, Sales, and Customer Portal
- Webhook + frontend polling fallback for reliable payment confirmation
- Multi-company support — each company uses its own ATH Business credentials
- Full refund support (partial refunds subject to ATH Móvil API capability — see Testing)
- Automatic expiry of abandoned pending transactions (cron every 15 minutes)
- Sandbox mode using `publicToken = "dummy"`
- Bilingual interface (English / Spanish)
- Compatible with Odoo 17, 18, and 19

---

## Requirements

- Odoo 17, 18, or 19 (Community or Enterprise)
- An active [ATH Business](https://ath.business) merchant account
- Your own ATH Business **Public Token** and **Private Key**
- You must accept [ATH Business Terms and Conditions](https://ath.business/terminos) before activating this provider

---

## Installation

1. Clone or copy the `payment_athmovil` folder into your Odoo addons directory:
   ```bash
   git clone https://github.com/sparkworkforcellc/payment_athmovil.git /path/to/odoo/addons/payment_athmovil
   ```
2. Restart your Odoo server
3. Update the apps list: **Settings → Apps → Update Apps List**
4. Search for **"ATH Móvil"** and click **Install**

---

## Configuration

1. Go to **Invoicing → Configuration → Payment Providers** (or **Website → Configuration → Payment Providers**)
2. Find **ATH Móvil** and click **Activate**
3. Enter your ATH Business credentials:
   - **Public Token**: found in ATH Business app → Settings → Development
   - **Private Token**: found in ATH Business app → Settings → Development
4. Set the provider state to **Enabled** for production
5. **(Recommended)** Configure the webhook URL in your ATH Business app:
   - Go to **ATH Business app → Settings → Development → Webhooks**
   - Set the webhook URL to: `https://yourdomain.com/payment/athmovil/webhook`

---

## Testing

ATH Móvil does not have a traditional sandbox environment. Use the following procedure:

### Step 1 — Configure sandbox mode
Set the **Public Token** field to `dummy` in the provider settings. Do **not** enter a real Private Token for testing.

### Step 2 — Prepare two separate ATH accounts
- **ATH Business account** (merchant): the account you registered at [ath.business](https://ath.business)
- **ATH Móvil Personal account** (customer): a separate ATH Móvil Personal account on a **different phone** with a **different ATH card**

> ⚠️ The merchant ATH Business account and the customer ATH Móvil Personal account **cannot be the same card or the same phone**.

### Step 3 — Run a test payment
1. Go to your Odoo eCommerce store and add a product to the cart
2. Proceed to checkout and select **ATH Móvil** as the payment method
3. The ATH Móvil payment modal will appear
4. On the **customer phone**, open the ATH Móvil Personal app — you will see a simulated payment request
5. Approve, cancel, or let it expire to test each flow

### Step 4 — Verify the transaction
- Check **Invoicing → Accounting → Payments** to confirm the transaction status
- Check the transaction chatter for detailed log messages

---

## Webhook Configuration

For production use, configure the webhook in your ATH Business app to ensure reliable payment confirmation:

1. Open the **ATH Business app** on your phone
2. Go to **Settings → Development → Webhooks**
3. Add your webhook URL: `https://yourdomain.com/payment/athmovil/webhook`

If the webhook is not configured, the module will fall back to frontend polling (every 5 seconds, up to 10 minutes).

---

## Legal Notice

- ATH Móvil® is a registered trademark of EVERTEC Group, LLC.
- This module is an independent integration and is **not affiliated with or endorsed by EVERTEC**.
- Each merchant must have their own active ATH Business account.
- You must accept [ATH Business Terms and Conditions](https://ath.business/terminos) before using this provider.
- ATH Business support: **787-773-5466**

---

## License

[LGPL-3.0](../LICENSE) — GNU Lesser General Public License v3.0

---

## Author

**Spark Workforce LLC**
- Website: [sparkworkforcellc.com](https://www.sparkworkforcellc.com)
- Support: [jvelez@sparkworkforcellc.com](mailto:jvelez@sparkworkforcellc.com)

---

---

# Español

# Proveedor de Pago ATH Móvil para Odoo

Integra [ATH Móvil Business](https://ath.business) como método de pago nativo en Odoo 17, 18 y 19. ATH Móvil es la red de pagos móviles dominante en Puerto Rico, operada por EVERTEC Group, LLC.

> **ATH Móvil® es una marca registrada de EVERTEC Group, LLC. Este módulo es una integración independiente y no está afiliado ni respaldado por EVERTEC.**

---

## Características

- Acepta pagos ATH Móvil en eCommerce, Facturación, Ventas y Portal del Cliente
- Webhook + polling frontend como respaldo para confirmación confiable de pagos
- Soporte multi-compañía — cada empresa usa sus propias credenciales ATH Business
- Soporte de reembolsos completos (reembolsos parciales sujetos a capacidad del API de ATH Móvil)
- Expiración automática de transacciones pendientes abandonadas (cron cada 15 minutos)
- Modo sandbox usando `publicToken = "dummy"`
- Interfaz bilingüe (inglés / español)
- Compatible con Odoo 17, 18 y 19

---

## Requisitos

- Odoo 17, 18 o 19 (Community o Enterprise)
- Una cuenta activa de [ATH Business](https://ath.business) como comerciante
- Tu propio **Token Público** y **Token Privado** de ATH Business
- Debes aceptar los [Términos y Condiciones de ATH Business](https://ath.business/terminos) antes de activar este proveedor

---

## Instalación

1. Clona o copia la carpeta `payment_athmovil` en tu directorio de addons de Odoo:
   ```bash
   git clone https://github.com/sparkworkforcellc/payment_athmovil.git /ruta/a/odoo/addons/payment_athmovil
   ```
2. Reinicia tu servidor Odoo
3. Actualiza la lista de apps: **Configuración → Apps → Actualizar Lista de Apps**
4. Busca **"ATH Móvil"** y haz clic en **Instalar**

---

## Configuración

1. Ve a **Facturación → Configuración → Proveedores de Pago** (o **Sitio Web → Configuración → Proveedores de Pago**)
2. Encuentra **ATH Móvil** y haz clic en **Activar**
3. Ingresa tus credenciales de ATH Business:
   - **Token Público**: se encuentra en la app ATH Business → Configuración → Desarrollo
   - **Token Privado**: se encuentra en la app ATH Business → Configuración → Desarrollo
4. Cambia el estado del proveedor a **Habilitado** para producción
5. **(Recomendado)** Configura la URL del webhook en tu app ATH Business:
   - Ve a **App ATH Business → Configuración → Desarrollo → Webhooks**
   - Establece la URL del webhook: `https://tudominio.com/payment/athmovil/webhook`

---

## Pruebas

ATH Móvil no tiene un ambiente sandbox tradicional. Usa el siguiente procedimiento:

### Paso 1 — Configurar modo sandbox
Establece el campo **Token Público** como `dummy` en la configuración del proveedor.

### Paso 2 — Preparar dos cuentas ATH separadas
- **Cuenta ATH Business** (comerciante): la cuenta que registraste en [ath.business](https://ath.business)
- **Cuenta ATH Móvil Personal** (cliente): una cuenta ATH Móvil Personal separada en un **teléfono diferente** con una **tarjeta ATH diferente**

> ⚠️ La cuenta ATH Business del comerciante y la cuenta ATH Móvil Personal del cliente **no pueden ser la misma tarjeta ni el mismo teléfono**.

### Paso 3 — Ejecutar un pago de prueba
1. Ve a tu tienda eCommerce de Odoo y agrega un producto al carrito
2. Procede al checkout y selecciona **ATH Móvil** como método de pago
3. Aparecerá el modal de pago de ATH Móvil
4. En el **teléfono del cliente**, abre la app ATH Móvil Personal — verás una solicitud de pago simulada
5. Aprueba, cancela o deja que expire para probar cada flujo

### Paso 4 — Verificar la transacción
- Revisa **Facturación → Contabilidad → Pagos** para confirmar el estado de la transacción
- Revisa el chatter de la transacción para mensajes de log detallados

---

## Configuración del Webhook

Para uso en producción, configura el webhook en tu app ATH Business:

1. Abre la **app ATH Business** en tu teléfono
2. Ve a **Configuración → Desarrollo → Webhooks**
3. Agrega tu URL de webhook: `https://tudominio.com/payment/athmovil/webhook`

Si el webhook no está configurado, el módulo usará polling frontend como respaldo (cada 5 segundos, hasta 10 minutos).

---

## Aviso Legal

- ATH Móvil® es una marca registrada de EVERTEC Group, LLC.
- Este módulo es una integración independiente y **no está afiliado ni respaldado por EVERTEC**.
- Cada comerciante debe tener su propia cuenta activa de ATH Business.
- Debes aceptar los [Términos y Condiciones de ATH Business](https://ath.business/terminos) antes de usar este proveedor.
- Soporte ATH Business: **787-773-5466**

---

## Licencia

[LGPL-3.0](../LICENSE) — GNU Lesser General Public License v3.0

---

## Autor

**Spark Workforce LLC**
- Sitio web: [sparkworkforcellc.com](https://www.sparkworkforcellc.com)
- Soporte: [jvelez@sparkworkforcellc.com](mailto:jvelez@sparkworkforcellc.com)
