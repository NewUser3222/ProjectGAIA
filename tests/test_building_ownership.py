# Step 64: Building ownership, occupancy, and use tests

import pytest

from src.gaia.agents.citizen import Citizen
from src.gaia.building import Building
from src.gaia.business import Business


def completed_building(building_id="BLD-64"):
    return Building(
        building_id,
        "house",
        (10, 10),
        construction_status="completed",
    )


def test_building_can_have_citizen_owner():
    building = completed_building()
    owner = Citizen(1, "Owner")

    building.set_owner(owner)

    assert building.owner is owner
    assert building.has_owner()
    assert building.is_owned_by(owner)


def test_building_can_have_business_owner():
    building = completed_building()
    business = Business("biz-64", "Workshop")

    building.set_owner(business)

    assert building.owner is business
    assert building.is_owned_by(business)


def test_dead_citizen_cannot_own_building():
    building = completed_building()
    owner = Citizen(2, "Dead Owner")
    owner.die()

    with pytest.raises(ValueError):
        building.set_owner(owner)


def test_completed_building_accepts_living_occupants():
    building = completed_building()
    citizen = Citizen(3, "Resident")

    building.add_occupant(citizen)

    assert building.has_occupant(citizen)
    assert building.get_occupants() == [citizen]


def test_dead_citizen_cannot_be_added_as_occupant():
    building = completed_building()
    citizen = Citizen(4, "Dead Resident")
    citizen.die()

    with pytest.raises(ValueError):
        building.add_occupant(citizen)


def test_dead_occupants_are_removed_from_active_occupancy():
    building = completed_building()
    living = Citizen(5, "Living")
    dead = Citizen(6, "Dead")

    building.add_occupant(living)
    building.add_occupant(dead)
    dead.die()

    building.remove_dead_occupants()

    assert building.get_occupants() == [living]


def test_incomplete_building_cannot_accept_occupants():
    building = Building(
        "BLD-65",
        "house",
        (10, 10),
        construction_status="under_construction",
    )
    citizen = Citizen(7, "Resident")

    with pytest.raises(ValueError):
        building.add_occupant(citizen)


def test_building_can_associate_with_business():
    building = completed_building()
    business = Business("biz-65", "Store")

    building.set_associated_business(business)

    assert building.get_associated_business() is business
    assert business in building.associated_entities


def test_building_use_requires_living_citizen_and_active_building():
    building = completed_building()
    citizen = Citizen(8, "User")

    assert building.is_available_for_use()
    assert building.can_be_used_by(citizen)

    citizen.die()

    assert not building.can_be_used_by(citizen)


def test_multiple_buildings_keep_ownership_and_occupancy_independent():
    first = completed_building("BLD-66")
    second = completed_building("BLD-67")

    first_owner = Citizen(9, "First Owner")
    second_owner = Citizen(10, "Second Owner")

    first.set_owner(first_owner)
    second.set_owner(second_owner)
    first.add_occupant(first_owner)

    assert first.owner is first_owner
    assert second.owner is second_owner
    assert first.get_occupants() == [first_owner]
    assert second.get_occupants() == []
