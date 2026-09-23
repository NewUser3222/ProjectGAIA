from src.gaia.agents.citizen import Citizen
from src.gaia.environment import EnvironmentState
from src.gaia.core.simulation import Simulation
from src.gaia.vehicle import Vehicle


def test_environment_has_deterministic_initial_state():
    environment = EnvironmentState()

    assert environment.day == 1
    assert environment.season == "spring"
    assert environment.weather == "clear"
    assert environment.temperature == 20.0
    assert environment.precipitation == 0.0
    assert environment.wind_speed == 0.0


def test_environment_progresses_with_time():
    environment = EnvironmentState()

    initial_state = environment.to_dict()
    environment.advance_tick()
    next_state = environment.to_dict()

    assert next_state["day"] == initial_state["day"] + 1
    assert next_state != initial_state


def test_environment_state_persists_in_world_across_ticks():
    simulation = Simulation()

    assert simulation.world.current_tick == 0
    assert simulation.world.environment.day == 1

    simulation.start()
    simulation.step()

    assert simulation.world.current_tick == 1
    assert simulation.world.environment.day == 2
    assert simulation.world.environment.season == "spring"


def test_vehicle_creation_and_registration():
    simulation = Simulation()
    vehicle = Vehicle("VEH-001", "car", location=(10, 10))

    simulation.world.transportation.add_vehicle(vehicle)

    assert simulation.world.transportation.get_vehicle("VEH-001") is vehicle
    assert vehicle in simulation.world.transportation.get_vehicles()


def test_vehicle_ownership():
    simulation = Simulation()
    citizen = Citizen("C-001", "Owner", age=30)
    vehicle = Vehicle("VEH-002", "car")

    simulation.add_citizen(citizen)
    simulation.world.transportation.add_vehicle(vehicle)
    simulation.world.transportation.set_owner(vehicle, citizen)

    assert vehicle.owner is citizen
    assert simulation.world.transportation.can_use_vehicle(citizen, vehicle)


def test_vehicle_movement():
    simulation = Simulation()
    vehicle = Vehicle("VEH-003", "truck", location=(5, 5))

    simulation.world.transportation.add_vehicle(vehicle)

    assert vehicle.move_to((15, 20))
    assert vehicle.location == (15, 20)


def test_citizen_can_travel_with_owned_vehicle():
    simulation = Simulation()
    citizen = Citizen("C-002", "Traveler", age=30, location=(5, 5))
    vehicle = Vehicle("VEH-004", "car", location=(5, 5), owner=citizen)

    simulation.add_citizen(citizen)
    simulation.world.transportation.add_vehicle(vehicle)

    result = simulation.world.transportation.travel(
        citizen,
        vehicle,
        (20, 25)
    )

    assert result["success"]
    assert citizen.location == (20, 25)
    assert vehicle.location == (20, 25)


def test_unowned_vehicle_can_be_used_by_living_citizen():
    simulation = Simulation()
    citizen = Citizen("C-003", "Traveler", age=30, location=(2, 2))
    vehicle = Vehicle("VEH-005", "bus", location=(2, 2))

    simulation.add_citizen(citizen)
    simulation.world.transportation.add_vehicle(vehicle)

    result = simulation.world.transportation.travel(
        citizen,
        vehicle,
        (8, 9)
    )

    assert result["success"]
    assert citizen.location == (8, 9)


def test_dead_citizen_cannot_use_transportation():
    simulation = Simulation()
    citizen = Citizen("C-004", "Former Traveler", age=30, location=(2, 2))
    vehicle = Vehicle("VEH-006", "car", location=(2, 2), owner=citizen)

    simulation.add_citizen(citizen)
    simulation.world.transportation.add_vehicle(vehicle)

    citizen.die()

    result = simulation.world.transportation.travel(
        citizen,
        vehicle,
        (8, 9)
    )

    assert not result["success"]
    assert citizen.location == (2, 2)


def test_transportation_coexists_with_simulation_tick():
    simulation = Simulation()
    citizen = Citizen("C-005", "Citizen", age=30, location=(1, 1))
    vehicle = Vehicle("VEH-007", "truck", location=(1, 1), owner=citizen)

    simulation.add_citizen(citizen)
    simulation.world.transportation.add_vehicle(vehicle)

    simulation.start()
    simulation.step()

    assert simulation.tick == 1
    assert simulation.world.current_tick == 1
    assert simulation.world.environment.day == 2
    assert vehicle in simulation.world.transportation.get_vehicles()
    assert vehicle.owner is citizen
    assert citizen.is_alive()


def test_multiple_citizens_and_vehicles_remain_independent():
    simulation = Simulation()

    citizens = [
        Citizen("C-101", "One", age=30, location=(1, 1)),
        Citizen("C-102", "Two", age=30, location=(2, 2)),
        Citizen("C-103", "Three", age=30, location=(3, 3)),
    ]

    vehicles = [
        Vehicle("VEH-101", "car", location=(1, 1), owner=citizens[0]),
        Vehicle("VEH-102", "truck", location=(2, 2), owner=citizens[1]),
        Vehicle("VEH-103", "bus", location=(3, 3)),
    ]

    for citizen in citizens:
        simulation.add_citizen(citizen)

    for vehicle in vehicles:
        simulation.world.transportation.add_vehicle(vehicle)

    simulation.world.transportation.travel(
        citizens[0], vehicles[0], (10, 10)
    )
    simulation.world.transportation.travel(
        citizens[1], vehicles[1], (20, 20)
    )
    simulation.world.transportation.travel(
        citizens[2], vehicles[2], (30, 30)
    )

    assert citizens[0].location == (10, 10)
    assert citizens[1].location == (20, 20)
    assert citizens[2].location == (30, 30)

    assert len(simulation.world.transportation.get_vehicles()) == 3
