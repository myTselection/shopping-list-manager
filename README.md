# Shopping List Manager Integration for Home Assistant

The backend integration that powers the Shopping List Manager. Provides persistent multi-list storage, a 500+ product catalog, real-time WebSocket events, and a full API for the Lovelace card — all running natively inside Home Assistant.

> **Pair with the [Shopping List Manager Card](https://github.com/thekiwismarthome/shopping-list-manager-card)** for the full UI experience.

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=thekiwismarthome&repository=shopping-list-manager&category=integration)

---

## Features

### 🛒 Multi-List Management
- Create and manage multiple shopping lists
- Private or shared lists with per-member access control
- Active list state shared across all connected devices and users
- List total price calculation

### 📦 Items
- Add, update, check, and delete items with quantity and unit
- Atomic quantity increment / decrement
- Bulk check and clear checked items
- Per-item pricing, notes, and category assignment

### 🔍 Product Catalog
- **500+ products** (NZ-focused, extensible to AU, US, GB, CA)
- Fuzzy search with alias matching
- Recently-used product suggestions
- Custom product creation
- Allergen filtering and product substitute groups
- Product images (WebP, 200×200px, optimised)

### 🗂️ Categories
- 13 default categories — Produce, Dairy, Meat, Bakery, Pantry, Frozen, Beverages, Snacks, Household, Health, Pet, Baby, Other
- Category colour coding and emoji icons
- Per-list category ordering

### 💳 Loyalty Cards
- Store loyalty and rewards card data
- Private or shared card access per user

### 🔄 Real-Time Events
- All changes fire events on the Home Assistant bus
- Custom WebSocket subscription proxy so **non-admin users** receive live updates without requiring HA admin privileges

---

## Requirements

| Component | Minimum Version |
|---|---|
| Home Assistant | 2024.1 |
| HACS | 2.x |

---

## Installation

### Via HACS (Recommended)

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=thekiwismarthome&repository=shopping-list-manager&category=integration)

1. Click the button above
2. Confirm adding the repository to HACS
3. Install **Shopping List Manager** from **HACS → Integrations**
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** and search for **Shopping List Manager**

### Manual Installation

1. Copy the `custom_components/shopping_list_manager/` folder into your HA `/config/custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration** and search for **Shopping List Manager**

---

## Lovelace Card

Install the companion card to get the full shopping UI:

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=thekiwismarthome&repository=shopping-list-manager-card&category=plugin)

---

## Documentation

Full documentation is available in the [Wiki](https://github.com/thekiwismarthome/shopping-list-manager/wiki).

## Support & Feedback

- [Open an Issue](https://github.com/thekiwismarthome/shopping-list-manager/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io)

---

## License

MIT — see [LICENSE](LICENSE) for details.
