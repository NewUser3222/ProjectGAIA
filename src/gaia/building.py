# Step 61: Building entity foundation
class Building:
    """Represents an independent physical building in the simulation world."""

    def __init__(
        self,
        building_id,
        building_type,
        location,
        dimensions=None,
        owner=None,
        condition="good",
        construction_status="planned",
    ):
        if not building_id:
            raise ValueError("Building ID cannot be empty.")

        if not building_type:
            raise ValueError("Building type cannot be empty.")

        if location is None:
            raise ValueError("Building location cannot be None.")

        if condition not in {"good", "damaged", "destroyed", "abandoned"}:
            raise ValueError("Invalid building condition.")

        if construction_status not in {
            "planned",
            "under_construction",
            "completed",
            "abandoned",
        }:
            raise ValueError("Invalid construction status.")

        self.building_id = building_id
        self.building_type = building_type
        self.location = location
        self.dimensions = dimensions
        self.owner = owner
        self.condition = condition
        self.construction_status = construction_status

        # Step 61: Track relationships without requiring occupants.
        self.occupants = []
        self.associated_entities = []

    # Step 61: Building identity
    def __repr__(self):
        return (
            f"Building("
            f"building_id={self.building_id!r}, "
            f"building_type={self.building_type!r}, "
            f"location={self.location!r}"
            f")"
        )

    # Step 61: Construction state
    def is_completed(self):
        return self.construction_status == "completed"

    def is_active(self):
        return (
            self.construction_status == "completed"
            and self.condition != "destroyed"
        )
