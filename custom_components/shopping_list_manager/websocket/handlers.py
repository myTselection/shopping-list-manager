"""WebSocket API handlers for Shopping List Manager."""
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from ..const import DOMAIN

from ..const import (
    WS_TYPE_LISTS_GET_ALL,
    WS_TYPE_LISTS_CREATE,
    WS_TYPE_LISTS_UPDATE,
    WS_TYPE_LISTS_DELETE,
    WS_TYPE_LISTS_SET_ACTIVE,
    WS_TYPE_LISTS_UPDATE_MEMBERS,
    WS_TYPE_USERS_GET_ALL,
    WS_TYPE_ITEMS_GET,
    WS_TYPE_ITEMS_ADD,
    WS_TYPE_ITEMS_UPDATE,
    WS_TYPE_ITEMS_CHECK,
    WS_TYPE_ITEMS_DELETE,
    WS_TYPE_ITEMS_REORDER,
    WS_TYPE_ITEMS_BULK_CHECK,
    WS_TYPE_ITEMS_CLEAR_CHECKED,
    WS_TYPE_ITEMS_GET_TOTAL,
    WS_TYPE_PRODUCTS_SEARCH,
    WS_TYPE_PRODUCTS_SUGGESTIONS,
    WS_TYPE_PRODUCTS_ADD,
    WS_TYPE_PRODUCTS_UPDATE,
    WS_TYPE_CATEGORIES_GET_ALL,
    WS_TYPE_LOYALTY_GET_ALL,
    WS_TYPE_LOYALTY_ADD,
    WS_TYPE_LOYALTY_UPDATE,
    WS_TYPE_LOYALTY_DELETE,
    WS_TYPE_LOYALTY_UPDATE_MEMBERS,
    WS_TYPE_SUBSCRIBE,
    EVENT_ITEM_ADDED,
    EVENT_ITEM_UPDATED,
    EVENT_ITEM_CHECKED,
    EVENT_ITEM_DELETED,
    EVENT_LIST_UPDATED,
    EVENT_LIST_DELETED,
)
from .. import get_storage

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# LIST HANDLERS
# =============================================================================

@websocket_api.websocket_command({
    vol.Required("type"): WS_TYPE_SUBSCRIBE,
})
@websocket_api.async_response
async def websocket_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Subscribe to shopping list manager events via WebSocket."""
    
    @callback
    def forward_event(event):
        """Forward HA bus event to WebSocket connection."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "event_type": event.event_type,
                    "data": event.data,
                }
            )
        )
    
    # Subscribe to all SLM events on the HA bus (backend has permission)
    unsubs = []
    unsubs.append(hass.bus.async_listen(EVENT_ITEM_ADDED, forward_event))
    unsubs.append(hass.bus.async_listen(EVENT_ITEM_UPDATED, forward_event))
    unsubs.append(hass.bus.async_listen(EVENT_ITEM_CHECKED, forward_event))
    unsubs.append(hass.bus.async_listen(EVENT_ITEM_DELETED, forward_event))
    unsubs.append(hass.bus.async_listen(EVENT_LIST_UPDATED, forward_event))
    unsubs.append(hass.bus.async_listen(EVENT_LIST_DELETED, forward_event))
    
    # Clean up when connection closes
    connection.subscriptions[msg["id"]] = lambda: [unsub() for unsub in unsubs]
    
    connection.send_message(websocket_api.result_message(msg["id"]))

