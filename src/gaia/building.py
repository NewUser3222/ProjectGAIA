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

        # Step 64: Track an associated business separately from generic entities.
        self.associated_business = None

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

    # Step 64: Building ownership
    def set_owner(self, owner):
        if owner is None:
            self.owner = None
            return

        from src.gaia.agents.citizen import Citizen
        from src.gaia.business import Business

        if not isinstance(owner, (Citizen, Business)):
            raise ValueError("Building owner must be a Citizen or Business.")

        if isinstance(owner, Citizen) and not owner.is_alive():
            raise ValueError("Dead citizens cannot own a building.")

        self.owner = owner

    def has_owner(self):
        return self.owner is not None

    def is_owned_by(self, owner):
        return self.owner is owner

    # Step 64: Building occupancy
    def add_occupant(self, citizen):
        from src.gaia.agents.citizen import Citizen

        if not isinstance(citizen, Citizen):
            raise ValueError("Building occupants must be Citizen objects.")

        if not citizen.is_alive():
            raise ValueError("Dead citizens cannot occupy a building.")

        if not self.is_active():
            raise ValueError("Inactive buildings cannot have active occupants.")

        if citizen not in self.occupants:
            self.occupants.append(citizen)

        return True

    def remove_occupant(self, citizen):
        if citizen in self.occupants:
            self.occupants.remove(citizen)

        return True

    def remove_dead_occupants(self):
        self.occupants = [
            citizen for citizen in self.occupants
            if citizen.is_alive()
        ]

    def has_occupant(self, citizen):
        return citizen in self.occupants

    def get_occupants(self):
        return list(self.occupants)

    # Step 64: Building business association
    def set_associated_business(self, business):
        if business is None:
            self.associated_business = None
            if self.associated_entities:
                self.associated_entities = [
                    entity
                    for entity in self.associated_entities
                    if entity is not self.associated_business
                ]
            return

        from src.gaia.business import Business

        if not isinstance(business, Business):
            raise ValueError(
                "Associated business must be a Business object."
            )

        self.associated_business = business

        if business not in self.associated_entities:
            self.associated_entities.append(business)

    def get_associated_business(self):
        return self.associated_business

    def is_available_for_use(self):
        return self.is_active()

    def can_be_used_by(self, citizen):
        from src.gaia.agents.citizen import Citizen

        return (
            isinstance(citizen, Citizen)
            and citizen.is_alive()
            and self.is_active()
        )
