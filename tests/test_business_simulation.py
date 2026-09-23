from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.business import Business
from src.gaia.core.simulation import Simulation


def test_simulation_can_add_business_to_world():
    simulation = Simulation()
    business = Business("b1", "Bakery")

    simulation.add_business(business)

    assert business in simulation.businesses
    assert business in simulation.world.businesses


def test_simulation_can_remove_business_from_world():
    simulation = Simulation()
    business = Business("b1", "Bakery")

    simulation.add_business(business)
    simulation.remove_business(business)

    assert business not in simulation.businesses
    assert business not in simulation.world.businesses


def test_world_tracks_only_business_objects():
    simulation = Simulation()

    try:
        simulation.add_business("not a business")
        assert False
    except TypeError:
        pass


def test_business_employed_citizen_uses_actual_business_employer():
    simulation = Simulation()

    owner = Citizen("c1", "Owner", age=30)
    worker = Citizen("c2", "Worker", age=25)

    owner.change_money(100)
    business = Business("b1", "Bakery", owners=[owner])
    business.change_money(100)

    job = Job(
        "j1",
        "Baker",
        production={"bread": 1},
        wage=10,
    )

    business.add_job(job)
    business.employ(worker, job)

    simulation.add_citizen(owner)
    simulation.add_citizen(worker)
    simulation.add_business(business)

    simulation.start()
    simulation.step()

    assert worker.get_employer() is business


def test_dead_employee_is_removed_during_simulation_step():
    simulation = Simulation()

    worker = Citizen("c1", "Worker", age=25)
    business = Business("b1", "Bakery")

    job = Job("j1", "Baker", production={"bread": 1})
    business.add_job(job)
    business.employ(worker, job)

    simulation.add_citizen(worker)
    simulation.add_business(business)

    worker.die()

    simulation.start()
    simulation.step()

    assert not business.has_employee(worker)
    assert worker.get_employer() is None
    assert worker.get_job() is None
