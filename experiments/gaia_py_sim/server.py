"""FastAPI bridge over the in-memory civilization world."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import llm_bridge
import observer
import persistence
import world as world_module

# One real second per tick; world.py turns every tick into one simulated minute.
AUTO_TICK_INTERVAL = 1.0

# Spawns walk in from the forest: 10-50 px inside one edge of the 960 px map.
PX = 1.0 / 9.6
SPAWN_EDGE_INNER = 10.0 * PX
SPAWN_EDGE_OUTER = 50.0 * PX
SPAWN_EDGE_NEAR = 910.0 * PX
SPAWN_EDGE_FAR = 950.0 * PX

app = FastAPI(title="GAIA Python Civilization Sim", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_log = logging.getLogger("uvicorn.error")

_snapshot = persistence.load_latest()
if _snapshot:
    try:
        world: world_module.World = world_module.World.load_from_snapshot(_snapshot)
        _log.info("GAIA restored the world from snapshot at tick %s", world.tick_count)
    except Exception:
        _log.warning("GAIA snapshot restore failed; starting a fresh world", exc_info=True)
        world = world_module.new_world()
else:
    world = world_module.new_world()
    _log.info("GAIA starting a fresh world (no stored snapshot)")
_tick_lock = asyncio.Lock()
_next_citizen_index = 0

is_running = False
is_paused = False
_auto_task: asyncio.Task | None = None
_prefetch_task: asyncio.Task | None = None

# Multiplier the auto loop divides its interval by (1x = one tick per second).
current_sim_speed = 1.0


STARVING_PRIORITY_HUNGER = 80
# Hybrid sampler: at most this many staggered citizens are sent to the model
# per batch. Crisis cases are always included on top of this cap.
LLM_BATCH_MAX = 6


def _select_living(count: int | None = None) -> list[world_module.Citizen]:
    """Event override + staggered sample for the model's work queue.

    Hunger > 80 or homelessness always gets an AI decision this batch. Everyone
    else is drawn from villagers whose personal think clock is due and who are
    not already walking, so the model is never asked to think for the whole town
    at once. Citizens left out keep the deterministic fallback brain.
    """

    global _next_citizen_index
    living = [citizen for citizen in world.citizens if citizen.alive]
    if not living:
        return []

    chosen = [
        citizen
        for citizen in living
        if citizen.hunger > STARVING_PRIORITY_HUNGER or world._is_homeless(citizen)
    ]
    taken = {citizen.id for citizen in chosen}
    pool = [
        citizen
        for citizen in living
        if citizen.id in world._active_citizen_ids and citizen.id not in taken
    ]
    limit = LLM_BATCH_MAX if count is None else count
    if pool:
        start = _next_citizen_index % len(pool)
        for offset in range(min(limit, len(pool))):
            chosen.append(pool[(start + offset) % len(pool)])
        _next_citizen_index = start + 1
    return chosen


def _state_payload() -> dict[str, Any]:
    return {
        **world.to_dict(),
        "is_running": is_running,
        "is_paused": is_paused,
        "auto_tick_interval": AUTO_TICK_INTERVAL,
        "sim_speed": current_sim_speed,
    }


async def run_one_tick() -> dict[str, Any]:
    """Ask two living citizens what to do, then advance exactly one tick."""

    global world
    async with _tick_lock:
        chosen = _select_living()
        observations = [citizen.observe(world) for citizen in chosen]
        if world.use_llm:
            decisions = await asyncio.gather(
                *(asyncio.to_thread(llm_bridge.decide, citizen, observation) for citizen, observation in zip(chosen, observations))
            )
        else:
            # PART A (Dev Mode): the deterministic brain answers; no model call.
            decisions = [world._fallback_decision(citizen) for citizen in chosen]
        for citizen, decision in zip(chosen, decisions):
            citizen.pending_action = decision

        result = world.tick()
        return {
            "tick": result["tick"],
            "decisions": [
                {
                    "citizen": citizen.id,
                    "name": citizen.name,
                    "action": decision.get("action", "rest"),
                    "resource": decision.get("resource", "grain"),
                    "reason": decision.get("reason", ""),
                }
                for citizen, decision in zip(chosen, decisions)
            ],
            "events": result["events"],
            "state": result["state"],
        }


async def _prefetch_decisions() -> None:
    """Ask the model for a fresh batch whenever the previous one lands.

    Decisions run on their own clock: a local 7B model needs seconds per reply, and
    blocking the tick loop on it made every speed multiplier meaningless. Batches are
    applied to the citizens' pending_action, which the next tick resolves.
    """

    global _prefetch_task
    if not world.use_llm:
        # PART A (Dev Mode): nothing to prefetch, and no model to keep warm.
        _prefetch_task = None
        return
    while is_running:
        if is_paused:
            await asyncio.sleep(0.5)
            continue
        # At speed the prefetch loop can queue requests faster than a local 7B model
        # answers them; a short breath here keeps Ollama from being hammered.
        if current_sim_speed > 1.0:
            await asyncio.sleep(0.5)
        chosen = _select_living()
        if not chosen:
            await asyncio.sleep(1.0)
            continue
        print(
            f"[LLM] Tick {world.tick_count} | Processing {len(chosen)} AI decisions.",
            flush=True,
        )
        observations = [citizen.observe(world) for citizen in chosen]
        decisions = await asyncio.gather(
            *(asyncio.to_thread(llm_bridge.decide, citizen, observation) for citizen, observation in zip(chosen, observations))
        )
        async with _tick_lock:
            for citizen, decision in zip(chosen, decisions):
                if citizen.alive:
                    citizen.pending_action = decision
    # Exiting: let the next autostart spawn a fresh worker.
    _prefetch_task = None


async def _auto_loop() -> None:
    """Tick on a drift-corrected schedule; processing time counts as elapsed."""

    global _prefetch_task
    loop = asyncio.get_running_loop()
    if _prefetch_task is None or _prefetch_task.done():
        _prefetch_task = asyncio.create_task(_prefetch_decisions())
    while is_running:
        # 1.0 s at 1x, 0.1 s at 10x; read the global each pass so /speed applies now.
        target_interval = AUTO_TICK_INTERVAL / max(current_sim_speed, 0.1)
        started = loop.time()
        if not is_paused:
            async with _tick_lock:
                world.tick()
        # Subtract the tick's own processing time so the clock cannot drift.
        await asyncio.sleep(max(0.0, target_interval - (loop.time() - started)))


async def _stop_auto() -> None:
    global _auto_task, _prefetch_task, is_running, is_paused
    is_running = False
    is_paused = False
    task, _auto_task = _auto_task, None
    prefetch, _prefetch_task = _prefetch_task, None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if prefetch is not None and not prefetch.done():
        prefetch.cancel()
        try:
            await prefetch
        except asyncio.CancelledError:
            pass


@app.get("/state")
def get_state() -> dict[str, Any]:
    """Full world JSON plus the loop's run/pause flags."""

    return _state_payload()


