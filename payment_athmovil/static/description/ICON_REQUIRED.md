# Icon Required Before Publishing

Before publishing to Odoo Apps Store, add a 64x64 PNG file named `icon.png`
in this directory (`static/description/icon.png`).

**Important**: The ATH Móvil® logo is a registered trademark of EVERTEC Group, LLC.
Do NOT use the ATH Móvil logo without written permission from EVERTEC.

Use a neutral placeholder icon (e.g., a simple payment/mobile icon) until
you obtain permission or create an original icon for this module.

You can generate a simple placeholder with:
```python
from PIL import Image
img = Image.new('RGB', (64, 64), color=(26, 130, 200))
img.save('icon.png')
```
