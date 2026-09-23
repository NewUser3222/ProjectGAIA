from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.business import Business


def test_business_creation_and_identity():
    business = Business("biz_001", "GAIA Foods")

    assert business.business_id == "biz_001"
    assert business.name == "GAIA Foods"
    assert business.is_active()
    assert business.get_money() == 0.0
    assert business.inventory == {}
    assert business.get_employees() == []


def test_business_has_independent_money_and_inventory():
    first = Business("biz_001", "First Business")
    second = Business("biz_002", "Second Business")

    first.change_money(100)
    first.add_item("food", 5)

    assert first.get_money() == 100
    assert first.get_item_quantity("food") == 5
    assert second.get_money() == 0
    assert second.get_item_quantity("food") == 0


def test_business_ownership():
    owner = Citizen(1, "Owner")
    business = Business("biz_001", "Owned Business")

    business.add_owner(owner)

    assert business.has_owner(owner)
    assert owner in business.owners


def test_business_can_be_created_with_owner():
    owner = Citizen(1, "Owner")
    business = Business("biz_001", "Owned Business", owners=[owner])

    assert business.has_owner(owner)


def test_business_employs_living_citizen():
    employee = Citizen(2, "Employee")
    business = Business("biz_001", "Employer")

    business.add_employee(employee)

    assert business.has_employee(employee)
    assert business.get_employees() == [employee]


def test_dead_citizen_cannot_be_added_as_employee():
    employee = Citizen(2, "Employee")
    employee.die()

    business = Business("biz_001", "Employer")

    try:
        business.add_employee(employee)
        assert False, "Dead citizen should not be employable."
    except ValueError as error:
        assert str(error) == "Dead citizens cannot be employed."


def test_dead_employees_are_removed():
    first = Citizen(1, "First")
    second = Citizen(2, "Second")
    business = Business("biz_001", "Employer")

    business.add_employee(first)
    business.add_employee(second)

    second.die()

    removed = business.remove_dead_employees()

    assert removed == 1
    assert business.has_employee(first)
    assert not business.has_employee(second)


def test_business_can_register_jobs():
    business = Business("biz_001", "Employer")

    job = Job(
        "job_001",
        "Farmer",
        production={"food": 2},
        wage=5
    )

    business.add_job(job)

    assert business.has_job("job_001")
    assert business.get_job("job_001") is job


def test_business_operating_state():
    business = Business("biz_001", "Business")

    business.deactivate()
    assert not business.is_active()

    business.activate()
    assert business.is_active()