@app.post("/tick")
async def post_tick() -> dict[str, Any]:
    """Legacy single-tick endpoint, kept for run_demo.py."""

    return await run_one_tick()


@app.post("/autostart")
async def post_autostart() -> dict[str, Any]:
    global _auto_task, is_running
    is_running = True
    if _auto_task is None or _auto_task.done():
        _auto_task = asyncio.create_task(_auto_loop())
    return {"running": True, "paused": is_paused}


@app.post("/autostop")
async def post_autostop() -> dict[str, Any]:
    await _stop_auto()
    return {"running": False}


@app.post("/pause")
async def post_pause() -> dict[str, Any]:
    global is_paused
    is_paused = True
    return {"paused": True}


@app.post("/resume")
async def post_resume() -> dict[str, Any]:
    global is_paused
    is_paused = False
    return {"paused": False}


@app.post("/speed")
def post_speed(payload: dict[str, Any] | None = Body(default=None)) -> Any:
    """Set the multiplier applied to the auto-tick interval."""

    global current_sim_speed
    if not isinstance(payload, dict):
        return _bad_request("body must be a JSON object")
    speed = payload.get("speed")
    if isinstance(speed, bool) or not isinstance(speed, (int, float)):
        return _bad_request("speed must be a number")
    if not 0.25 <= float(speed) <= 20.0:
        return _bad_request("speed must be between 0.25 and 20")
    current_sim_speed = float(speed)
    return {"sim_speed": current_sim_speed, "auto_tick_interval": AUTO_TICK_INTERVAL}


@app.post("/step")
async def post_step() -> dict[str, Any]:
    await run_one_tick()
    return {"stepped": True, "tick": world.tick_count}


@app.post("/reset")
async def post_reset() -> dict[str, Any]:
    global world, _next_citizen_index
    await _stop_auto()
    persistence.clear_all()
    world = world_module.new_world()
    _next_citizen_index = 0
    # Seed the durable record with the fresh world so the observer stays truthful.
    persistence.save_citizens([citizen.to_dict() for citizen in world.citizens])
    persistence.save_snapshot(world.tick_count, world.to_dict())
    return _state_payload()


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": message})


def _citizen_or_none(citizen_id: Any) -> world_module.Citizen | None:
    if not isinstance(citizen_id, str):
        return None
    return next((citizen for citizen in world.citizens if citizen.id == citizen_id), None)


def _record(event: dict[str, Any], citizen: world_module.Citizen | None = None) -> None:
    world.history.append(event)
    persistence.save_event(world.tick_count, str(event.get("event", "event")), event.get("id"), event)
    if citizen is not None:
        persistence.save_citizens([citizen.to_dict()])


