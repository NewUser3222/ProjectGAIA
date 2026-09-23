# Step 46: Define configuration-driven economic resource values

RESOURCE_VALUES = {
    "food": 10.0,
    "water": 8.0,
    "wood": 5.0,
    "stone": 4.0,
    "metal": 12.0,
    "energy": 6.0
}


def get_resource_value(resource_name):
    """Return the configured base economic value for one resource unit."""
    if resource_name not in RESOURCE_VALUES:
        raise ValueError(f"Unknown resource: {resource_name}")
    return RESOURCE_VALUES[resource_name]


def calculate_resource_value(resource_name, quantity):
    """Calculate economic value independently from physical quantity."""
    if quantity < 0:
        raise ValueError("Quantity cannot be negative.")
    return get_resource_value(resource_name) * quantity


def calculate_inventory_value(inventory):
    """Calculate the total configured economic value of an inventory."""
    if inventory is None:
        raise ValueError("Inventory cannot be None.")

    total = 0.0

    for resource_name, quantity in inventory.items():
        if quantity < 0:
            raise ValueError("Inventory quantity cannot be negative.")
        total += calculate_resource_value(resource_name, quantity)

    return total
