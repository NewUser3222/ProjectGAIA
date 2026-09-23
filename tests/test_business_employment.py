from src.gaia.agents.action import ActionExecutor, ActionOption
from src.gaia.agents.citizen import Citizen
from src.gaia.agents.job import Job
from src.gaia.business import Business


def test_business_employs_citizen_into_business_job():
    owner = Citizen(1, "Owner")
    employee = Citizen(2, "Employee")

    business = Business("biz_001", "Farm", owners=[owner])
    job = Job(
        "job_001",
        "Farmer",
        production={"food": 3},
        wage=10
    )

    business.add_job(job)
    business.employ(employee, job)

    assert business.has_employee(employee)
    assert employee.get_employer() is business
    assert employee.get_job() is job
    assert business.get_employee_job(employee) is job


def test_citizen_cannot_be_employed_by_two_businesses():
    employee = Citizen(1, "Employee")

    first = Business("biz_001", "First")
    second = Business("biz_002", "Second")

    first_job = Job("job_001", "First Job")
    second_job = Job("job_002", "Second Job")

    first.add_job(first_job)
    second.add_job(second_job)

    first.employ(employee, first_job)

    try:
        second.employ(employee, second_job)
        assert False, "Citizen should not hold incompatible business employment."
    except ValueError as error:
        assert str(error) == "Citizen is already employed by another business."


def test_business_work_produces_into_business_inventory():
    employee = Citizen(1, "Employee")
    business = Business("biz_001", "Farm")

    job = Job(
        "job_001",
        "Farmer",
        production={"food": 4},
        wage=10,
        energy_cost=5
    )

    business.add_job(job)
    business.employ(employee, job)
    business.change_money(100)

    action = ActionOption("work", "Work")
    result = ActionExecutor().execute(
        employee,
        action,
        world_context={"tick": 1, "employer": business}
    )

    assert result["success"]
    assert business.get_item_quantity("food") == 4
    assert employee.get_item_quantity("food") == 0
    assert employee.get_money() == 10
    assert business.get_money() == 90


def test_business_work_pays_existing_wage_system():
    employee = Citizen(1, "Employee")
    business = Business("biz_001", "Workshop")

    job = Job(
        "job_001",
        "Worker",
        production={"wood": 2},
        wage=15
    )

    business.add_job(job)
    business.employ(employee, job)
    business.change_money(50)

    result = ActionExecutor().execute(
        employee,
        ActionOption("work", "Work"),
        world_context={"tick": 1, "employer": business}
    )

    assert result["success"]
    assert result["wage"] == 15
    assert employee.get_money() == 15
    assert business.get_money() == 35


def test_business_cannot_employ_dead_citizen():
    employee = Citizen(1, "Employee")
    employee.die()

    business = Business("biz_001", "Business")
    job = Job("job_001", "Worker")
    business.add_job(job)

    try:
        business.employ(employee, job)
        assert False, "Dead citizen should not be employable."
    except ValueError as error:
        assert str(error) == "Citizen is not eligible for this job."


def test_dead_employee_is_removed_from_business():
    employee = Citizen(1, "Employee")
    business = Business("biz_001", "Business")
    job = Job("job_001", "Worker", production={"food": 1})

    business.add_job(job)
    business.employ(employee, job)

    employee.die()
    removed = business.remove_dead_employees()

    assert removed == 1
    assert not business.has_employee(employee)
    assert employee.get_employer() is None
    assert employee.get_job() is None


def test_business_without_enough_money_cannot_complete_paid_work():
    employee = Citizen(1, "Employee")
    business = Business("biz_001", "Business")

    job = Job(
        "job_001",
        "Worker",
        production={"food": 2},
        wage=25
    )

    business.add_job(job)
    business.employ(employee, job)
    business.change_money(10)

    result = ActionExecutor().execute(
        employee,
        ActionOption("work", "Work"),
        world_context={"tick": 1, "employer": business}
    )

    assert not result["success"]
    assert business.get_item_quantity("food") == 0
    assert employee.get_item_quantity("food") == 0
    assert employee.get_money() == 0
    assert business.get_money() == 10


def test_businesses_remain_independent():
    employee_one = Citizen(1, "Employee One")
    employee_two = Citizen(2, "Employee Two")

    first = Business("biz_001", "First")
    second = Business("biz_002", "Second")

    first_job = Job("job_001", "Worker One", production={"food": 3}, wage=5)
    second_job = Job("job_002", "Worker Two", production={"wood": 7}, wage=5)

    first.add_job(first_job)
    second.add_job(second_job)

    first.employ(employee_one, first_job)
    second.employ(employee_two, second_job)

    first.change_money(20)
    second.change_money(50)

    ActionExecutor().execute(
        employee_one,
        ActionOption("work", "Work"),
        world_context={"tick": 1, "employer": first}
    )

    assert first.get_item_quantity("food") == 3
    assert first.get_item_quantity("wood") == 0
    assert second.get_item_quantity("food") == 0
    assert second.get_item_quantity("wood") == 0

    assert first.get_money() == 15
    assert second.get_money() == 50