@app.post("/intervene/give")
def intervene_give(payload: dict[str, Any] | None = Body(default=None)) -> Any:
    """God hand: drop coins/grain/wood into one citizen's pocket."""

    if not isinstance(payload, dict):
        return _bad_request("body must be a JSON object")
    citizen = _citizen_or_none(payload.get("citizen_id"))
    if citizen is None:
        return _bad_request(f"unknown citizen_id {payload.get('citizen_id')!r}")
    resource = payload.get("resource")
    if resource not in ("coins", "grain", "wood"):
        return _bad_request("resource must be one of coins, grain, wood")
    amount = payload.get("amount")
    if not isinstance(amount, int) or isinstance(amount, bool) or not 1 <= amount <= 10000:
        return _bad_request("amount must be an integer between 1 and 10000")

    setattr(citizen, resource, getattr(citizen, resource) + amount)
    event = {
        "event": "gift",
        "id": citizen.id,
        "resource": resource,
        "amount": amount,
        "tick": world.tick_count,
    }
    _record(event, citizen)
    return _state_payload()


def _edge_spawn() -> tuple[float, float]:
    """A random point in the trees along one edge, so newcomers walk into the village."""

    side = world.rng.choice(("west", "east", "north", "south"))
    along = world.rng.uniform(SPAWN_EDGE_INNER, SPAWN_EDGE_FAR)
    if side == "west":
        return world.rng.uniform(SPAWN_EDGE_INNER, SPAWN_EDGE_OUTER), along
    if side == "east":
        return world.rng.uniform(SPAWN_EDGE_NEAR, SPAWN_EDGE_FAR), along
    if side == "north":
        return along, world.rng.uniform(SPAWN_EDGE_INNER, SPAWN_EDGE_OUTER)
    return along, world.rng.uniform(SPAWN_EDGE_NEAR, SPAWN_EDGE_FAR)


@app.post("/intervene/spawn")
def intervene_spawn(payload: dict[str, Any] | None = Body(default=None)) -> Any:
    """God hand: walk a fresh 25-year-old villager in from a random forest edge."""

    if payload is not None and not isinstance(payload, dict):
        return _bad_request("body must be a JSON object")
    payload = payload or {}
    x, y = _edge_spawn()
    if payload.get("x") is not None and payload.get("y") is not None:
        try:
            x = float(payload["x"])
            y = float(payload["y"])
        except (TypeError, ValueError):
            return _bad_request("x and y must be numbers")
        if not (0 <= x <= world_module.WORLD_WIDTH and 0 <= y <= world_module.WORLD_HEIGHT):
            return _bad_request(f"x must be 0-{world_module.WORLD_WIDTH} and y 0-{world_module.WORLD_HEIGHT}")

    numbers = [
        int(citizen.id[1:])
        for citizen in world.citizens
        if citizen.id.startswith("c") and citizen.id[1:].isdigit()
    ]
    citizen = world_module.Citizen(
        id=f"c{max(numbers, default=0) + 1}",
        name=world._child_name(),
        personality=world.rng.choice([seed[2] for seed in world_module.CITIZEN_SEED]),
        grain=world.rng.randint(5, 8),
        wood=world.rng.randint(2, 4),
        coins=world.rng.randint(25, 35),
        hunger=40,
        age=25,
        # A newcomer gets the same short asynchronous head start as a newborn.
        next_think_tick=world.tick_count + world.rng.randint(0, world_module.INITIAL_THINK_MAX),
        x=x,
        y=y,
        walk_speed=world.rng.uniform(world_module.WALK_SPEED_MIN, world_module.WALK_SPEED_MAX),
    )
    world.citizens.append(citizen)
    # A newcomer moves straight into a map house that still has room.
    world._auto_assign_homes()
    _record(
        {"event": "spawned", "id": citizen.id, "name": citizen.name, "tick": world.tick_count},
        citizen,
    )
    return _state_payload()


@app.post("/intervene/kill")
def intervene_kill(payload: dict[str, Any] | None = Body(default=None)) -> Any:
    """God hand: kill a citizen and spill the estate back to market supply."""

    if not isinstance(payload, dict):
        return _bad_request("body must be a JSON object")
    citizen = _citizen_or_none(payload.get("citizen_id"))
    if citizen is None:
        return _bad_request(f"unknown citizen_id {payload.get('citizen_id')!r}")
    if not citizen.alive:
        return _bad_request(f"citizen {citizen.id} is already dead")

    citizen.alive = False
    citizen.pending_action = None
    world.grain_supply += citizen.grain
    world.wood_supply += citizen.wood
    citizen.grain = citizen.wood = citizen.coins = 0
    _record({"event": "killed", "id": citizen.id, "tick": world.tick_count}, citizen)
    return _state_payload()


@app.get("/observer/events")
def get_observer_events(limit: int = 50, since_tick: int | None = None) -> list[dict[str, Any]]:
    """Newest persisted events, read-only."""

    return observer.get_events(limit=limit, since_tick=since_tick)


@app.get("/observer/citizen/{citizen_id}")
def get_observer_citizen(citizen_id: str) -> dict[str, Any]:
    """Birth, death and every stored event naming one citizen."""

    return observer.get_citizen_history(citizen_id)


@app.get("/observer/summary")
def get_observer_summary() -> dict[str, Any]:
    """Lifetime totals and current population."""

    return observer.get_summary()