@websocket_api.websocket_command({
    vol.Required("type"): "shopping_list_manager/items/increment",
    vol.Required("item_id"): str,
    vol.Required("amount"): vol.Coerce(float),
})
@websocket_api.async_response
async def websocket_increment_item(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Increment item quantity atomically."""

    storage = get_storage(hass)
    item_id = msg["item_id"]
    amount = msg["amount"]

    # First get current item
    for list_id, items in storage._items.items():
        for item in items:
            if item.id == item_id:
                new_quantity = item.quantity + amount

                if new_quantity < 1:
                    new_quantity = 1

                updated_item = await storage.update_item(
                    item_id,
                    quantity=new_quantity
                )
                if updated_item:
                    hass.bus.async_fire(
                        EVENT_ITEM_UPDATED,
                        {
                            "list_id": updated_item.list_id,
                            "item_id": item_id,
                            "item": updated_item.to_dict()
                        }
                    )
                    connection.send_result(msg["id"], {
                        "item": updated_item.to_dict()
                    })
                    return

    connection.send_error(msg["id"], "not_found", "Item not found")


@websocket_api.websocket_command({
    vol.Required("type"): "shopping_list_manager/products/get_by_ids",
    vol.Required("product_ids"): [str],
})
@websocket_api.async_response
async def ws_get_products_by_ids(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Return products matching given product IDs."""

    storage = get_storage(hass)
    product_ids = set(msg["product_ids"])

    # Get all products from storage
    all_products = storage.get_products()

    products = [
        product.to_dict()
        for product in all_products
        if product.id in product_ids
    ]

    connection.send_result(msg["id"], {"products": products})



@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_LISTS_GET_ALL,
    }
)
@callback
def websocket_get_lists(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle get all lists command."""
    storage = get_storage(hass)
    user = connection.user
    user_id = user.id if user else None
    is_admin = user.is_admin if user else False
    lists = storage.get_lists(user_id=user_id, is_admin=is_admin)

    connection.send_result(
        msg["id"],
        {
            "lists": [lst.to_dict() for lst in lists]
        }
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_LISTS_CREATE,
        vol.Required("name"): str,
        vol.Optional("icon", default="mdi:cart"): str,
        vol.Optional("private", default=True): bool,
    }
)
@websocket_api.async_response
async def websocket_create_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle create list command."""
    storage = get_storage(hass)

    # Private lists are owned by the creating user; global lists have no owner.
    is_private = msg.get("private", True)
    owner_id = connection.user.id if is_private and connection.user else None

    new_list = await storage.create_list(
        name=msg["name"],
        icon=msg.get("icon", "mdi:cart"),
        owner_id=owner_id,
    )
    
    # Fire event
    hass.bus.async_fire(
        EVENT_LIST_UPDATED,
        {"list_id": new_list.id, "action": "created"}
    )
    
    connection.send_result(
        msg["id"],
        {"list": new_list.to_dict()}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_LISTS_UPDATE,
        vol.Required("list_id"): str,
        vol.Optional("name"): str,
        vol.Optional("icon"): str,
        vol.Optional("category_order"): [str],
    }
)
@websocket_api.async_response
async def websocket_update_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle update list command."""
    storage = get_storage(hass)
    list_id = msg["list_id"]
    
    # Build update kwargs
    update_data = {}
    if "name" in msg:
        update_data["name"] = msg["name"]
    if "icon" in msg:
        update_data["icon"] = msg["icon"]
    if "category_order" in msg:
        update_data["category_order"] = msg["category_order"]
    
    updated_list = await storage.update_list(list_id, **update_data)
    
    if updated_list is None:
        connection.send_error(msg["id"], "not_found", "List not found")
        return
    
    # Fire event
    hass.bus.async_fire(
        EVENT_LIST_UPDATED,
        {"list_id": list_id, "action": "updated"}
    )
    
    connection.send_result(
        msg["id"],
        {"list": updated_list.to_dict()}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_LISTS_DELETE,
        vol.Required("list_id"): str,
    }
)
@websocket_api.async_response
async def websocket_delete_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle delete list command."""
    storage = get_storage(hass)
    list_id = msg["list_id"]

    lst = storage.get_list(list_id)
    if lst is None:
        connection.send_error(msg["id"], "not_found", "List not found")
        return

    # Only the owner or an admin may delete a private list
    if lst.owner_id is not None:
        user = connection.user
        if not (user and (user.is_admin or user.id == lst.owner_id)):
            connection.send_error(msg["id"], "forbidden", "Only the list owner can delete this list")
            return

    success = await storage.delete_list(list_id)

    if not success:
        connection.send_error(msg["id"], "not_found", "List not found")
        return
    
    # Fire event
    hass.bus.async_fire(
        EVENT_LIST_DELETED,
        {"list_id": list_id}
    )
    
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_LISTS_SET_ACTIVE,
        vol.Required("list_id"): str,
    }
)
@websocket_api.async_response
async def websocket_set_active_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle set active list command."""
    storage = get_storage(hass)
    list_id = msg["list_id"]
    
    success = await storage.set_active_list(list_id)
    
    if not success:
        connection.send_error(msg["id"], "not_found", "List not found")
        return
    
    # Fire event
    hass.bus.async_fire(
        EVENT_LIST_UPDATED,
        {"list_id": list_id, "action": "set_active"}
    )
    
    connection.send_result(msg["id"], {"success": True})


# =============================================================================
# ITEM HANDLERS
# =============================================================================

@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_ITEMS_GET,
        vol.Required("list_id"): str,
    }
)
@callback
def websocket_get_items(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle get items command."""
    storage = get_storage(hass)
    list_id = msg["list_id"]
    
    items = storage.get_items(list_id)
    
    connection.send_result(
        msg["id"],
        {
            "items": [item.to_dict() for item in items]
        }
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_ITEMS_ADD,
        vol.Required("list_id"): str,
        vol.Required("name"): str,
        vol.Required("category_id"): str,
        vol.Optional("product_id"): str,
        vol.Optional("quantity", default=1): vol.Coerce(float),
        vol.Optional("unit", default="units"): str,
        vol.Optional("note"): str,
        vol.Optional("price"): vol.Coerce(float),
        vol.Optional("image_url"): str,
        vol.Optional("barcode"): str,
    }
)
@websocket_api.async_response
async def websocket_add_item(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle add item command."""
    storage = get_storage(hass)
    list_id = msg["list_id"]
    
    # Build item data
    item_data = {
        "name": msg["name"],
        "category_id": msg["category_id"],
        "quantity": msg.get("quantity", 1),
        "unit": msg.get("unit", "units"),
    }
    
    # Optional fields
    optional_fields = ["product_id", "note", "price", "image_url", "barcode"]
    for field in optional_fields:
        if field in msg:
            item_data[field] = msg[field]
    
    new_item = await storage.add_item(list_id, **item_data)
    
    if new_item is None:
        connection.send_error(msg["id"], "not_found", "List not found")
        return
    
    # Fire event
    hass.bus.async_fire(
        EVENT_ITEM_ADDED,
        {
            "list_id": list_id,
            "item_id": new_item.id,
            "item": new_item.to_dict()
        }
    )
    
    connection.send_result(
        msg["id"],
        {"item": new_item.to_dict()}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_ITEMS_UPDATE,
        vol.Required("item_id"): str,
        vol.Optional("name"): str,
        vol.Optional("quantity"): vol.Coerce(float),
        vol.Optional("unit"): str,
        vol.Optional("note"): str,
        vol.Optional("price"): vol.Coerce(float),
        vol.Optional("category_id"): str,
        vol.Optional("image_url"): str,
    }
)
@websocket_api.async_response
async def websocket_update_item(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle update item command."""
    storage = get_storage(hass)
    item_id = msg["item_id"]
    
    # Build update data
    update_data = {}
    update_fields = ["name", "quantity", "unit", "note", "price", "category_id", "image_url"]
    for field in update_fields:
        if field in msg:
            update_data[field] = msg[field]
    
    updated_item = await storage.update_item(item_id, **update_data)
    
    if updated_item is None:
        connection.send_error(msg["id"], "not_found", "Item not found")
        return
    
    # Fire event
    hass.bus.async_fire(
        EVENT_ITEM_UPDATED,
        {
            "list_id": updated_item.list_id,
            "item_id": item_id,
            "item": updated_item.to_dict()
        }
    )
    
    connection.send_result(
        msg["id"],
        {"item": updated_item.to_dict()}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_ITEMS_CHECK,
        vol.Required("item_id"): str,
        vol.Required("checked"): bool,
    }
)
@websocket_api.async_response
async def websocket_check_item(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle check/uncheck item command."""
    storage = get_storage(hass)
    item_id = msg["item_id"]
    checked = msg["checked"]
    
    updated_item = await storage.check_item(item_id, checked)
    
    if updated_item is None:
        connection.send_error(msg["id"], "not_found", "Item not found")
        return
    
    # Fire event
    hass.bus.async_fire(
        EVENT_ITEM_CHECKED,
        {
            "list_id": updated_item.list_id,
            "item_id": item_id,
            "checked": checked
        }
    )
    
    connection.send_result(
        msg["id"],
        {"item": updated_item.to_dict()}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_ITEMS_DELETE,
        vol.Required("item_id"): str,
    }
)
@websocket_api.async_response
async def websocket_delete_item(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle delete item command."""
    storage = get_storage(hass)
    item_id = msg["item_id"]
    
    success = await storage.delete_item(item_id)
    
    if not success:
        connection.send_error(msg["id"], "not_found", "Item not found")
        return
    
    # Fire event
    hass.bus.async_fire(
        EVENT_ITEM_DELETED,
        {"item_id": item_id}
    )
    
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_ITEMS_REORDER,
        vol.Required("list_id"): str,
        vol.Required("item_order"): [str],
    }
)
@websocket_api.async_response
async def websocket_reorder_items(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle reorder items command."""
    storage = get_storage(hass)
    list_id = msg["list_id"]
    item_order = msg["item_order"]
    
    updated_list = await storage.update_list(list_id, item_order=item_order)
    
    if updated_list is None:
        connection.send_error(msg["id"], "not_found", "List not found")
        return
    
    # Fire event
    hass.bus.async_fire(
        EVENT_LIST_UPDATED,
        {"list_id": list_id, "action": "reordered"}
    )
    
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_ITEMS_BULK_CHECK,
        vol.Required("item_ids"): [str],
        vol.Required("checked"): bool,
    }
)
@websocket_api.async_response
async def websocket_bulk_check_items(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle bulk check/uncheck items command."""
    storage = get_storage(hass)
    item_ids = msg["item_ids"]
    checked = msg["checked"]
    
    count = await storage.bulk_check_items(item_ids, checked)
    
    # Fire event
    hass.bus.async_fire(
        EVENT_ITEM_CHECKED,
        {
            "item_ids": item_ids,
            "checked": checked,
            "count": count
        }
    )
    
    connection.send_result(
        msg["id"],
        {"success": True, "count": count}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_ITEMS_CLEAR_CHECKED,
        vol.Required("list_id"): str,
    }
)
@websocket_api.async_response
async def websocket_clear_checked_items(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle clear checked items command."""
    storage = get_storage(hass)
    list_id = msg["list_id"]
    
    count = await storage.clear_checked_items(list_id)
    
    # Fire event
    hass.bus.async_fire(
        EVENT_ITEM_DELETED,
        {"list_id": list_id, "count": count, "action": "cleared_checked"}
    )
    
    connection.send_result(
        msg["id"],
        {"success": True, "count": count}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_ITEMS_GET_TOTAL,
        vol.Required("list_id"): str,
    }
)
@callback
def websocket_get_list_total(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle get list total command."""
    storage = get_storage(hass)
    list_id = msg["list_id"]
    
    total_data = storage.get_list_total(list_id)
    
    connection.send_result(msg["id"], total_data)


# =============================================================================
# PRODUCT HANDLERS
# =============================================================================

@websocket_api.websocket_command(
    {
        vol.Required("type"): "shopping_list_manager/products/substitutes",
        vol.Required("product_id"): str,
        vol.Optional("limit", default=5): int,
    }
)
@callback
def websocket_get_product_substitutes(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle get product substitutes command."""
    storage = get_storage(hass)
    
    try:
        substitutes = storage.find_product_substitutes(
            product_id=msg["product_id"],
            limit=msg.get("limit", 5),
        )
        
        connection.send_result(
            msg["id"],
            {"substitutes": [product.to_dict() for product in substitutes]}
        )
    except Exception as err:
        _LOGGER.error("Error finding substitutes: %s", err)
        connection.send_error(msg["id"], "substitutes_failed", str(err))

@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_PRODUCTS_SEARCH,
        vol.Required("query"): str,
        vol.Optional("limit", default=10): int,
        vol.Optional("exclude_allergens"): [str],
        vol.Optional("include_tags"): [str],
        vol.Optional("substitution_group"): str,
    }
)
@callback
def websocket_search_products(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle search products command with enhanced filters."""
    storage = get_storage(hass)
    
    try:
        results = storage.search_products(
            query=msg["query"],
            limit=msg.get("limit", 10),
            exclude_allergens=msg.get("exclude_allergens"),
            include_tags=msg.get("include_tags"),
            substitution_group=msg.get("substitution_group"),
        )
        
        connection.send_result(
            msg["id"],
            {"products": [product.to_dict() for product in results]}
        )
    except Exception as err:
        _LOGGER.error("Error searching products: %s", err)
        connection.send_error(msg["id"], "search_failed", str(err))
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_PRODUCTS_SUGGESTIONS,
        vol.Optional("limit", default=20): int,
    }
)
@callback
def websocket_get_product_suggestions(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle get product suggestions command."""
    storage = get_storage(hass)
    limit = msg.get("limit", 20)
    
    suggestions = storage.get_product_suggestions(limit)
    
    connection.send_result(
        msg["id"],
        {
            "products": [product.to_dict() for product in suggestions]
        }
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_PRODUCTS_ADD,
        vol.Required("name"): str,
        vol.Required("category_id"): str,
        vol.Optional("aliases"): [str],
        vol.Optional("default_unit", default="units"): str,
        vol.Optional("default_quantity", default=1): vol.Coerce(float),
        vol.Optional("price"): vol.Coerce(float),
        vol.Optional("barcode"): str,
        vol.Optional("image_url"): str,
    }
)
@websocket_api.async_response
async def websocket_add_product(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle add product command."""
    storage = get_storage(hass)
    
    # Build product data
    product_data = {
        "name": msg["name"],
        "category_id": msg["category_id"],
        "default_unit": msg.get("default_unit", "units"),
        "default_quantity": msg.get("default_quantity", 1),
        "custom": True,
        "source": "user"
    }
    
    # Optional fields
    optional_fields = ["aliases", "price", "barcode", "image_url"]
    for field in optional_fields:
        if field in msg:
            product_data[field] = msg[field]
    
    new_product = await storage.add_product(**product_data)
    
    connection.send_result(
        msg["id"],
        {"product": new_product.to_dict()}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_PRODUCTS_UPDATE,
        vol.Required("product_id"): str,
        vol.Optional("name"): str,
        vol.Optional("category_id"): str,
        vol.Optional("price"): vol.Coerce(float),
        vol.Optional("default_unit"): str,
        vol.Optional("default_quantity"): vol.Coerce(float),
        vol.Optional("aliases"): [str],
        vol.Optional("image_url"): str,
    }
)
@websocket_api.async_response
async def websocket_update_product(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle update product command."""
    storage = get_storage(hass)
    product_id = msg["product_id"]
    
    # Build update data
    update_data = {}
    update_fields = ["name", "category_id", "price", "default_unit", "default_quantity", "aliases", "image_url"]
    for field in update_fields:
        if field in msg:
            update_data[field] = msg[field]
    
    # Add price_updated timestamp if price changed
    if "price" in update_data:
        from ..models import current_timestamp
        update_data["price_updated"] = current_timestamp()
    
    updated_product = await storage.update_product(product_id, **update_data)
    
    if updated_product is None:
        connection.send_error(msg["id"], "not_found", "Product not found")
        return
    
    connection.send_result(
        msg["id"],
        {"product": updated_product.to_dict()}
    )


# =============================================================================
# CATEGORY HANDLERS
# =============================================================================

@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_CATEGORIES_GET_ALL,
    }
)
@callback
def websocket_get_categories(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle get all categories command."""
    storage = get_storage(hass)
    categories = storage.get_categories()
    
    connection.send_result(
        msg["id"],
        {
            "categories": [cat.to_dict() for cat in categories]
        }
    )


# =============================================================================
# INTEGRATION SETTINGS HANDLERS
# =============================================================================

@websocket_api.websocket_command(
    {
        vol.Required("type"): "shopping_list_manager/get_integration_settings",
    }
)
@callback
def websocket_get_integration_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Return current country and available country options."""
    country = hass.data[DOMAIN].get("country", "NZ")
    connection.send_result(
        msg["id"],
        {
            "country": country,
            "available_countries": {
                "NZ": "New Zealand",
                "AU": "Australia",
                "US": "United States",
                "GB": "United Kingdom",
                "CA": "Canada",
            },
        }
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "shopping_list_manager/set_country",
        vol.Required("country"): str,
    }
)
@websocket_api.async_response
async def websocket_set_country(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Switch to a different country catalog. Preserves user-added products."""
    country = msg["country"].upper()
    storage = get_storage(hass)

    count = await storage.reload_catalog(country)

    # Persist to HA config entry so country survives restart
    entries = hass.config_entries.async_entries(DOMAIN)
    if entries:
        entry = entries[0]
        hass.config_entries.async_update_entry(entry, options={**entry.options, "country": country})

    hass.data[DOMAIN]["country"] = country

    connection.send_result(
        msg["id"],
        {"success": True, "country": country, "products_loaded": count}
    )


# =============================================================================
# BACKUP / RESTORE HANDLERS
# =============================================================================

@websocket_api.websocket_command(
    {
        vol.Required("type"): "shopping_list_manager/export_data",
    }
)
@websocket_api.async_response
async def websocket_export_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Export all user-created data as a JSON-serialisable dict."""
    storage = get_storage(hass)
    data = await storage.export_user_data()
    connection.send_result(msg["id"], data)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "shopping_list_manager/import_data",
        vol.Required("data"): dict,
    }
)
@websocket_api.async_response
async def websocket_import_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Import user data from a backup payload."""
    storage = get_storage(hass)
    counts = await storage.import_user_data(msg["data"])
    connection.send_result(msg["id"], {"success": True, "imported": counts})


# =============================================================================
# LIST MEMBERS HANDLER
# =============================================================================

@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_LISTS_UPDATE_MEMBERS,
        vol.Required("list_id"): str,
        vol.Required("allowed_users"): [str],
    }
)
@websocket_api.async_response
async def websocket_update_list_members(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Update the allowed_users for a private list."""
    storage = get_storage(hass)
    list_id = msg["list_id"]

    lst = storage.get_list(list_id)
    if lst is None:
        connection.send_error(msg["id"], "not_found", "List not found")
        return

    # Only the owner or an admin may manage members
    user = connection.user
    if lst.owner_id is not None and not (user and (user.is_admin or user.id == lst.owner_id)):
        connection.send_error(msg["id"], "forbidden", "Only the list owner can manage members")
        return

    updated = await storage.update_list_members(list_id, msg["allowed_users"])
    hass.bus.async_fire(
        EVENT_LIST_UPDATED,
        {"list_id": list_id, "action": "members_updated"}
    )
    connection.send_result(msg["id"], {"list": updated.to_dict()})


# =============================================================================
# HA USERS HANDLER
# =============================================================================

@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_USERS_GET_ALL,
    }
)
@websocket_api.async_response
async def websocket_get_ha_users(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Return all active, non-system HA users."""
    users = await hass.auth.async_get_users()
    result = [
        {"id": u.id, "name": u.name}
        for u in users
        if not u.system_generated and u.is_active
    ]
    connection.send_result(msg["id"], {"users": result})


# =============================================================================
# LOYALTY CARD HANDLERS
# =============================================================================

@websocket_api.websocket_command({
    vol.Required("type"): WS_TYPE_LOYALTY_GET_ALL,
})
@websocket_api.async_response
async def websocket_get_loyalty_cards(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Return all loyalty cards visible to the current user."""
    storage = get_storage(hass)
    user = connection.user
    user_id = user.id if user else None
    is_admin = user.is_admin if user else False
    cards = storage.get_loyalty_cards(user_id=user_id, is_admin=is_admin)
    connection.send_result(msg["id"], {"cards": [c.to_dict() for c in cards]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_TYPE_LOYALTY_ADD,
    vol.Required("name"): str,
    vol.Required("number"): str,
    vol.Optional("barcode", default=""): str,
    vol.Optional("logo", default=""): str,
    vol.Optional("notes", default=""): str,
    vol.Optional("color", default="#9fa8da"): str,
    vol.Optional("private", default=True): bool,
})
@websocket_api.async_response
async def websocket_add_loyalty_card(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Add a new loyalty card."""
    storage = get_storage(hass)
    user = connection.user
    owner_id = user.id if (user and msg.get("private")) else None

    card = await storage.create_loyalty_card(
        owner_id=owner_id,
        name=msg["name"],
        number=msg["number"],
        barcode=msg.get("barcode", ""),
        logo=msg.get("logo", ""),
        notes=msg.get("notes", ""),
        color=msg.get("color", "#9fa8da"),
    )
    connection.send_result(msg["id"], {"card": card.to_dict()})


@websocket_api.websocket_command({
    vol.Required("type"): WS_TYPE_LOYALTY_UPDATE,
    vol.Required("card_id"): str,
    vol.Optional("name"): str,
    vol.Optional("number"): str,
    vol.Optional("barcode"): str,
    vol.Optional("logo"): str,
    vol.Optional("notes"): str,
    vol.Optional("color"): str,
})
@websocket_api.async_response
async def websocket_update_loyalty_card(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Update an existing loyalty card."""
    storage = get_storage(hass)
    card_id = msg["card_id"]

    card = storage.get_loyalty_card(card_id)
    if card is None:
        connection.send_error(msg["id"], "not_found", "Loyalty card not found")
        return

    user = connection.user
    if card.owner_id is not None and not (user and (user.is_admin or user.id == card.owner_id)):
        connection.send_error(msg["id"], "forbidden", "Only the card owner can update it")
        return

    fields = {k: v for k, v in msg.items() if k not in ("type", "id", "card_id")}
    updated = await storage.update_loyalty_card(card_id, **fields)
    connection.send_result(msg["id"], {"card": updated.to_dict()})


@websocket_api.websocket_command({
    vol.Required("type"): WS_TYPE_LOYALTY_DELETE,
    vol.Required("card_id"): str,
})
@websocket_api.async_response
async def websocket_delete_loyalty_card(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Delete a loyalty card."""
    storage = get_storage(hass)
    card_id = msg["card_id"]

    card = storage.get_loyalty_card(card_id)
    if card is None:
        connection.send_error(msg["id"], "not_found", "Loyalty card not found")
        return

    user = connection.user
    if card.owner_id is not None and not (user and (user.is_admin or user.id == card.owner_id)):
        connection.send_error(msg["id"], "forbidden", "Only the card owner can delete it")
        return

    await storage.delete_loyalty_card(card_id)
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_TYPE_LOYALTY_UPDATE_MEMBERS,
    vol.Required("card_id"): str,
    vol.Required("allowed_users"): [str],
})
@websocket_api.async_response
async def websocket_update_loyalty_card_members(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Update the allowed_users for a private loyalty card."""
    storage = get_storage(hass)
    card_id = msg["card_id"]

    card = storage.get_loyalty_card(card_id)
    if card is None:
        connection.send_error(msg["id"], "not_found", "Loyalty card not found")
        return

    user = connection.user
    if card.owner_id is not None and not (user and (user.is_admin or user.id == card.owner_id)):
        connection.send_error(msg["id"], "forbidden", "Only the card owner can manage members")
        return

    updated = await storage.update_loyalty_card_members(card_id, msg["allowed_users"])
    connection.send_result(msg["id"], {"card": updated.to_dict()})
