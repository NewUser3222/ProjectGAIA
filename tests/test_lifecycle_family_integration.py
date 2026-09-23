from src.gaia.agents.citizen import Citizen
from src.gaia.core.simulation import Simulation


def test_newborn_enters_normal_simulation_lifecycle():
    simulation = Simulation()

    parent_a = Citizen("parent-a", "Parent A", age=30)
    parent_b = Citizen("parent-b", "Parent B", age=30)

    simulation.add_citizen(parent_a)
    simulation.add_citizen(parent_b)

    child = simulation.create_child(
        parent_a,
        parent_b,
        "child-1",
        "Child One"
    )

    assert child in simulation.citizens
    assert child in simulation.world.citizens
    assert child.age == 0
    assert child.generation == 1
    assert child.is_alive()

    simulation.start()
    simulation.step()

    assert child.age == 1
    assert child.is_alive()
    assert child.citizen_id in parent_a.get_children()
    assert child.citizen_id in parent_b.get_children()


def test_multigenerational_family_survives_normal_ticks():
    simulation = Simulation()

    grandparent_a = Citizen("gp-a", "Grandparent A", age=60)
    grandparent_b = Citizen("gp-b", "Grandparent B", age=60)
    parent_a = Citizen("parent-a", "Parent A", age=30)
    parent_b = Citizen("parent-b", "Parent B", age=30)

    simulation.add_citizen(grandparent_a)
    simulation.add_citizen(grandparent_b)
    simulation.add_citizen(parent_a)
    simulation.add_citizen(parent_b)

    parent = simulation.create_child(
        grandparent_a,
        grandparent_b,
        "parent-child",
        "Parent Child"
    )

    child = simulation.create_child(
        parent_a,
        parent_b,
        "child",
        "Child"
    )

    simulation.start()
    simulation.step()

    assert parent.age == 1
    assert child.age == 1
    assert parent.generation == 1
    assert child.generation == 1


def test_dead_family_members_remain_historical_but_leave_active_loop():
    simulation = Simulation()

    parent_a = Citizen("parent-a", "Parent A", age=30)
    parent_b = Citizen("parent-b", "Parent B", age=30)

    simulation.add_citizen(parent_a)
    simulation.add_citizen(parent_b)

    child = simulation.create_child(
        parent_a,
        parent_b,
        "child-1",
        "Child One"
    )

    parent_a.die()
    parent_age_at_death = parent_a.age

    simulation.start()
    simulation.step()

    assert parent_a in simulation.citizens
    assert parent_a in simulation.world.citizens
    assert not parent_a.is_alive()
    assert parent_a.age == parent_age_at_death

    assert child.is_alive()
    assert child.age == 1
    assert child.has_parent("parent-a")


def test_birth_and_death_change_active_population_naturally():
    simulation = Simulation()

    parent_a = Citizen("parent-a", "Parent A", age=30)
    parent_b = Citizen("parent-b", "Parent B", age=30)

    simulation.add_citizen(parent_a)
    simulation.add_citizen(parent_b)

    assert len([c for c in simulation.citizens if c.is_alive()]) == 2

    child = simulation.create_child(
        parent_a,
        parent_b,
        "child-1",
        "Child One"
    )

    assert len([c for c in simulation.citizens if c.is_alive()]) == 3

    child.die()

    simulation.start()
    simulation.step()

    active_citizens = [
        citizen for citizen in simulation.citizens
        if citizen.is_alive()
    ]

    assert len(active_citizens) == 2
    assert child in simulation.citizens
    assert child in simulation.world.citizens


def test_existing_decision_loop_processes_living_family_members():
    simulation = Simulation()

    parent_a = Citizen("parent-a", "Parent A", age=30)
    parent_b = Citizen("parent-b", "Parent B", age=30)

    simulation.add_citizen(parent_a)
    simulation.add_citizen(parent_b)

    child = simulation.create_child(
        parent_a,
        parent_b,
        "child-1",
        "Child One"
    )

    simulation.start()
    simulation.step()

    assert simulation.tick == 1
    assert child.age == 1
    assert child.needs is not None
    assert child.has_parent(parent_a.citizen_id)
    assert child.has_parent(parent_b.citizen_id)
