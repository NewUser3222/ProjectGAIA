"""In-memory civilization world for the GAIA Python simulation experiment.

Rules implemented exactly as specified for this minimal build:

* Citizens with ``hunger > 40`` eat one grain from their own stores (hunger -40).
  A citizen with no grain simply gains hunger (+2, or +1 under a roof) and starves.
* Market starts at price 10 / supply 100 for grain and wood; prices never go
  below a floor of 1. Supply only moves when a citizen buys or sells.
* Buy: pay the current price, price +1, supply -1, inventory +1.
* Sell: earn the current price, price -1, supply +1, inventory -1.
* Trade: barter directly with another villager (e.g. 2 wood for 1 grain).

The module is intentionally small: plain dataclasses, no persistence, no clock.
"""

from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import llm_bridge
import persistence

_LOGGER = logging.getLogger(__name__)
CONFIG_PATH = Path(__file__).with_name("config.json")


def _load_config() -> dict[str, Any]:
    """Read config.json once; missing or malformed files fall back to defaults."""

    try:
        with CONFIG_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("config root must be a JSON object")
        return data
    except FileNotFoundError:
        _LOGGER.warning("config.json missing at %s; using built-in defaults", CONFIG_PATH)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        _LOGGER.warning("config.json unreadable (%s); using built-in defaults", error)
    return {}


CONFIG = _load_config()
_SIM_CONFIG = CONFIG.get("sim") if isinstance(CONFIG.get("sim"), dict) else {}


def _sim_setting(name: str, default: Any, cast: type = int) -> Any:
    raw = _SIM_CONFIG.get(name, default)
    try:
        return cast(raw)
    except (TypeError, ValueError):
        _LOGGER.warning("sim.%s=%r is invalid; using %r", name, raw, default)
        return default


def _bool_setting(name: str, default: bool) -> bool:
    """Read a boolean sim setting without bool("false") coming back True."""

    raw = _SIM_CONFIG.get(name, default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return default


# PART A (Dev Mode): when this is false the world never waits for the model. The
# deterministic fallback brain takes every decision, so a 20,000-tick refinement
# run is not paced by a local 7B model. Turn it back on for the live handover.
USE_LLM = _bool_setting("use_llm", True)


HUNGER_RISE = 1
EAT_THRESHOLD = 50
AUTO_EAT_THRESHOLD = 30
EAT_RELIEF = 40
MIN_PRICE = 3
MAX_PRICE = 20.0
PRICE_IMPACT = 0.2
# A grain market holding more than 500 units is in surplus, so the price is forced
# down to MIN_PRICE: food must stay affordable when the fields are overflowing.
SURPLUS_SUPPLY = 500
# The central bank issues food stamps from the tax reserve to a penniless, starving
# citizen. Five coins is one bulk meal at MIN_PRICE.
FOOD_STAMP_AMOUNT = 5
# Issue the stamp as soon as hunger crosses 50, not at the starvation cliff.
FOOD_STAMP_HUNGER = 50
# Housing stimulus: the Bank buys one bed for 15 coins, but only while its reserve
# is healthy. Each subsidised citizen is charged, even when they share a new roof.
BANK_HOUSING_COST = 15
BANK_HOUSING_MIN_RESERVE = 50
# A house that takes in orphans keeps a small pantry so the children can eat
# without a living parent carrying grain for them.
ORPHAN_PANTRY_STOCK = 10
# GAIA Assistant watch: anomalies and citizen questions are sampled every this many
# ticks, deduplicated per citizen/kind for GAIA_REPEAT_TICKS, and kept in gaia_log.
# Housing override (Banished / Stellaris): while beds are short, the model is
# not allowed to choose. A homeless adult is put to work on a roof, and births
# stop once the shortage passes this share of the population.
HOUSING_BIRTH_CAP = 0.15
URGENCY_ADULT_MAX_AGE = 60
HOUSING_REPORT_INTERVAL = 10

GAIA_CHECK_INTERVAL = 50
# Placeholder heartbeat: while the LLM is disconnected, GAIA files a nominal
# anomaly every this many ticks so the console pipeline stays visible.
GAIA_NOMINAL_INTERVAL = 200
GAIA_REPEAT_TICKS = 1000
GAIA_LOG_LIMIT = 50
GAIA_WEALTH_COINS = 150
GAIA_HUNGER_ALARM = 80
GAIA_QUERY_HUNGER = 75
GAIA_HOMELESS_TICKS = 500
GAIA_MARKET_POPULATION = 20
START_PRICE = 10
START_SUPPLY = 100

RESOURCES = ("grain", "wood")
ACTIONS = ("buy", "sell", "trade", "gather", "wander", "rest", "build", "socialize")
GATHER_YIELD = 2
# Phase 93: a trip's load scales with the body carrying it. A child carries one, an
# adult twenty-four. With a flat two, a town of children could not feed itself.
# Measured: four, six and ten all ran the town at or below break-even, because a
# villager only gets out to a node about once every 400 ticks and a person eats a
# grain every 40. At ten the fields yielded 4.1 grain/tick against the 5.7 that 229
# people needed, so the shelves emptied, births hit the Malthusian floor and the
# town starved back down to 200. One adult trip now feeds one adult for ~950 ticks.
ADULT_GATHER_YIELD = 24
CHILD_GATHER_YIELD = 1
# Hoarding cap: once a villager holds this much grain they may not farm again until
# they have sold some, so the surplus reaches the shelves instead of piling up.
HOARD_GRAIN_LIMIT = 40
# Grain anomaly guards: an empty market drafts every hungry villager into farming,
# and a market that stays empty is restocked from the village reserves.
EMERGENCY_FARM_SUPPLY = 10
EMERGENCY_FARM_HUNGER = 30
MARKET_RELIEF_TICKS = 10
WANDER_STEP = 2
HISTORY_LIMIT = 200
# A full-state JSON snapshot every tick is the heaviest write in the loop. Five is
# fine for resume accuracy (a restart loses at most five simulated minutes) and it
# makes a 20,000-tick refinement run practical.
SNAPSHOT_INTERVAL = 5
REPEAT_LIMIT = 3
# Inventory rules run survival-first: a starving citizen is never sent to sell
# stock while grain is buyable or gatherable, and selling starts at a buffer of 8.
FORCE_SELL_STOCK = 8
FORCE_SELL_GRAIN = 3
FORCE_SELL_HUNGER = 40
FORCE_BUY_HUNGER = 30
SELL_BATCH = 3
BULK_BUY_AMOUNT = 3

# Economic policy: a living wage, a daily stipend and a floor-price stimulus.
# The wage is earned on a completed market sale, never on a harvest: a villager
# holding a stock of wood has to walk it to the market to turn it into coins.
WAGE = 5
# A harvest pays a token wage so a villager with an empty purse can earn the fare
# for food. The real money is still made on the sale (WAGE above), not the trip.
GATHER_WAGE = 1
# Per-tick spoilage. Every stock loses this fraction of itself each tick, carried
# as a fraction so integer purses still shrink by whole units at the rate their
# size implies: a 100-wood hoard loses a unit per tick, a villager holding three
# grain loses one every ~33 ticks. A flat -0.01 units per tick was rejected: it
# would take ten thousand ticks to rot a hoard away, which changes nothing.
#
# Phase 93: 1% a tick rots a pantry in an hour of sim time (1 tick = 1 minute), so
# no harvest could ever be stored. Measured on a 1,500-tick town: two thirds of the
# grain brought in vanished to spoilage while its people starved beside it. At 0.1%
# a 24-grain harvest keeps for about a sim day, which makes a trip worth taking.
SPOILAGE_PER_TICK = 0.001
# The market shelf rots at the same rate once it holds more than this much of a
# resource, so a flooded market cannot stay flooded forever.
MARKET_SPOILAGE_THRESHOLD = 50
MARKET_SPOILAGE_PER_TICK = 0.001
# A shelf holding twice the spoilage threshold is glutted: a harvest of that
# resource brings back half, so gathering cannot keep flooding the market.
MARKET_GLUT_SUPPLY = 100
# Over-farming guard: past this much market grain, farmers are sent to cut wood.
OVERFARM_SUPPLY = 300
# Phase 93: the line above is now a floor, not the whole rule. The shelf has to hold
# this much grain for every living villager before anyone is sent away from the
# fields. A fixed 300 was written for a 50-person town; at 143 people it fired on
# every farmer in the village at once, grain output stopped dead and 215 starved
# beside a market holding 461 grain.
OVERFARM_PER_CITIZEN = 6
DAILY_STIPEND = 2
STIPEND_INTERVAL = 1440
# Wealth tax: a tenth of every purse, once per simulated day, into the bank.
WEALTH_TAX_RATE = 0.10
TAX_INTERVAL = 1440
# Tax rows are kept in their own log: the 200-event history drops them within a
# tick or two, which left the bank ledger with nothing to show.
TAX_LOG_LIMIT = 200
STIMULUS_AMOUNT = 5
STIMULUS_INTERVAL = 100
STIMULUS_COOLDOWN = 1440
GRAIN_RELIEF_AMOUNT = 20

# Barter: default exchange is 2 of the offered resource for 1 of the wanted one.
TRADE_OFFER_DEFAULT = 2
TRADE_WANT_DEFAULT = 1

# Building layout: the viewer draws 0-100 sim units as 960 px, so one 32 px tile
# is 32 / 9.6 sim units. A new building snaps to those tiles, keeps 80 px of
# breathing room from every other building and never covers a dirt road.
PX_PER_UNIT = 9.6
TILE_PX = 32
BUILD_MIN_DISTANCE = 80.0 / PX_PER_UNIT
# The tiles the viewer paints as dirt: the two crossroads plus the house spurs.
ROAD_COLUMNS = (14, 15)
ROAD_ROWS = (14, 15)
ROAD_SPUR_COLUMNS = (5, 22)
ROAD_SPUR_ROWS = tuple(range(7, 21))

BUILD_COSTS: dict[str, dict[str, int]] = {
    "shelter": {"wood": 5, "coins": 10},
    "granary": {"wood": 10, "coins": 20},
}

# Jobs: the first successful harvest of a resource teaches the trade.
JOB_BY_RESOURCE = {"grain": "Farmer", "wood": "Woodcutter"}

# Homes: every shelter holds five villagers, the builder included.
# PART B: ten to a house. With 10 beds per roof the 160 x 160 map holds the whole
# town without another row of houses for every five villagers.
HOME_CAPACITY = 10

# Market queue: slots sit on a ring around the counter instead of in one line
# west, so a crowd spreads out and never blocks the avenue.
QUEUE_RADIUS = 30.0
MIN_QUEUE_SLOTS = 8
# Each extra villager in line buys this much ring: ten heads need a 15 unit circle.
QUEUE_RADIUS_PER_CITIZEN = 1.5
# A trade counts as arrived inside this radius of the frozen queue slot. It used
# to be 0.75, tighter than the slot spacing, so villagers circled the counter
# forever and never registered as arrived.
TRADE_ARRIVE_RADIUS = 3.0

# Static workplace, present in every world: the Town Hall doubles as Job Center.
WORKPLACE: dict[str, Any] = {
    "id": "b0",
    "type": "workplace",
    "name": "Town Hall / Job Center",
    "x": 34.0,
    "y": 34.0,
    "district_id": 1,
    "owner_id": "",
    "built_tick": 0,
}

# Map houses: the village starts with roofs already standing around the square.
# Nobody has to gather 5 wood and 10 coins just to sleep (and breed) under a roof.
STATIC_HOUSE_SITES: tuple[tuple[str, float, float], ...] = (
    ("b1", 44.0, 44.0),
    ("b2", 56.0, 44.0),
    ("b3", 44.0, 56.0),
    ("b4", 56.0, 56.0),
)


def _static_house(building_id: str, x: float, y: float) -> dict[str, Any]:
    return {
        "id": building_id,
        "type": "shelter",
        "name": "Village House",
        "x": x,
        "y": y,
        "district_id": 1,
        "owner_id": "",
        "built_tick": 0,
    }


STATIC_HOUSES = tuple(_static_house(building_id, x, y) for building_id, x, y in STATIC_HOUSE_SITES)

# Spatial grid (no obstacles yet): the map starts as one square village block and
# grows outward when the town runs out of beds.
# PART B: structured tile expansion. The settlement is a row of 100 x 100 tiles and
# grows east only, so the map's width is the number of tiles times TILE_WIDTH.
TILE_WIDTH = 100.0
TILE_HEIGHT = 100.0
# Each tile is zoned for this many roofs: 25 houses x 10 beds = 250 people.
HOUSES_PER_TILE = 25
# PART B: the population a tile is planned for. A new tile is added when the town
# reaches this many people, well before the 250 beds are gone, so the market, fields
# and walking room arrive before the density does. At 500 people the map is three
# tiles (300 x 100), which is exactly the handover target.
TILE_POP_CAPACITY = 200
# Tile 1 is wood-only by design. Open the grain tile as soon as the first
# settlement is viable, otherwise a fresh world has no food source at all.
FIRST_TILE_POP_CAPACITY = 10
BASE_WORLD_WIDTH = TILE_WIDTH
BASE_WORLD_HEIGHT = TILE_HEIGHT
WORLD_WIDTH = BASE_WORLD_WIDTH
WORLD_HEIGHT = BASE_WORLD_HEIGHT
# Organic expansion: each step adds this many units on both axes, and the town has
# to live in the new land for 500 ticks before the next step.
MAP_EXPANSION_STEP = 30.0
MAP_EXPANSION_COOLDOWN = 500
# PART A: land grows only for a town that is large (over 100 people) and short of
# counters (fewer than three). The old "population within five of every bed"
# trigger fired while the village was still tiny, because four starting houses are
# 20 beds and six founders fill them almost at once, so empty land and markets
# multiplied for a town of a few dozen people.
MAP_EXPANSION_MIN_POPULATION = 100
MAP_EXPANSION_MARKET_LIMIT = 3
# Stability guard: no second step inside one 500-tick cooldown and at most three
# steps per run, so a town that never opens a fourth counter cannot grow forever.
MAP_EXPANSION_MIN_INTERVAL = 500
MAP_EXPANSION_MAX_EXPANSIONS = 3
# PART A: hard footprint ceiling. Once the town is this wide the map stops growing,
# whatever the population does, so a long run can never fill the screen with land.
MAX_WORLD_WIDTH = TILE_WIDTH * 10.0
MAX_WORLD_HEIGHT = TILE_HEIGHT
MAP_EXPANSION_MAX_SIZE = MAX_WORLD_WIDTH
# Kept for snapshots that still record the old bed-margin rule.
MAP_EXPANSION_BED_MARGIN = 5
# Fresh fields planted in the new land on each step: wood north, grain south.
MAP_EXPANSION_NODES = 3
# The cobbled square sits in the middle of the map; it is the only market.
MARKET_X = 50.0
MARKET_Y = WORLD_HEIGHT / 2.0
DISTRICT_1_CENTER = (MARKET_X, MARKET_Y)

# Asynchronous movement. Lockstep ticks made every villager leave for the fields
# on the same tick and stand on the same pixels; decisions now fire on their own
# schedule and nobody stands exactly where the node or the queue slot is.
# Think clock: after acting, a villager waits 10-30 ticks before the next decision
# resolves, so the town never sets off as one block.
NEXT_THINK_MIN = 10
NEXT_THINK_MAX = 30
# A fresh citizen starts with a 0-20 tick head start instead of acting on tick 1.
INITIAL_THINK_MAX = 20
# Hunger emergencies use a jittered threshold so a hungry cohort scatters its
# reactions over several ticks instead of rushing the market together.
HUNGER_TRIGGER_JITTER = 5
# Hybrid sampler: a crisis (hunger above this, or homelessness) bypasses the
# think clock so the model gets a chance to react to it immediately.
LLM_CRISIS_HUNGER = 80
GATHER_SPREAD = 8.0
# Queue jitter is drawn once, when a villager joins the line, and never re-rolled:
# a slot that moves every tick is a target nobody can reach.
QUEUE_JITTER = 10.0
# PART C: the queue is concentric rings, not one crowded hoop. 48 units is the
# widest apron that still keeps a counter's line on the map.
MAX_QUEUE_RADIUS = 48.0
QUEUE_RING_GAP = 12.0
QUEUE_SLOT_SPACING = 10.0
# Personal space: villagers closer than this push each other apart before walking.
# PART C: boids separation. Neighbours are found through a spatial hash of
# (int(x/10), int(y/10)) buckets, so a 500-person town checks nine buckets instead
# of 500 bodies per villager. Anyone inside SEPARATION_DISTANCE is pushed apart,
# weighted by (1 - distance / SEPARATION_DISTANCE) so the closest pairs push hardest.
SEPARATION_DISTANCE = 5.0
SEPARATION_PUSH = 2.0
SEPARATION_RADIUS = SEPARATION_DISTANCE
# A local crowd of more than MAX_CLUMP within CLUMP_RADIUS gets an extra repulsion
# away from its own centroid until the density drops below the threshold.
MAX_CLUMP = 10
CLUMP_RADIUS = 10.0
CLUMP_PUSH = 3.0
# Bucket size: 10 units, which makes the CLUMP_RADIUS neighbourhood exactly the 9
# adjacent buckets the separation pass queries.
SPATIAL_CELL = 10.0
# Destination jitter: gather and market targets are offset by +/- this many units so
# a hundred villagers never path to the exact same pixel.
DESTINATION_JITTER = 10.0
# Node load balancing: each villager already standing at a node makes it this many
# units less attractive to the next one.
NODE_OCCUPANCY_PENALTY = 6.0
# Housing plan: village roofs stand in one of the four quadrants around the market
# and never crowd the square itself.
HOUSE_MARKET_CLEARANCE = 15.0
HOUSE_QUADRANT_AXIS_CLEARANCE = 5.0
# "In the market district" for the trade rules: close enough to the counter.
MARKET_DISTRICT_RADIUS = 12.0
# Market milestones: (population, x, y). The town opens another counter each time
# it crosses a population step, one per corner of the original square map. Ids are
# handed out in opening order, because zoning can open a counter before a milestone.
MARKET_FOUNDINGS: tuple[tuple[int, float, float], ...] = (
    (30, 20.0, 80.0),
    (65, 80.0, 20.0),
    (95, 80.0, 80.0),
)
# Once the square is full, new roofs gather within this radius of the newest counter.
MARKET_NEIGHBORHOOD_RADIUS = 20.0
# Market zoning: a house may only stand within this radius of the counter it is
# zoned to, and no counter carries more than MAX_HOUSES_PER_MARKET roofs.
MARKET_ZONE_RADIUS = 35.0
# PART B: one counter owns a whole tile's worth of plots (25 roofs = 250 beds).
MAX_HOUSES_PER_MARKET = HOUSES_PER_TILE
# PART A/B: a roof's whole 3 x 3 footprint must sit on grass, and no more than
# two roofs may crowd the clear ring around a counter.
MAX_HOUSES_NEAR_MARKET = 2
MARKET_CLEAR_RADIUS = 15.0
# PART D: the newest tile gets this many roofs before the rest of the map builds.
FRONTIER_HOUSES_REQUIRED = 8
# PART B: a second counter needs a town of 30 and a first counter that has run out
# of zoning room, not just a population milestone.
MARKET_MIN_POPULATION = 30
# PART C: a hard ceiling on counters. Five is the dense-city layout; a sixth would
# only add roofs the town cannot fill and another block to draw every frame.
MARKET_HARD_CAP = 5
# The four corner counters run out of zoning room long before the land runs out.
# Past this many roofs the town opens a frontier counter, so building never stalls.
FRONTIER_MARKET_HOUSE_TRIGGER = 28
# Strict zoning: no roof inside this radius of the square, and every builder starts
# in their own corner of the map.
CENTER_BUILD_CLEARANCE = 15.0

# The map is 100 x 100 units at 9.6 px/unit and 32 px tiles: 30 tiles each way.
GRID_TILES_X = max(1, round(WORLD_WIDTH * PX_PER_UNIT / TILE_PX))
GRID_TILES_Y = max(1, round(WORLD_HEIGHT * PX_PER_UNIT / TILE_PX))
GRID_TILES = GRID_TILES_X


def _dirt_road_tiles() -> set[tuple[int, int]]:
    """Every tile the viewer paints as a road, so no building is raised on one."""

    tiles: set[tuple[int, int]] = set()
    for column in ROAD_COLUMNS:
        for row in range(GRID_TILES_Y):
            tiles.add((column, row))
    for row in ROAD_ROWS:
        for column in range(GRID_TILES_X):
            tiles.add((column, row))
    for column in ROAD_SPUR_COLUMNS:
        for row in ROAD_SPUR_ROWS:
            tiles.add((column, row))
    return tiles


DIRT_ROAD_TILES = _dirt_road_tiles()


def _in_housing_quadrant(x: float, y: float) -> bool:
    """Village houses stand in one of the four corners around the market.

    Ground inside HOUSE_MARKET_CLEARANCE of the square is plaza and market apron,
    and a spot hugging either avenue would sit in its tracks, so both coordinates
    must clear the centre lines as well.
    """

    dx = x - MARKET_X
    dy = y - MARKET_Y
    if math.hypot(dx, dy) < HOUSE_MARKET_CLEARANCE:
        return False
    return abs(dx) >= HOUSE_QUADRANT_AXIS_CLEARANCE and abs(dy) >= HOUSE_QUADRANT_AXIS_CLEARANCE


def _quadrant_of(x: float, y: float) -> int:
    """Which corner of the square a point belongs to: NE, SE, SW, NW as 0-3."""

    east = x >= MARKET_X
    south = y >= MARKET_Y
    if east:
        return 1 if south else 0
    return 2 if south else 3


def tile_of_x(value: float) -> int:
    """The viewer tile column for a 0-200 sim coordinate (60 tiles of 32 px)."""

    return max(0, min(GRID_TILES_X - 1, int(value * PX_PER_UNIT // TILE_PX)))


def tile_of_y(value: float) -> int:
    """The viewer tile row for a 0-100 sim coordinate (30 tiles of 32 px)."""

    return max(0, min(GRID_TILES_Y - 1, int(value * PX_PER_UNIT // TILE_PX)))


def tile_center_unit(gx: int, gy: int) -> tuple[float, float]:
    """The sim-unit centre of a viewer tile: the only place a building may stand."""

    return (
        (gx * TILE_PX + TILE_PX / 2.0) / PX_PER_UNIT,
        (gy * TILE_PX + TILE_PX / 2.0) / PX_PER_UNIT,
    )


GATHER_RADIUS = _sim_setting("gather_radius", 5)
MOVE_SPEED = _sim_setting("move_speed", 4)
# Pedestrians walk at a believable individual pace (sim units per tick), never
# faster than this hard ceiling. A tick is one simulated minute, so 1 unit/tick
# reads as a normal walk instead of a slide across the map.
WALK_SPEED_MIN = 0.8
WALK_SPEED_MAX = 1.4
MAX_SPEED = 5.0
# A citizen counts as "there" once this close to target_x/target_y; trades fire here.
ARRIVE_RADIUS = 5.0
# The viewer draws the 0-100 sim grid as 960 px, so 20 px is just over two sim
# units. Market and socialise targets are jittered by this much so villagers ring
# the square instead of piling onto a single pixel.
TARGET_JITTER = 20.0 / 9.6

# Calendar: one tick is one simulated minute, starting Monday, Spring, Year 1.
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
# Explicit season boundaries: 91 + 91 + 91 + 92 days = 365.
SEASON_LENGTHS = (("Spring", 91), ("Summer", 91), ("Fall", 91), ("Winter", 92))
TICKS_PER_DAY = 1440
TICKS_PER_YEAR = 525600


def season_for_day(day_of_year: int) -> str:
    """Which season a 0-based day of the year (0-364) falls in."""

    remaining = day_of_year % 365
    for name, length in SEASON_LENGTHS:
        if remaining < length:
            return name
        remaining -= length
    return SEASON_LENGTHS[-1][0]
NODE_AMOUNT = 50
# Phase 93: twelve grain fields, not eight. A node regrows NODE_REGROWTH_AMOUNT every
# NODE_REGROWTH_INTERVAL ticks, so eight fields are a hard 8-grain/tick ceiling on the
# whole map. Measured: a town of 314 ate 10 grain/tick, sat exactly on that ceiling and
# starved 87 people every 500 ticks however much each trip carried. Twelve fields feed
# roughly 370 mouths at the same eating rate, which leaves the reserve a real margin.
GRAIN_NODE_COUNT = 12
WOOD_NODE_COUNT = 4
# Tile specialisation: the west tile is woodland, the east tile is farmland.
# A fresh world starts with only the west tile open, so 32 wood and no grain.
TILE_NODE_COUNT = 32
SPECIALIZED_TILE_NODES: dict[int, tuple[str, int]] = {
    1: ("wood", TILE_NODE_COUNT),
    2: ("grain", TILE_NODE_COUNT),
}
NODE_MIN_DISTANCE = 8
# Fields regrow. Without this the map's 400 grain were eaten in a few hundred
# ticks and every village starved out however well it farmed.
NODE_REGROWTH_INTERVAL = 10
NODE_REGROWTH_AMOUNT = 10

# Lifecycle rules
START_AGE_MIN = 20
START_AGE_MAX = 40
DEATH_AGE = 80.0
# PoC aging scale: one sim year = 60 ticks. A child reaches 16 in 960 ticks,
# so a second generation breeds inside a 20,000-tick run instead of long after it.
AGE_PER_TICK = 1.0 / 60
ADULT_MIN_AGE = 16
ADULT_MAX_AGE = 45
# Children stay close to a parent. Beyond this distance they follow; inside it
# they play within KID_PLAY_RADIUS of where they are standing.
KID_FOLLOW_DISTANCE = 7.0
KID_PLAY_RADIUS = 6.0
# Birth blockers are biological only: hunger, a roof, a free bed and the calendar.
# There is no per-couple child cap any more; a couple keeps having children for as
# long as both parents are 18-45, fed and housed.
BIRTH_HUNGER_LIMIT = 60
# Phase 93: three sim months between births. One sim year is now 60 ticks, so 90
# is a quarter year. At 30 the couples out-bred their workforce: a measured run
# reached 213 children against 19 adults, and the adults starved feeding them.
BIRTH_COOLDOWN_TICKS = 90
# Phase 93 Malthusian limits: no child is conceived on an empty market, and none
# while a fifth of the town is already past the eating threshold with nothing left.
BIRTH_MIN_MARKET_GRAIN = 20
BIRTH_FAMINE_HUNGER = 60
BIRTH_FAMINE_SHARE = 0.2
# Phase 93: grain the town must hold per living villager (shelves and purses) before
# another child is conceived. The shelf alone was the wrong signal: at tick 3,000 the
# market held 722 grain while 117 of 331 villagers had none, so births kept coming at
# 250 per 500 ticks, the town overshot to 452 and starved back down to 332.
BIRTH_RESERVE_PER_HEAD = 4.0
BIRTH_CHANCE = 0.10
# Baby boom: below six villagers the birth chance doubles, and a near-extinct
# village (< 4) keeps the older emergency rate of 40%.
LOW_POP_THRESHOLD = 6
LOW_POP_BIRTH_CHANCE = 0.20
CRITICAL_POP_THRESHOLD = 4
CRITICAL_BIRTH_CHANCE = 0.40
MAX_LIVING = _sim_setting("max_living", 500)
BIRTH_NAMES = ("Ada", "Bran", "Cora", "Dev", "Eli", "Fay", "Gus", "Hana", "Ivo", "Jae", "Kai", "Lena")

# (id, name, personality, hunger); starting inventory and age are rolled per world.
CITIZEN_SEED: tuple[tuple[str, str, str, int], ...] = (
    ("c1", "Mira", "Careful grain farmer who hoards food for winter.", 70),
    ("c2", "Rowan", "Opportunistic trader who buys low and sells high.", 45),
    ("c3", "Elowen", "Woodcutter who distrusts markets and prefers to build.", 80),
    ("c4", "Tomas", "Anxious baker who panics when prices rise.", 55),
    ("c5", "Sana", "Patient elder who eats little and saves coins.", 62),
    ("c6", "Bram", "Restless youth who spends coins as fast as he earns them.", 30),
)


@dataclass
class Citizen:
    """One villager with a small inventory, purse and hunger level."""

    id: str
    name: str
    personality: str
    grain: int = 0
    wood: int = 0
    coins: int = 0
    hunger: int = 0
    age: float = 0.0
    alive: bool = True
    parent_ids: list[str] = field(default_factory=list)
    # "unemployed" until the first harvest; homes are shelter building ids.
    job: str = "unemployed"
    home_id: str | None = None
    # A child whose last parent died is placed in a house with a shared pantry.
    orphaned: bool = False
    # Monogamy: one partner at a time, and a 100-tick cooldown between births.
    partner_id: str | None = None
    last_birth_tick: int = 0
    x: float = 0.0
    y: float = 0.0
    # Individual walking pace in sim units per tick. The body, not the action,
    # owns this so a crowd never moves at one shared speed.
    walk_speed: float = 1.0
    # Where the current action must be performed; a cleared target is where they stand.
    target_x: float | None = None
    target_y: float | None = None
    # The decision that is waiting for this citizen to arrive at target_x/target_y.
    travel_action: dict[str, Any] | None = field(default=None, repr=False)
    # Granary prefix for a storage mechanic that has no consumers yet.
    storage_bonus: int = 0
    # Streak tracking so a model that repeats one action gets nudged into variety.
    last_action: str = ""
    # Kept after the walk ends so the detail card can still show why they last acted.
    last_reason: str = "None"
    same_action_count: int = 0
    # Set by the server between deciding and ticking; always one action per tick.
    pending_action: dict[str, Any] | None = field(default=None, repr=False)
    # Market line: the slot index and the exact standing spot are assigned once,
    # when the villager joins, and never recomputed while they wait. The market
    # they joined is frozen too, so their spot stays at their own block's counter.
    queue_slot_index: int | None = None
    queue_x: float | None = None
    queue_y: float | None = None
    # The counter this trip belongs to, frozen with the slot so the walk and the
    # sale agree even when a new market opens while the villager is on the road.
    market_id: int | None = None
    # The tick this villager may act on again: the think clock that desynchronises
    # the village so nobody walks in lockstep.
    next_think_tick: int = 0
    # Fractional spoilage owed per resource; a whole unit is removed at 1.0.
    decay_carry: dict[str, float] = field(default_factory=lambda: {"grain": 0.0, "wood": 0.0})

    def __post_init__(self) -> None:
        # "No destination" and "already there" are the same thing.
        if self.target_x is None:
            self.target_x = self.x
        if self.target_y is None:
            self.target_y = self.y

    def to_dict(self) -> dict[str, Any]:
        # The decision in flight (walking or queued) is the current action; fall
        # back to the last completed kind so an idle citizen still reads sensibly.
        active = self.travel_action or self.pending_action or {}
        return {
            "id": self.id,
            "name": self.name,
            "personality": self.personality,
            "grain": self.grain,
            "wood": self.wood,
            "coins": self.coins,
            "hunger": self.hunger,
            "age": self.age,
            "alive": self.alive,
            "current_action": str(active.get("action") or self.last_action or "Idle"),
            "current_reason": str(active.get("reason") or self.last_reason or "None"),
            "parent_ids": list(self.parent_ids),
            "job": self.job,
            "home_id": self.home_id,
            "orphaned": self.orphaned,
            "partner_id": self.partner_id,
            "last_birth_tick": self.last_birth_tick,
            "going_home": bool(self.travel_action and self.travel_action.get("action") == "return"),
            "x": self.x,
            "y": self.y,
            "walk_speed": self.walk_speed,
            "target_x": float(self.target_x if self.target_x is not None else self.x),
            "target_y": float(self.target_y if self.target_y is not None else self.y),
            "market_id": self.market_id,
            "storage_bonus": self.storage_bonus,
        }

    def observe(self, world: "World") -> dict[str, Any]:
        """The observation handed to the LLM: own state plus market prices."""

        return {
            # "homeless" drives the shelter line in the model prompt.
            "self": {**self.to_dict(), "homeless": world._is_homeless(self)},
            "market": world.market_dict(),
        }


class World:
    """The whole simulation: six citizens and one shared two-resource market."""

    def __init__(self) -> None:
        self.tick_count = 0
        # Elected every MAYOR_ELECTION_INTERVAL ticks from the living citizens.
        self.mayor_id: str | None = None
        self.rng = random.Random()
        self.history: list[dict[str, Any]] = []
        # PART A: Dev Mode switch. When false, _apply_actions never reads a model
        # decision and calls _fallback_decision instead.
        self.use_llm = USE_LLM
        # PART B: the map is a row of tiles. The first tile is the village square.
        self.tile_width = TILE_WIDTH
        self.tile_height = TILE_HEIGHT
        self.tile_count_x = 1
        self.set_world_size(self.tile_count_x * self.tile_width, self.tile_height)
        self.last_expansion_tick = 0
        # How many tiles have been added this run (kept for old snapshots/harness).
        self.expansion_count = 0
        # PART D: a freshly added tile gets the first roofs before the rest of the
        # map may build again, so growth fills the frontier instead of backfilling.
        self.needs_frontier_build = False
        # PART C: spatial hash rebuilt once per tick, bucketing living citizens by
        # (int(x/10), int(y/10)). Separation and clump checks read only 9 buckets.
        self.spatial_grid: dict[tuple[int, int], list[Citizen]] = {}
        # The Town Hall / Job Center and the village houses are part of the map,
        # not something villagers have to build before they can start a family.
        self.buildings: list[dict[str, Any]] = [
            dict(WORKPLACE),
            *(dict(house) for house in STATIC_HOUSES),
        ]
        # The dirt roads are part of the map too, so no roof is raised on them.
        self.road_tiles: set[tuple[int, int]] = set(DIRT_ROAD_TILES)
        # Citizen ids in market order: index 0 is at the counter, the rest queue behind.
        self.market_queue: list[str] = []
        # Every counter on the map. The square opens the town; each growth step plants
        # another one in the corner of the land it just added, so a villager sells at
        # whichever counter is nearest instead of crossing the whole settlement.
        self.markets: list[dict[str, Any]] = [{"id": 1, "x": MARKET_X, "y": MARKET_Y}]
        # The map's own houses are zoned to the counter they stand beside, so their
        # residents shop there and the roofs count against that market's cap.
        for building in self.buildings:
            if building.get("type") == "shelter" and building.get("market_id") is None:
                building["market_id"] = int(
                    self._nearest_market(float(building["x"]), float(building["y"]))["id"]
                )
        self.citizens: list[Citizen] = [
            Citizen(
                id=cid,
                name=name,
                personality=personality,
                grain=self.rng.randint(5, 8),
                wood=self.rng.randint(2, 4),
                coins=self.rng.randint(25, 35),
                hunger=hunger,
                age=self.rng.randint(START_AGE_MIN, START_AGE_MAX),
                # The founding six start in the village, never out in the empty field.
                x=float(DISTRICT_1_CENTER[0] + self.rng.uniform(-20.0, 20.0)),
                y=float(DISTRICT_1_CENTER[1] + self.rng.uniform(-20.0, 20.0)),
                walk_speed=self.rng.uniform(WALK_SPEED_MIN, WALK_SPEED_MAX),
            )
            for cid, name, personality, hunger in CITIZEN_SEED
        ]
        # Stagger the first decisions so the founding six do not all act on tick 1.
        for citizen in self.citizens:
            citizen.next_think_tick = self.rng.randint(0, INITIAL_THINK_MAX)
        self.resource_nodes: list[dict[str, Any]] = self._spawn_nodes()
        self.grain_price = START_PRICE
        self.grain_supply = START_SUPPLY
        self.wood_price = START_PRICE
        self.wood_supply = START_SUPPLY
        self.last_stimulus_tick = 0
        # Lifetime wealth tax collected, kept even after history entries are trimmed.
        self.taxes_collected = 0
        # Real money: taxes land here and pay for food stamps (see _food_stamps).
        self.central_bank_reserve = 0
        # GAIA Assistant: the anomaly/query log the bottom card renders, the first
        # tick each citizen was seen homeless, and the last tick each note was filed.
        self.gaia_log: list[dict[str, Any]] = []
        # PART A: AI-prefetch hint; decisions are gated by each citizen's own clock.
        self._active_citizen_ids: set[str] = set()
        # Every forced homeless order is counted so the [HOUSING] line can prove
        # the override is firing; _urgency_state keeps the log to one entry per
        # villager per branch instead of one entry per tick.
        self.urgency_overrides = 0
        self._urgency_state: dict[str, str] = {}
        self._gaia_homeless_since: dict[str, int] = {}
        self._gaia_last_note: dict[str, int] = {}
        # Bounded ledger of the most recent tax rows for the bank console.
        self.tax_events: list[dict[str, Any]] = []
        # First tick the grain market hit zero, so relief can fire after ten ticks.
        self.grain_empty_since: int | None = None
        # Central-bank grain buyback: active while the market shelf is nearly empty.
        self.grain_buyback_active = False
        # Per-tick spoilage: fractional units owed per resource (market shelves only;
        # citizens carry their own), plus lifetime loss counters for diagnostics.
        self.market_decay: dict[str, float] = {resource: 0.0 for resource in RESOURCES}
        self.spoiled: dict[str, int] = {resource: 0 for resource in RESOURCES}
        # Everyone moves in on day one, so hunger and births start from a fair footing.
        self._auto_assign_homes()

    # -- state -----------------------------------------------------------------

    def market_dict(self) -> dict[str, int]:
        return {
            "grain_price": self.grain_price,
            "grain_supply": self.grain_supply,
            "wood_price": self.wood_price,
            "wood_supply": self.wood_supply,
        }

    @property
    def population(self) -> int:
        return sum(1 for citizen in self.citizens if citizen.alive)

    def _homeless_count(self) -> int:
        """Adults with no roof at all; children live with a parent, not a bed."""

        return sum(
            1
            for citizen in self.citizens
            if citizen.alive and citizen.age >= ADULT_MIN_AGE and citizen.home_id is None
        )

    def calendar_dict(self) -> dict[str, Any]:
        """Derive the in-world calendar from tick_count: 1 tick = 1 minute."""

        total_mins = self.tick_count
        hour24 = (total_mins // 60) % 24
        minute = total_mins % 60
        total_days = total_mins // TICKS_PER_DAY
        day_of_year = total_days % 365
        suffix = "AM" if hour24 < 12 else "PM"
        return {
            "sim_time": f"{hour24 % 12 or 12:02d}:{minute:02d} {suffix}",
            # Weekdays run continuously across years (365 is not a multiple of 7).
            "sim_day": DAY_NAMES[total_days % 7],
            "sim_season": season_for_day(day_of_year),
            "sim_year": (total_mins // TICKS_PER_YEAR) + 1,
            "sim_day_of_year": day_of_year,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            **self.calendar_dict(),
            "population": self.population,
            "mayor_id": self.mayor_id,
            "last_stimulus_tick": self.last_stimulus_tick,
            "taxes_collected": self.taxes_collected,
            "central_bank_reserve": self.central_bank_reserve,
            "gaia_log": self.gaia_log,
            "tax_events": [dict(entry) for entry in self.tax_events],
            "world_width": self.world_width,
            "world_height": self.world_height,
            "last_expansion_tick": self.last_expansion_tick,
            "grain_buyback_active": self.grain_buyback_active,
            "road_tiles": [[gx, gy] for gx, gy in sorted(self.road_tiles)],
            "market": self.market_dict(),
            "markets": [dict(market) for market in self.markets],
            "history": self.history,
            "resource_nodes": [dict(node) for node in self.resource_nodes],
            "buildings": [self._building_dict(building) for building in self.buildings],
            "citizens": [citizen.to_dict() for citizen in self.citizens],
        }

    # -- rules -----------------------------------------------------------------

    def tick(self) -> dict[str, Any]:
        """Eat, then resolve one pending action per citizen, then advance the clock."""

        tick_number = self.tick_count + 1
        # PART A: no shared decision batch. This set is only a hint for the AI
        # prefetcher: spend its limited replies on villagers whose personal clock
        # is due and who are not already walking somewhere. The decision loop
        # below checks every citizen's own next_think_tick directly.
        self._active_citizen_ids = {
            citizen.id
            for citizen in self.citizens
            if citizen.alive
            and tick_number >= citizen.next_think_tick
            and citizen.travel_action is None
            and self._distance(citizen.x, citizen.y, citizen.target_x, citizen.target_y) <= 2.0
        }
        history_start = len(self.history)
        events: list[dict[str, Any]] = []
        # Food before anything else: an empty market drafts every hungry villager.
        events.extend(self._emergency_farming())
        # Food stamps before survival checks: a penniless citizen must hold coins
        # when the emergency buy below looks at their purse.
        events.extend(self._food_stamps())
        events.extend(self._emergency_survival())
        self._prune_queue()
        self._age_citizens()
        events.extend(self._feed_citizens())
        # A village with no spare beds spills outward instead of stacking on itself.
        events.extend(self._check_map_expansion())
        # PART B: counters now arrive with tiles, one per 100 x 100 block. The old
        # milestone/frontier market algorithm is deliberately not called: it opened
        # counters independently of the land and broke the one-market-per-tile plan.
        # Every tick, not once a day: a stock loses a fraction of itself as it sits.
        self._spoil_resources()
        events.extend(self._resolve_deaths(tick_number))
        # Roofs and partners are automatic: grown villagers are housed first, then
        # single adults with a roof are paired, so births are never blocked on chores.
        events.extend(self._auto_assign_homes(tick_number))
        events.extend(self._auto_partner(tick_number))
        events.extend(self._births(tick_number))
        # Newborns move in with a parent, or into any house still under capacity.
        events.extend(self._auto_assign_homes(tick_number))
        # A full village: the homeless build before they do anything else.
        events.extend(self._auto_build_homes())
        # Nobody stands still and starves just because the model has not spoken yet.
        events.extend(self._idle_work())
        # The hoard cap runs last so it can veto any gather grain decided above.
        events.extend(self._cap_hoarding())
        # Anyone still walking also counts as busy, or passive drift would drag them off course.
        selected_ids = {
            citizen.id
            for citizen in self.citizens
            if citizen.pending_action is not None or citizen.travel_action is not None
        }
        events.extend(self._apply_actions())
        events.extend(self._passive_wander(selected_ids))
        # PART C: a final clump-resolution pass, after every body has moved, so even
        # villagers standing still in a queue or at a crowded house are pushed out
        # of a local crowd above MAX_CLUMP. O(n) through the spatial hash.
        self._resolve_clumps()
        events.extend(self._regrow_nodes(tick_number))
        events.extend(self._economy_policy(tick_number))
        # GAIA's observer runs last so it reads the settled state of the tick.
        events.extend(self._gaia_watch(tick_number))
        # PART A: the first Mayor is elected at tick 10, then the town returns to
        # its normal 2,000-tick cadence. After that, any vacancy (death or a missing
        # id in an older save) is filled on the next tick instead of leaving the
        # town leaderless until the next scheduled election.
        mayor = next(
            (citizen for citizen in self.citizens if citizen.id == self.mayor_id),
            None,
        )
        mayor_alive = bool(mayor and mayor.alive)
        scheduled_election = tick_number == 10 or (
            tick_number > 10 and tick_number % 2000 == 0
        )
        if scheduled_election or (tick_number >= 10 and not mayor_alive):
            events.extend(self._hold_election(tick_number))
        if tick_number % HOUSING_REPORT_INTERVAL == 0:
            print(
                f"[HOUSING] Pop: {self.population} | Beds: {self._total_beds()} | "
                f"Homeless: {self._homeless_count()} | "
                f"Urgency Overrides: {self.urgency_overrides}",
                flush=True,
            )
        self.tick_count = tick_number
        self._persist(tick_number, history_start)
        self._trim_history()
        return {"tick": self.tick_count, "events": events, "state": self.to_dict()}

    def _hold_election(self, tick_number: int) -> list[dict[str, Any]]:
        """The first election is at tick 10, then every 2,000 ticks after that.

        The richest living citizen by coins + grain + wood wins.
        """

        living = [citizen for citizen in self.citizens if citizen.alive]
        if not living:
            return []
        winner = max(living, key=lambda citizen: citizen.coins + citizen.grain + citizen.wood)
        self.mayor_id = winner.id
        event = {
            "event": "election",
            "tick": tick_number,
            "id": winner.id,
            "name": winner.name,
            "message": f"{winner.name} was elected Mayor.",
            "value": round(winner.coins + winner.grain + winner.wood, 2),
        }
        self.history.append(event)
        return [event]

    def _emergency_farming(self) -> list[dict[str, Any]]:
        """When the market has almost no grain, every hungry villager works the fields.

        Before this, the town ate the market to zero and the gather trip still paid
        one or two grain, so starvation was baked into the supply curve.
        """

        events: list[dict[str, Any]] = []
        if self.grain_supply >= EMERGENCY_FARM_SUPPLY:
            return events
        tick_number = self.tick_count + 1
        for citizen in self.citizens:
            if not citizen.alive or citizen.hunger <= EMERGENCY_FARM_HUNGER:
                continue
            current = citizen.pending_action or {}
            if current.get("emergency") == "farming":
                continue
            citizen.pending_action = {
                "action": "gather",
                "resource": "grain",
                "emergency": "farming",
                "reason": "emergency: market has no grain, farm",
            }
            event = {
                "event": "emergency_farming",
                "id": citizen.id,
                "name": citizen.name,
                "reason": "market grain supply below 10",
                "supply": self.grain_supply,
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)
        return events

    def _emergency_survival(self) -> list[dict[str, Any]]:
        """Buy food for anyone about to starve, whether or not the LLM has replied.

        This runs before actions resolve, so a slow model can no longer freeze a
        citizen into starvation while they hold enough coins for grain.
        """

        events: list[dict[str, Any]] = []
        tick_number = self.tick_count + 1
        for citizen in self.citizens:
            if not citizen.alive:
                continue
            hunger_trigger = LLM_CRISIS_HUNGER + self.rng.randint(
                -HUNGER_TRIGGER_JITTER, HUNGER_TRIGGER_JITTER
            )
            if citizen.hunger > hunger_trigger and citizen.grain == 0 and citizen.coins >= self.grain_price:
                citizen.pending_action = {
                    "action": "buy",
                    "resource": "grain",
                    "emergency": "survival",
                    "reason": "emergency: starving, buy grain",
                }
                event = {
                    "event": "emergency_survival",
                    "id": citizen.id,
                    "name": citizen.name,
                    "action": "buy",
                    "resource": "grain",
                    "tick": tick_number,
                }
                self.history.append(event)
                events.append(event)
        return events

    def _trim_history(self) -> None:
        """Keep only the newest events so a long run cannot grow memory forever."""

        overflow = len(self.history) - HISTORY_LIMIT
        if overflow > 0:
            del self.history[:overflow]

    def _persist(self, tick_number: int, history_start: int) -> None:
        """Mirror this tick into SQLite; a storage failure only logs a warning.

        Snapshots are written for every tick (not just every tenth) so a restart
        resumes at the exact tick and the observer's live summary is accurate;
        the size cost is a few kilobytes per tick.
        """

        try:
            # One transaction per tick: per-row commits cost more than the tick itself.
            persistence.save_tick(
                tick_number,
                [citizen.to_dict() for citizen in self.citizens],
                self.buildings,
                self.history[history_start:],
                self.to_dict() if tick_number % SNAPSHOT_INTERVAL == 0 else None,
            )
        except Exception as error:  # persistence must never break the sim
            _LOGGER.warning("persistence skipped for tick %s: %s", tick_number, error)

    @classmethod
    def load_from_snapshot(cls, snapshot: dict[str, Any]) -> "World":
        """Rebuild a world from a stored /state snapshot (startup only)."""

        world = cls()
        restored: list[Citizen] = []
        for data in snapshot.get("citizens") or []:
            restored.append(
                Citizen(
                    id=str(data.get("id", "")),
                    name=str(data.get("name", "")),
                    personality=str(data.get("personality", "")),
                    grain=int(data.get("grain", 0)),
                    wood=int(data.get("wood", 0)),
                    coins=int(data.get("coins", 0)),
                    hunger=int(data.get("hunger", 0)),
                    age=float(data.get("age", 0)),
                    alive=bool(data.get("alive", True)),
                    parent_ids=[str(parent) for parent in data.get("parent_ids") or []],
                    job=str(data.get("job", "unemployed")),
                    home_id=str(data["home_id"]) if data.get("home_id") else None,
                    orphaned=bool(data.get("orphaned", False)),
                    partner_id=str(data["partner_id"]) if data.get("partner_id") else None,
                    last_birth_tick=int(data.get("last_birth_tick", 0)),
                    x=float(data.get("x", 0.0)),
                    y=float(data.get("y", 0.0)),
                    target_x=float(data.get("target_x", data.get("x", 0.0))),
                    target_y=float(data.get("target_y", data.get("y", 0.0))),
                    market_id=int(data["market_id"]) if data.get("market_id") else None,
                    walk_speed=(
                        float(data["walk_speed"])
                        if data.get("walk_speed") is not None
                        else world.rng.uniform(WALK_SPEED_MIN, WALK_SPEED_MAX)
                    ),
                )
            )
        if restored:
            world.citizens = restored
            # Older snapshots stored children as adult workers with their own
            # home_id. Normalise them on load so the new rules apply before the
            # first tick, even when the sim resumes paused.
            for citizen in world.citizens:
                if not citizen.alive:
                    continue
                if citizen.age < ADULT_MIN_AGE:
                    citizen.job = "Child"
                    # A child normally sleeps under a parent's roof, but an orphan
                    # keeps the house they were moved into when that parent died.
                    has_living_parent = any(
                        other.alive and other.id in citizen.parent_ids
                        for other in world.citizens
                    )
                    if has_living_parent:
                        citizen.home_id = None
                        citizen.orphaned = False
                    else:
                        citizen.orphaned = citizen.orphaned or citizen.home_id is not None
                elif citizen.job == "Child":
                    citizen.job = "unemployed"

        nodes = snapshot.get("resource_nodes")
        if isinstance(nodes, list) and nodes:
            world.resource_nodes = [dict(node) for node in nodes]

        buildings = snapshot.get("buildings")
        world.buildings = [dict(building) for building in buildings] if isinstance(buildings, list) else []
        # Older snapshots predate the static workplace; every map needs one.
        if not any(building.get("type") == "workplace" for building in world.buildings):
            world.buildings.insert(0, dict(WORKPLACE))
        # Snapshots from before the map houses existed still get the static roofs.
        known_ids = {str(building.get("id")) for building in world.buildings}
        for house in STATIC_HOUSES:
            if house["id"] not in known_ids:
                world.buildings.append(dict(house))
        # The building schema carries a district id; every roof now sits in District 1.
        for building in world.buildings:
            building.setdefault("district_id", 1)
        # The map may have grown on an earlier run: restore its size and cooldown.
        world.set_world_size(
            int(snapshot.get("world_width", BASE_WORLD_WIDTH) or BASE_WORLD_WIDTH),
            int(snapshot.get("world_height", BASE_WORLD_HEIGHT) or BASE_WORLD_HEIGHT),
        )
        # PART B: restore the tile count from the stored footprint.
        world.tile_count_x = max(1, int(round(world.world_width / TILE_WIDTH)))
        world.last_expansion_tick = int(snapshot.get("last_expansion_tick", 0) or 0)
        # The counters are part of the map. Old snapshots have none stored, so one is
        # back-filled for every growth step the map has already taken.
        stored_markets = snapshot.get("markets")
        world.markets = [{"id": 1, "x": MARKET_X, "y": MARKET_Y}]
        if isinstance(stored_markets, list) and stored_markets:
            world.markets = [
                {
                    "id": int(market.get("id", index + 1)),
                    "x": float(market["x"]),
                    "y": float(market["y"]),
                }
                for index, market in enumerate(stored_markets)
                if isinstance(market, dict) and "x" in market and "y" in market
            ] or world.markets
        else:
            steps = max(
                0,
                round((world.world_width - BASE_WORLD_WIDTH) / MAP_EXPANSION_STEP),
            )
            for step in range(1, steps + 1):
                offset = MAP_EXPANSION_STEP * (step - 1) + MAP_EXPANSION_STEP / 2.0
                world.markets.append(
                    {
                        "id": len(world.markets) + 1,
                        "x": round(world.world_width - offset, 1),
                        "y": round(world.world_height - offset, 1),
                    }
                )
        # The map's roads live in the snapshot too, so a reload keeps the same ground.
        roads = snapshot.get("road_tiles")
        if isinstance(roads, list) and roads:
            world.road_tiles = {
                (int(tile[0]), int(tile[1]))
                for tile in roads
                if isinstance(tile, (list, tuple)) and len(tile) == 2
            }
        # Older saves have mixed fields everywhere. Enforce the west-wood /
        # east-grain tiles even when resuming a long-running world.
        world._ensure_specialized_nodes()
        world._auto_assign_homes()
        world.market_queue = []
        for citizen in world.citizens:
            citizen.storage_bonus = 5 * sum(
                1
                for building in world.buildings
                if building.get("owner_id") == citizen.id and building.get("type") == "granary"
            )

        market = snapshot.get("market") or {}
        world.grain_price = min(MAX_PRICE, max(MIN_PRICE, float(market.get("grain_price", START_PRICE))))
        world.grain_supply = max(0, int(market.get("grain_supply", START_SUPPLY)))
        world.wood_price = min(MAX_PRICE, max(MIN_PRICE, float(market.get("wood_price", START_PRICE))))
        world.wood_supply = int(market.get("wood_supply", START_SUPPLY))

        world.tick_count = int(snapshot.get("tick", 0))
        # Think clocks are intentionally not persisted: on resume, spread every
        # citizen over the next 0-20 ticks so a loaded save cannot wake in one wave.
        for citizen in world.citizens:
            citizen.next_think_tick = world.tick_count + world.rng.randint(0, INITIAL_THINK_MAX)
        stored_mayor = snapshot.get("mayor_id")
        world.mayor_id = str(stored_mayor) if stored_mayor else None
        world.last_stimulus_tick = int(snapshot.get("last_stimulus_tick", 0) or 0)
        world.taxes_collected = int(snapshot.get("taxes_collected", 0) or 0)
        world.central_bank_reserve = int(snapshot.get("central_bank_reserve", 0) or 0)
        world.gaia_log = [
            dict(entry) for entry in (snapshot.get("gaia_log") or [])[-GAIA_LOG_LIMIT:]
        ]
        stored_taxes = snapshot.get("tax_events")
        world.tax_events = list(stored_taxes)[-TAX_LOG_LIMIT:] if isinstance(stored_taxes, list) else []
        world.grain_empty_since = None
        world.grain_buyback_active = bool(snapshot.get("grain_buyback_active", False))
        history = snapshot.get("history")
        world.history = list(history)[-HISTORY_LIMIT:] if isinstance(history, list) else []
        return world

    def _age_citizens(self) -> None:
        for citizen in self.citizens:
            if not citizen.alive:
                continue
            citizen.age += AGE_PER_TICK
            # Childhood is a status, not a job, and a child has no home of their
            # own: they sleep wherever their parents are. Turning 16 clears the
            # status and lets _auto_assign_homes give them a bed of their own.
            if citizen.age < ADULT_MIN_AGE:
                citizen.job = "Child"
                if not citizen.orphaned:
                    citizen.home_id = None
            elif citizen.job == "Child":
                citizen.job = "unemployed"

    def _resolve_deaths(self, tick_number: int) -> list[dict[str, Any]]:
        """Age and starvation deaths; wealth goes to living children, else to the market."""

        events: list[dict[str, Any]] = []
        for citizen in self.citizens:
            if not citizen.alive:
                continue
            if citizen.age < DEATH_AGE and citizen.hunger < 100:
                continue

            citizen.alive = False
            # Widow / widower: the survivor is free to pair again.
            for survivor in self.citizens:
                if survivor.partner_id == citizen.id:
                    survivor.partner_id = None
            citizen.pending_action = None
            citizen.travel_action = None
            self._leave_queue(citizen)
            citizen.target_x, citizen.target_y = citizen.x, citizen.y
            cause = "age" if citizen.age >= DEATH_AGE else "hunger"
            inheritance = self._inherit(citizen)
            event = {"event": "death", "id": citizen.id, "tick": tick_number, "cause": cause}
            self.history.append(event)
            events.append({**event, "name": citizen.name, "age": citizen.age, "inheritance": inheritance})
            # A child who now has no living parent is moved immediately, before
            # the next tick's child branch can follow a dead id or go hungry.
            events.extend(self._orphan_children(citizen, tick_number))
        return events

    def _inherit(self, deceased: Citizen) -> list[str]:
        """Split the estate equally between living children; childless estates return to supply."""

        children = [child for child in self.citizens if child.alive and deceased.id in child.parent_ids]
        grain, wood, coins = deceased.grain, deceased.wood, deceased.coins
        deceased.grain = deceased.wood = deceased.coins = 0
        if not children:
            self.grain_supply += grain
            self.wood_supply += wood
            return []

        share_grain, grain_left = divmod(grain, len(children))
        share_wood, wood_left = divmod(wood, len(children))
        share_coins, coins_left = divmod(coins, len(children))
        for index, child in enumerate(children):
            child.grain += share_grain + (grain_left if index == 0 else 0)
            child.wood += share_wood + (wood_left if index == 0 else 0)
            child.coins += share_coins + (coins_left if index == 0 else 0)
        return [child.id for child in children]

    def _orphan_children(self, deceased: Citizen, tick_number: int) -> list[dict[str, Any]]:
        """Move newly parentless children into a house with a shared pantry.

        Children ordinarily have no bed of their own, so a dead parent used to leave
        them following nobody with an empty purse. The surviving child is assigned
        to the emptiest shelter with room and any grain they inherited goes into
        that house's pantry; the pantry is topped up from the market if needed.
        """

        events: list[dict[str, Any]] = []
        for child in self.citizens:
            if not child.alive or child.age >= ADULT_MIN_AGE:
                continue
            if deceased.id not in child.parent_ids:
                continue
            has_living_parent = any(
                other.alive and other.id != deceased.id and other.id in child.parent_ids
                for other in self.citizens
            )
            if has_living_parent:
                continue
            shelters = [b for b in self.buildings if b.get("type") == "shelter"]
            open_houses = [
                house
                for house in shelters
                if self._occupancy(str(house["id"])) < HOME_CAPACITY
            ]
            if not open_houses:
                events.append(
                    {
                        "event": "orphan_no_home",
                        "id": child.id,
                        "name": child.name,
                        "tick": tick_number,
                    }
                )
                continue
            house = min(
                open_houses,
                key=lambda entry: self._occupancy(str(entry["id"])),
            )
            house_id = str(house["id"])
            child.orphaned = True
            child.home_id = house_id
            house["grain"] = int(house.get("grain", 0)) + int(child.grain)
            child.grain = 0
            missing = max(0, ORPHAN_PANTRY_STOCK - int(house.get("grain", 0)))
            stocked = min(missing, max(0, int(self.grain_supply)))
            if stocked:
                self.grain_supply -= stocked
                house["grain"] = int(house.get("grain", 0)) + stocked
            event = {
                "event": "orphan_housed",
                "id": child.id,
                "name": child.name,
                "building": house_id,
                "pantry": int(house.get("grain", 0)),
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)
        return events

    def _gaia_note(self, kind: str, message: str, tick_number: int, key: str) -> dict[str, Any] | None:
        """Append one GAIA log entry, unless the same note was just filed.

        The sweep runs every 50 ticks; without the dedupe key a starving rich citizen
        and a homeless citizen would refill the log with the same sentence forever.
        """

        last = self._gaia_last_note.get(key)
        if last is not None and tick_number - last < GAIA_REPEAT_TICKS:
            return None
        self._gaia_last_note[key] = tick_number
        entry = {"type": kind, "message": message, "tick": tick_number}
        self.gaia_log.append(entry)
        del self.gaia_log[:-GAIA_LOG_LIMIT]
        return entry

    def _gaia_question(self, citizen: Citizen, homeless: bool) -> str:
        """Ask a varied question drawn from every problem the citizen currently has."""

        questions: list[str] = []
        if homeless:
            questions.extend(
                (
                    "How do I build a house?",
                    "Where can I find shelter?",
                    "I am tired of sleeping on the grass.",
                )
            )
        if citizen.coins < self.grain_price:
            questions.extend(
                (
                    "How do I earn coins?",
                    "Why is the market empty?",
                    "Where can I find work?",
                )
            )
        if citizen.hunger >= GAIA_QUERY_HUNGER:
            questions.extend(
                (
                    "I am starving, where is the food?",
                    "How do I buy grain?",
                    "Why does no one share their food?",
                )
            )
        if not questions:
            questions.append("I am struggling. What should I do?")
        question = self.rng.choice(questions)
        return (
            f"{question} Hunger {citizen.hunger}/100, "
            f"{int(citizen.coins)} coins, {citizen.grain} grain."
        )

    def _gaia_watch(self, tick_number: int) -> list[dict[str, Any]]:
        """GAIA's observer: anomalies plus one desperation-ranked LLM answer.

        Every GAIA_CHECK_INTERVAL ticks it files:
          * an anomaly when someone holds > 150 coins yet is starving (> 80 hunger);
          * an anomaly when the grain shelf is empty with more than 20 villagers;
          * an anomaly when a citizen has been homeless for more than 500 ticks;
          * at most one dynamic question, answered by Ollama, for the most desperate
            citizen whose query is not on its 1,000-tick cooldown.
        """

        events: list[dict[str, Any]] = []
        if tick_number % GAIA_CHECK_INTERVAL:
            return events

        # PART B: placeholder heartbeat. Filed directly (not through _gaia_note) so
        # the repeat guard cannot swallow the 200-tick beat.
        if tick_number % GAIA_NOMINAL_INTERVAL == 0:
            nominal = {
                "type": "anomaly",
                "message": "GAIA is monitoring. All systems nominal.",
                "tick": tick_number,
            }
            self.gaia_log.append(nominal)
            del self.gaia_log[:-GAIA_LOG_LIMIT]
            events.append(nominal)

        desperate: list[tuple[float, Citizen, bool]] = []
        for citizen in self.citizens:
            if not citizen.alive:
                continue
            homeless = self._is_homeless(citizen)
            if homeless:
                since = self._gaia_homeless_since.setdefault(citizen.id, tick_number)
                if tick_number - since > GAIA_HOMELESS_TICKS:
                    entry = self._gaia_note(
                        "anomaly",
                        f"{citizen.name} has been homeless for {tick_number - since} ticks.",
                        tick_number,
                        f"homeless:{citizen.id}",
                    )
                    if entry:
                        events.append(entry)
            else:
                self._gaia_homeless_since.pop(citizen.id, None)

            if citizen.coins > GAIA_WEALTH_COINS and citizen.hunger > GAIA_HUNGER_ALARM:
                entry = self._gaia_note(
                    "anomaly",
                    f"{citizen.name} is starving but has {int(citizen.coins)} coins.",
                    tick_number,
                    f"wealth:{citizen.id}",
                )
                if entry:
                    events.append(entry)

            broke = citizen.coins < self.grain_price
            starving = citizen.hunger >= GAIA_QUERY_HUNGER
            if starving or broke or homeless:
                query_key = f"query:{citizen.id}"
                last_query = self._gaia_last_note.get(query_key)
                if last_query is None or tick_number - last_query >= GAIA_REPEAT_TICKS:
                    # Hunger dominates; poverty and homelessness break ties.
                    score = citizen.hunger + (50 if starving else 0)
                    score += 25 if broke else 0
                    score += 10 if homeless else 0
                    desperate.append((score, citizen, homeless))

        if self.grain_supply == 0 and self.population > GAIA_MARKET_POPULATION:
            entry = self._gaia_note(
                "anomaly",
                f"Market anomaly: 0 grain on the shelf with {self.population} villagers alive.",
                tick_number,
                "market:grain_empty",
            )
            if entry:
                events.append(entry)

        # One request per watch, regardless of how many citizens are struggling:
        # the local model must never become a per-citizen cost in the tick loop.
        # Dev mode is deterministic end-to-end: asking Ollama here added a 5-second
        # timeout every 50 ticks and made a 20,000-tick harness impractical.
        if desperate and self.use_llm:
            _, asker, asker_homeless = max(desperate, key=lambda item: item[0])
            question = self._gaia_question(asker, asker_homeless)
            answer_text = llm_bridge.ask_gaia(question)
            if answer_text:
                query = self._gaia_note(
                    "query",
                    f"{asker.name} asks: {question}",
                    tick_number,
                    f"query:{asker.id}",
                )
                if query:
                    events.append(query)
                answer = self._gaia_note(
                    "answer",
                    f"GAIA: {answer_text}",
                    tick_number,
                    f"answer:{asker.id}",
                )
                if answer:
                    events.append(answer)
        return events

    def _food_stamps(self) -> list[dict[str, Any]]:
        """The bank turns the tax reserve into a meal for anyone starving with no coin.

        Taxes used to vanish into a counter, while a citizen with 0 coins starved in
        front of a full market. The reserve is now real money and it is spent on food
        stamps: 5 coins, issued when the purse is empty and hunger is past 50.
        """

        events: list[dict[str, Any]] = []
        tick_number = self.tick_count + 1
        for citizen in self.citizens:
            if not citizen.alive or citizen.coins > 0 or citizen.hunger <= FOOD_STAMP_HUNGER:
                continue
            if self.central_bank_reserve < FOOD_STAMP_AMOUNT:
                continue
            self.central_bank_reserve -= FOOD_STAMP_AMOUNT
            citizen.coins += FOOD_STAMP_AMOUNT
            event = {
                "event": "food_stamp",
                "amount": FOOD_STAMP_AMOUNT,
                "id": citizen.id,
                "name": citizen.name,
                "coins": citizen.coins,
                "hunger": citizen.hunger,
                "reserve": self.central_bank_reserve,
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)
        return events

    def _economy_policy(self, tick_number: int) -> list[dict[str, Any]]:
        """Daily stipend, immediate food stamps, and the bank's price stimulus."""

        events: list[dict[str, Any]] = []
        # Keep the policy safe when called directly (and catch a citizen who spent
        # their stamp earlier in this tick): hunger 50, empty purse, five coins.
        events.extend(self._food_stamps())
        # Grain buyback: once the shelf drops below ten, the bank pays double for
        # grain until the market recovers. Log one intervention per crisis.
        if self.grain_supply < 10:
            if not self.grain_buyback_active:
                self.grain_buyback_active = True
                event = {
                    "event": "bank_intervention",
                    "supply": self.grain_supply,
                    "price": self.grain_price,
                    "multiplier": 2,
                    "reason": "grain shelf below 10: buyback active",
                    "tick": tick_number,
                }
                self.history.append(event)
                events.append(event)
        else:
            self.grain_buyback_active = False
        # Spoilage is no longer a daily 20% step: _spoil_resources() runs every tick.
        if tick_number % TAX_INTERVAL == 0:
            for citizen in self.citizens:
                if not citizen.alive or citizen.coins <= 0:
                    continue
                # Never withhold more than the purse actually holds.
                amount = min(int(citizen.coins), int(citizen.coins * WEALTH_TAX_RATE))
                if amount <= 0:
                    continue
                citizen.coins -= amount
                self.taxes_collected += amount
                # Taxes no longer evaporate: they fund the food-stamp reserve.
                self.central_bank_reserve += amount
                event = {
                    "event": "tax",
                    "id": citizen.id,
                    "name": citizen.name,
                    "amount": amount,
                    "rate": WEALTH_TAX_RATE,
                    "coins": citizen.coins,
                    "tick": tick_number,
                }
                self.history.append(event)
                events.append(event)
                self.tax_events.append(event)
                del self.tax_events[:-TAX_LOG_LIMIT]
        if tick_number % STIPEND_INTERVAL == 0:
            for citizen in self.citizens:
                if not citizen.alive:
                    continue
                citizen.coins += DAILY_STIPEND
                event = {
                    "event": "stipend",
                    "id": citizen.id,
                    "name": citizen.name,
                    "amount": DAILY_STIPEND,
                    "coins": citizen.coins,
                    "tick": tick_number,
                }
                self.history.append(event)
                events.append(event)
        # Market relief: ten ticks of an empty grain market triggers a restock, so a
        # sold-out market can never starve the whole town.
        if self.grain_supply <= 0:
            if self.grain_empty_since is None:
                self.grain_empty_since = tick_number
            elif tick_number - self.grain_empty_since > MARKET_RELIEF_TICKS:
                self.grain_supply += GRAIN_RELIEF_AMOUNT
                self.grain_empty_since = None
                event = {
                    "event": "grain_relief",
                    "amount": GRAIN_RELIEF_AMOUNT,
                    "supply": self.grain_supply,
                    "price": self.grain_price,
                    "reason": "market empty for more than 10 ticks",
                    "tick": tick_number,
                }
                self.history.append(event)
                events.append(event)
        else:
            self.grain_empty_since = None
        if self.grain_price >= MAX_PRICE:
            self.grain_supply += GRAIN_RELIEF_AMOUNT
            event = {
                "event": "grain_relief",
                "amount": GRAIN_RELIEF_AMOUNT,
                "supply": self.grain_supply,
                "price": self.grain_price,
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)
        low_population = self.population < 3
        cooldown_ready = tick_number - self.last_stimulus_tick > STIMULUS_COOLDOWN
        if (low_population and cooldown_ready) or (
            tick_number % STIMULUS_INTERVAL == 0
            and self.grain_price <= MIN_PRICE
            and self.wood_price <= MIN_PRICE
        ):
            self.last_stimulus_tick = tick_number
            for citizen in self.citizens:
                if not citizen.alive:
                    continue
                citizen.coins += STIMULUS_AMOUNT
                event = {
                    "event": "stimulus",
                    "id": citizen.id,
                    "name": citizen.name,
                    "amount": STIMULUS_AMOUNT,
                    "coins": citizen.coins,
                    "trigger": "low_population" if low_population else "floor_price",
                    "tick": tick_number,
                }
                self.history.append(event)
                events.append(event)
        return events

    def _births(self, tick_number: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        # PART A (Phase 93): the Malthusian limit. A village that cannot feed the
        # children it already has does not start another one.
        #
        # An empty market stops births outright: below BIRTH_MIN_MARKET_GRAIN there
        # is no surplus to raise a child on. Measured before this rule: 316
        # starvation deaths by tick 3,000 while births ran at full rate, because 213
        # children and 19 adults cannot work the fields that feed 232 mouths.
        if self.grain_supply < BIRTH_MIN_MARKET_GRAIN:
            return events
        # A famine stops them too: past BIRTH_FAMINE_HUNGER a villager has already
        # eaten what they had and is losing ground. If more than a fifth of the town
        # is in that state, the next baby is a mouth, not a worker.
        hungry = sum(
            1 for c in self.citizens if c.alive and c.hunger > BIRTH_FAMINE_HUNGER
        )
        if hungry > self.population * BIRTH_FAMINE_SHARE:
            return events
        # And never without a reserve to raise them on: granaries and purses together
        # must hold BIRTH_RESERVE_PER_HEAD grain for every living villager, so growth
        # stops at the food ceiling instead of overshooting it and starving back.
        reserve = self.grain_supply + sum(c.grain for c in self.citizens if c.alive)
        if reserve < self.population * BIRTH_RESERVE_PER_HEAD:
            return events
        # Stellaris cap, never a free-bed veto: an empty bed means the town breeds,
        # whatever the homeless share is. The cap only bites when the beds are gone.
        beds = self._total_beds()
        homeless = self._homeless_count()
        if (
            beds <= self.population
            and self.population
            and homeless > self.population * HOUSING_BIRTH_CAP
        ):
            return events
        # No spare bed is a housing problem, not a reason to stop having children:
        # grow the map (respecting the expansion cooldown) before births dry up.
        if beds and self.population >= beds:
            events.extend(self._check_map_expansion())
        adults = [c for c in self.citizens if c.alive and ADULT_MIN_AGE <= c.age <= ADULT_MAX_AGE]
        for index, first in enumerate(adults):
            for second in adults[index + 1:]:
                if self.population >= MAX_LIVING:
                    return events
                if first.hunger >= BIRTH_HUNGER_LIMIT or second.hunger >= BIRTH_HUNGER_LIMIT:
                    continue
                # Monogamy: a single pair may bond, existing partners must be each other.
                if first.partner_id not in (None, second.id) or second.partner_id not in (None, first.id):
                    continue
                # A roof first: homeless couples do not start families.
                if first.home_id is None or second.home_id is None:
                    continue
                # A free bed is required: no child is born into a full village.
                if beds and self.population >= beds:
                    continue
                # Nine sim months since the last birth for either parent (both are
                # stamped together, so this is the mother's cooldown in practice).
                if tick_number - max(first.last_birth_tick, second.last_birth_tick) <= BIRTH_COOLDOWN_TICKS:
                    continue
                chance = BIRTH_CHANCE
                if self.population < LOW_POP_THRESHOLD:
                    chance = LOW_POP_BIRTH_CHANCE
                if self.population < CRITICAL_POP_THRESHOLD:
                    chance = CRITICAL_BIRTH_CHANCE
                if self.rng.random() >= chance:
                    continue

                if first.partner_id is None or second.partner_id is None:
                    first.partner_id, second.partner_id = second.id, first.id
                    partnered = {
                        "event": "partnered",
                        "id1": first.id,
                        "id2": second.id,
                        "tick": tick_number,
                    }
                    self.history.append(partnered)
                    events.append(partnered)
                first.last_birth_tick = second.last_birth_tick = tick_number

                # Births are free: charging parents 30 coins depopulated the village.
                child = Citizen(
                    id=f"c{len(self.citizens) + 1}",
                    name=self._child_name(),
                    personality=self.rng.choice((first.personality, second.personality))
                    + f" (child of {first.name} and {second.name})",
                    age=0,
                    grain=0,
                    wood=0,
                    coins=0,
                    hunger=0,
                    job="Child",
                    parent_ids=[first.id, second.id],
                    # A newborn gets its own short head start before its first thought.
                    next_think_tick=tick_number + self.rng.randint(0, INITIAL_THINK_MAX),
                    x=min(WORLD_WIDTH, max(0.0, first.x + self.rng.uniform(-3, 3))),
                    y=min(WORLD_HEIGHT, max(0.0, first.y + self.rng.uniform(-3, 3))),
                    walk_speed=self.rng.uniform(WALK_SPEED_MIN, WALK_SPEED_MAX),
                )
                self.citizens.append(child)
                # Children have no home_id of their own; they follow a parent and
                # sleep under that parent's roof without consuming a separate bed.
                event = {
                    "event": "birth",
                    "id": child.id,
                    "tick": tick_number,
                    "parents": [first.id, second.id],
                    "name": child.name,
                }
                self.history.append(event)
                events.append(event)
        return events

    def _child_name(self) -> str:
        """Draw a name, numbering it when a living villager already answers to it."""

        name = self.rng.choice(BIRTH_NAMES)
        living_names = {citizen.name for citizen in self.citizens if citizen.alive}
        if name not in living_names:
            return name
        suffix = 2
        while f"{name} {suffix}" in living_names:
            suffix += 1
        return f"{name} {suffix}"

    def _spend(self, first: Citizen, second: Citizen, amount: int) -> None:
        """Split a shared cost between two parents, spilling over when one is short."""

        half = amount // 2
        from_first = min(first.coins, half)
        first.coins -= from_first
        remaining = amount - from_first
        from_second = min(second.coins, remaining)
        second.coins -= from_second
        remaining -= from_second
        if remaining:
            extra = min(first.coins, remaining)
            first.coins -= extra

    def _feeding_parent(self, citizen: Citizen) -> Citizen | None:
        """A living parent with grain to spare, so a child is not born to starve."""

        if citizen.age >= ADULT_MIN_AGE or not citizen.parent_ids:
            return None
        donors = [
            other
            for other in self.citizens
            if other.alive and other.id in citizen.parent_ids and other.grain > 1
        ]
        return max(donors, key=lambda donor: donor.grain) if donors else None

    def _child_pantry_home(self, citizen: Citizen) -> dict[str, Any] | None:
        """The house pantry a child may eat from: their own roof or a parent's roof."""

        if citizen.age >= ADULT_MIN_AGE:
            return None
        home = self._home_building(citizen)
        if home is not None:
            return home
        for parent in self.citizens:
            if parent.alive and parent.id in citizen.parent_ids:
                home = self._home_building(parent)
                if home is not None:
                    return home
        return None

    def _feed_citizens(self) -> list[dict[str, Any]]:
        """Hunger climbs for everyone every tick; anyone over 30 eats a grain if they have one.

        A child with no grain of their own eats from their house pantry. That covers
        both orphans and children whose surviving parent has an empty purse or store;
        the old parent-only rule let children with inherited coins starve beside a
        full market because they could not trade.
        """

        events: list[dict[str, Any]] = []
        tick_number = self.tick_count + 1
        for citizen in self.citizens:
            if not citizen.alive:
                continue
            rise = 1 if self._has_shelter(citizen) else HUNGER_RISE
            citizen.hunger = min(100, citizen.hunger + rise)
            if citizen.grain == 0 and citizen.hunger > AUTO_EAT_THRESHOLD:
                # Any child eats from the pantry of their own house or a parent's.
                # If it is empty, the town refills a small amount from the market
                # so a parentless or unfed child is never silently starved.
                if citizen.age < ADULT_MIN_AGE:
                    home = self._child_pantry_home(citizen)
                    if home is not None:
                        pantry = int(home.get("grain", 0))
                        if pantry <= 0 and self.grain_supply > 0:
                            stocked = min(ORPHAN_PANTRY_STOCK, int(self.grain_supply))
                            self.grain_supply -= stocked
                            pantry = stocked
                            home["grain"] = stocked
                        if pantry > 0:
                            home["grain"] = pantry - 1
                            citizen.hunger = max(0, citizen.hunger - EAT_RELIEF)
                            fed = {
                                "event": "fed_by_orphanage" if citizen.orphaned else "fed_by_household",
                                "id": citizen.id,
                                "name": citizen.name,
                                "building": str(home["id"]),
                                "hunger_after": citizen.hunger,
                                "tick": tick_number,
                            }
                            self.history.append(fed)
                            events.append(fed)
                            continue
                donor = self._feeding_parent(citizen)
                if donor is not None:
                    donor.grain -= 1
                    citizen.hunger = max(0, citizen.hunger - EAT_RELIEF)
                    fed = {
                        "event": "fed_by_parent",
                        "id": citizen.id,
                        "name": citizen.name,
                        "parent": donor.id,
                        "hunger_after": citizen.hunger,
                        "tick": tick_number,
                    }
                    self.history.append(fed)
                    events.append(fed)
                    continue
            if citizen.hunger > AUTO_EAT_THRESHOLD and citizen.grain > 0:
                citizen.grain -= 1
                citizen.hunger = max(0, citizen.hunger - EAT_RELIEF)
                eat = {
                    "event": "eat",
                    "id": citizen.id,
                    "grain_remaining": citizen.grain,
                    "hunger_after": citizen.hunger,
                    "tick": tick_number,
                }
                self.history.append(eat)
                events.append({"citizen": citizen.id, "event": "ate", "hunger": citizen.hunger})
            elif citizen.hunger > AUTO_EAT_THRESHOLD:
                events.append({"citizen": citizen.id, "event": "starving", "hunger": citizen.hunger})
        return events

    def _spoil_resources(self) -> None:
        """Per-tick fractional spoilage for private purses and market shelves.

        Each stock loses SPOILAGE_PER_TICK of itself every tick. The fraction is
        carried per citizen and per resource, so an integer inventory still loses
        whole units at the rate its size implies instead of waiting for a daily
        step: a citizen with 100 wood loses one every ten ticks, one with 3 grain
        loses one every ~330 ticks. The market shelf rots the same way once it holds
        more than MARKET_SPOILAGE_THRESHOLD.

        Silent on purpose: even at a tenth of a percent per tick a large village would
        write hundreds of
        history rows per tick and push every other event out of the 200-row log.
        Lifetime totals live in ``self.spoiled`` for diagnostics.
        """

        for citizen in self.citizens:
            if not citizen.alive:
                continue
            for resource in RESOURCES:
                stock = getattr(citizen, resource)
                if stock <= 0:
                    citizen.decay_carry[resource] = 0.0
                    continue
                owed = stock * SPOILAGE_PER_TICK + citizen.decay_carry[resource]
                whole = int(owed)
                citizen.decay_carry[resource] = owed - whole
                if whole <= 0:
                    continue
                removed = min(stock, whole)
                setattr(citizen, resource, stock - removed)
                self.spoiled[resource] += removed
        for resource in RESOURCES:
            attribute = f"{resource}_supply"
            supply = getattr(self, attribute)
            if supply <= MARKET_SPOILAGE_THRESHOLD:
                self.market_decay[resource] = 0.0
                continue
            owed = supply * MARKET_SPOILAGE_PER_TICK + self.market_decay[resource]
            whole = int(owed)
            self.market_decay[resource] = owed - whole
            if whole <= 0:
                continue
            removed = min(supply, whole)
            setattr(self, attribute, supply - removed)
            self.spoiled[resource] += removed

    def _fallback_decision(self, citizen: Citizen) -> dict[str, Any]:
        """A deterministic stand-in for a model that timed out or returned junk.

        Order matters: hunger outranks a roof, and a homeless villager outranks idle
        wandering, because a bed is what lets a family have children. The hunger line
        is 40, not 70: at high population the model chokes, and a villager who waits
        until 70 to eat is already losing the race. A broke citizen always works —
        never idles — and a hungry or homeless citizen never idles either.
        """

        # Hard safety net: a citizen holding grain when the market is nearly empty
        # sells immediately, even before the hunger branch can send them home.
        if self.grain_supply < 5 and citizen.grain > 5:
            return {"action": "sell", "resource": "grain", "reason": "fallback: grain buyback, sell surplus"}
        if citizen.hunger > 40:
            if citizen.grain > 0:
                return {"action": "eat", "resource": "grain", "reason": "fallback: hungry, eat grain"}
            if citizen.coins >= self.grain_price and self.grain_supply > 0:
                return {"action": "buy", "resource": "grain", "reason": "fallback: hungry, buy grain"}
            # Cannot afford food: earn it. Grain while the stomach is loud, wood when
            # only the pantry is empty (wood is what a homeless villager builds with).
            work = "grain" if citizen.hunger > 60 or self.grain_supply <= 0 else "wood"
            return {
                "action": "gather",
                "resource": work,
                "reason": f"fallback: broke at hunger {citizen.hunger}, gather {work}",
            }
        if self._home_building(citizen) is None:
            cost = BUILD_COSTS["shelter"]
            if citizen.wood >= cost["wood"] and citizen.coins >= cost["coins"]:
                return {"action": "build", "resource": "shelter", "reason": "fallback: homeless, build"}
            return {"action": "gather", "resource": "wood", "reason": "fallback: homeless, gather wood"}
        return {"action": "wander", "resource": "grain", "reason": "fallback: idle, wander"}

    def _kid_decision(self, citizen: Citizen) -> dict[str, Any]:
        """A child's entire behaviour: follow a parent, or play nearby.

        Deliberately deterministic and model-free. A child never trades, never
        takes a work order and never spends a token; this is called directly from
        _apply_actions before the adult decision path.
        """

        parents = [
            other
            for other in self.citizens
            if other.alive and other.id in citizen.parent_ids
        ]
        if parents:
            parent = min(
                parents,
                key=lambda other: self._distance(citizen.x, citizen.y, other.x, other.y),
            )
            if self._distance(citizen.x, citizen.y, parent.x, parent.y) > KID_FOLLOW_DISTANCE:
                return {
                    "action": "follow",
                    "parent": parent.id,
                    "target": (self._clamp(parent.x), self._clamp(parent.y)),
                    "reason": f"child: following {parent.name}",
                }
        angle = self.rng.uniform(0.0, math.tau)
        radius = self.rng.uniform(1.0, KID_PLAY_RADIUS)
        return {
            "action": "play",
            "target": (
                self._clamp(citizen.x + math.cos(angle) * radius),
                self._clamp(citizen.y + math.sin(angle) * radius),
            ),
            "reason": "child: playing nearby",
        }

    def _apply_actions(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        tick_number = self.tick_count + 1
        # PART C: one spatial hash build per tick; _separate only reads 9 buckets.
        self._build_spatial_grid()
        for citizen in self.citizens:
            action = citizen.pending_action
            if not citizen.alive:
                citizen.pending_action = None
                citizen.travel_action = None
                citizen.target_x, citizen.target_y = citizen.x, citizen.y
                continue

            # Crisis purchase before the walk gate: a hungry adult with coins
            # buys a meal at the decision point instead of walking home and back
            # until hunger reaches 100. The existing walk continues untouched.
            if (
                citizen.age >= ADULT_MIN_AGE
                and citizen.grain == 0
                and citizen.hunger > 50
                and citizen.coins >= self.grain_price
                and self.grain_supply > 0
            ):
                purchase = self._buy(citizen, "grain")
                if purchase.get("event") == "bought":
                    purchase_event = {
                        **purchase,
                        "id": citizen.id,
                        "tick": tick_number,
                        "reason": "crisis: purchased before walking",
                    }
                    self.history.append(purchase_event)
                    events.append(purchase_event)
                    if citizen.hunger > AUTO_EAT_THRESHOLD and citizen.grain > 0:
                        citizen.grain -= 1
                        citizen.hunger = max(0, citizen.hunger - EAT_RELIEF)
                        self.history.append(
                            {
                                "event": "ate",
                                "id": citizen.id,
                                "hunger_after": citizen.hunger,
                                "tick": tick_number,
                                "reason": "crisis: ate purchased grain",
                            }
                        )

            # PART D: a walk in progress is never interrupted by a think tick.
            # Citizens with travel_action keep their destination and queued action;
            # a far target without travel_action (older save or send-home) is
            # resumed instead of leaving the villager frozen on the spot.
            walking = citizen.travel_action is not None
            if (
                not walking
                and self._distance(citizen.x, citizen.y, citizen.target_x, citizen.target_y) > 2.0
            ):
                walking = True
            if walking:
                if citizen.travel_action is not None:
                    events.extend(self._continue_travel(citizen, tick_number))
                else:
                    events.append(self._step_toward(citizen, citizen.target_x, citizen.target_y))
                continue

            # PART A: children never reach the LLM, the market, or adult work
            # rules. Their whole decision space is follow a parent or play nearby.
            if citizen.age < ADULT_MIN_AGE:
                citizen.job = "Child"
                if not citizen.orphaned:
                    citizen.home_id = None
                citizen.pending_action = None
                if tick_number < citizen.next_think_tick:
                    continue
                citizen.next_think_tick = tick_number + self.rng.randint(NEXT_THINK_MIN, NEXT_THINK_MAX)
                decision = self._kid_decision(citizen)
                kind = str(decision["action"])
                reason = str(decision["reason"])
                citizen.last_action = kind
                citizen.last_reason = reason
                self.history.append(
                    {
                        "event": "action",
                        "tick": tick_number,
                        "id": citizen.id,
                        "action": kind,
                        "resource": "grain",
                        "reason": reason,
                    }
                )
                target = decision.get("target")
                if target and self._distance(citizen.x, citizen.y, target[0], target[1]) > ARRIVE_RADIUS:
                    citizen.target_x, citizen.target_y = target
                    citizen.travel_action = {
                        "action": kind,
                        "reason": reason,
                        "parent": decision.get("parent"),
                    }
                    events.append(self._step_toward(citizen, target[0], target[1]))
                    continue
                event = self._execute_action(citizen, kind, "grain", decision, tick_number)
                citizen.target_x, citizen.target_y = citizen.x, citizen.y
                if event is not None:
                    events.append(event)
                continue

            # Hard housing override, before any LLM decision is read: a homeless
            # adult does not get to choose. Materials in hand raise a roof now,
            # otherwise the order is a wood run; the model's action is discarded.
            if citizen.home_id is None and ADULT_MIN_AGE <= citizen.age <= URGENCY_ADULT_MAX_AGE:
                cost = BUILD_COSTS["shelter"]
                if citizen.wood >= cost["wood"] and citizen.coins >= cost["coins"]:
                    branch, kind_forced = "build", ("build", "shelter")
                else:
                    branch, kind_forced = "gather", ("gather", "wood")
                action = {
                    "action": kind_forced[0],
                    "resource": kind_forced[1],
                    "emergency": "housing",
                    "reason": f"urgency: homelessness override ({branch})",
                }
                citizen.pending_action = action
                citizen.travel_action = None
                self.urgency_overrides += 1
                if self._urgency_state.get(citizen.id) != branch:
                    self._urgency_state[citizen.id] = branch
                    urgency_event = {
                        "event": "urgency_build",
                        "id": citizen.id,
                        "name": citizen.name,
                        "action": kind_forced[0],
                        "resource": kind_forced[1],
                        "reason": "homelessness override",
                        "tick": tick_number,
                    }
                    self.history.append(urgency_event)
                    events.append(urgency_event)
            else:
                self._urgency_state.pop(citizen.id, None)

            # PART A/B: the citizen's own clock drives the decision. Hunger uses a
            # jittered threshold so a hungry cohort does not all wake together;
            # homelessness remains an immediate crisis. Emergency world orders
            # (housing, survival, farm) still bypass the wait because survival
            # cannot queue behind a clock.
            crisis = (
                citizen.hunger
                > LLM_CRISIS_HUNGER
                + self.rng.randint(-HUNGER_TRIGGER_JITTER, HUNGER_TRIGGER_JITTER)
                or self._is_homeless(citizen)
            )
            if (
                tick_number < citizen.next_think_tick
                and not crisis
                and not (action or {}).get("emergency")
            ):
                continue
            citizen.next_think_tick = tick_number + self.rng.randint(NEXT_THINK_MIN, NEXT_THINK_MAX)

            # The model timed out or replied with something unusable: never let the
            # villager freeze on a failed think. A deterministic heuristic takes the
            # wheel and the console records that the AI dropped the decision.
            # PART A (Dev Mode): when use_llm is false no model answer is ever
            # expected, so an empty pending_action goes straight to the fallback
            # brain. A world rule that already queued work (housing, idle work,
            # emergency farming) still runs: those are the town's own orders, not
            # the AI's. In AI mode a failed model reply is replaced the same way.
            if (not self.use_llm and not action) or (
                self.use_llm
                and (not action or str(action.get("reason", "")).startswith("fallback:"))
            ):
                action = self._fallback_decision(citizen)
                self.history.append(
                    {
                        "event": "fallback_action",
                        "tick": tick_number,
                        "id": citizen.id,
                        "name": citizen.name,
                        "action": action["action"],
                        "resource": action.get("resource"),
                        "reason": action["reason"],
                    }
                )
                if action["action"] == "eat":
                    # Eating is automatic in _feed_citizens; there is nowhere to walk.
                    citizen.pending_action = None
                    continue
            citizen.pending_action = None

            kind = str(action.get("action", "rest")).lower()
            resource = str(action.get("resource", "grain")).lower()
            reason = str(action.get("reason") or "")[:60]
            if action.get("reason"):
                citizen.last_reason = str(action["reason"])

            # Only wander/rest loops are broken: gathering again is how a citizen
            # builds up enough stock to sell, so repeated gathers are left alone.
            if kind == citizen.last_action:
                citizen.same_action_count += 1
            else:
                citizen.last_action = kind
                citizen.same_action_count = 1
            if kind in ("wander", "rest") and citizen.same_action_count >= REPEAT_LIMIT:
                self.history.append(
                    {
                        "event": "repetition_override",
                        "tick": tick_number,
                        "id": citizen.id,
                        "action": kind,
                        "forced": "gather",
                        "count": citizen.same_action_count,
                    }
                )
                kind = "gather"
                resource = "grain"
                citizen.same_action_count = 0

            # Deterministic rules, in priority order: survival first, then surplus.
            forced_label: str | None = None
            forced_rule: str | None = None
            # An emergency order (farm now, build a roof now) outranks the normal rules.
            emergency = bool(action.get("emergency"))
            # A citizen with an empty grain store and enough coins must buy food
            # before any wander, craft, or emergency order can send them elsewhere.
            # If the market itself is empty, the gather branch below still applies.
            if (
                citizen.grain == 0
                and citizen.coins >= self.grain_price
                and self.grain_supply > 0
            ):
                if (kind, resource) != ("buy", "grain"):
                    kind, resource = "buy", "grain"
                    forced_label, forced_rule = "buy", "no grain: forced market purchase"
            elif not emergency and citizen.grain == 0 and (
                citizen.hunger > FORCE_BUY_HUNGER or citizen.coins >= self.grain_price
            ):
                if (kind, resource) != ("gather", "grain"):
                    kind, resource = "gather", "grain"
                    forced_label, forced_rule = "gather", "starvation: gather grain"
            elif not emergency and self.grain_supply < 20 and kind == "gather" and resource != "grain":
                # Market nearly empty: every gather trip must target grain, not wood.
                resource = "grain"
                forced_label, forced_rule = "gather", "grain shortage: gather grain"
            elif (
                not emergency
                and self._in_market_district(citizen)
                and citizen.grain >= FORCE_SELL_GRAIN
                and citizen.hunger < FORCE_SELL_HUNGER
            ):
                # Surplus food goes to market, but only from the market district:
                # a villager out in the fields gathers first instead of marching
                # across the map to stand in a queue.
                if (kind, resource) != ("sell", "grain"):
                    kind, resource = "sell", "grain"
                    forced_label, forced_rule = "sell", "surplus grain: sell to market"
            elif not emergency and self._in_market_district(citizen) and (
                citizen.grain >= FORCE_SELL_STOCK or citizen.wood >= FORCE_SELL_STOCK
            ):
                if citizen.grain >= FORCE_SELL_STOCK and citizen.wood >= FORCE_SELL_STOCK:
                    # Food enters the market before timber when both run high.
                    stock_resource = "grain"
                else:
                    stock_resource = "grain" if citizen.grain >= citizen.wood else "wood"
                if (kind, resource) != ("sell", stock_resource):
                    kind, resource = "sell", stock_resource
                    forced_label, forced_rule = "sell", "surplus: sell stock"
            if forced_label is not None:
                self.history.append(
                    {
                        "event": "forced_economy",
                        "tick": tick_number,
                        "id": citizen.id,
                        "name": citizen.name,
                        "action": forced_label,
                        "resource": resource,
                        "rule": forced_rule,
                    }
                )

            # Record the decision actually applied so the viewer shows what happened.
            self.history.append(
                {
                    "event": "action",
                    "tick": tick_number,
                    "id": citizen.id,
                    "action": kind,
                    "resource": resource,
                    "reason": reason,
                }
            )

            # Trades belong in the market line, gathers at the node, socialising beside a neighbour.
            plan = self._plan_action(citizen, kind, resource)
            if plan is not None:
                target_x, target_y = plan["target"]
                citizen.target_x, citizen.target_y = target_x, target_y
                if self._distance(citizen.x, citizen.y, target_x, target_y) > self._arrive_radius(kind):
                    citizen.travel_action = {
                        "action": kind,
                        "resource": resource,
                        **{key: value for key, value in plan.items() if key != "target"},
                    }
                    events.append(self._step_toward(citizen, target_x, target_y))
                    continue

            event = self._execute_action(citizen, kind, resource, action, tick_number)
            if plan is None:
                # Actions done on the spot keep the old 1-2 unit drift; arrivals stay put.
                self._nudge(citizen, 1.0, 2.0)
            citizen.target_x, citizen.target_y = citizen.x, citizen.y
            if kind in ("buy", "sell", "trade"):
                # Out of the line and on the way home (or back to the workplace).
                self._send_home(citizen)
            if event is not None:
                events.append(event)
        return events

    def _plan_action(self, citizen: Citizen, kind: str, resource: str) -> dict[str, Any] | None:
        """Where an action has to happen; None means do it right here."""

        if kind in ("buy", "sell", "trade"):
            # PART C: join the line only inside the market district. Freezing a slot
            # for a villager still crossing the map packed the ring with dozens of
            # people who were nowhere near the counter; travellers now walk to a
            # jittered point by the market and take a slot when they arrive.
            if self._in_market_district(citizen):
                self._join_queue(citizen)
                return {"target": self._queue_position(citizen)}
            market = self._citizen_market(citizen)
            return {
                "target": (
                    self._clamp(float(market["x"]) + self.rng.uniform(-DESTINATION_JITTER, DESTINATION_JITTER)),
                    self._clamp(float(market["y"]) + self.rng.uniform(-DESTINATION_JITTER, DESTINATION_JITTER)),
                )
            }
        if kind == "gather":
            node = self._nearest_node(citizen, resource)
            if node is None:
                return None
            # PART C: destination jitter. The node's standing ring already spreads
            # a crowd, but +/- DESTINATION_JITTER keeps every approach path distinct.
            return {
                "target": (
                    self._clamp(float(node["x"]) + self.rng.uniform(-DESTINATION_JITTER, DESTINATION_JITTER)),
                    self._clamp(float(node["y"]) + self.rng.uniform(-DESTINATION_JITTER, DESTINATION_JITTER)),
                ),
                "node": node["id"],
            }
        if kind == "build":
            # While the newest tile is being settled, a builder standing outside it
            # must walk into that tile before the roof is raised. The actual build
            # still recomputes the spot on arrival, so a stale travel target can
            # never put a roof through a newly placed one.
            if resource != "shelter" or not self.needs_frontier_build:
                return None
            spot = self._free_build_spot(citizen, resource)
            if spot is None:
                return None
            target_tile = self._tile_number_at(spot[0])
            if target_tile == self.tile_count_x and self._tile_number_at(citizen.x) != target_tile:
                return {"target": (spot[0], spot[1]), "build_spot": spot}
            return None
        if kind == "socialize":
            others = [other for other in self.citizens if other.alive and other.id != citizen.id]
            if not others:
                return None
            partner = self.rng.choice(others)
            return {
                "target": (
                    self._clamp(partner.x + self._jitter()),
                    self._clamp(partner.y + self._jitter()),
                ),
                "partner": partner.id,
            }
        return None

    def _jitter(self) -> float:
        """A random +/-20 px displacement, expressed in 0-100 sim units."""

        return self.rng.uniform(-TARGET_JITTER, TARGET_JITTER)

    @staticmethod
    def _clamp(value: float) -> float:
        return min(WORLD_WIDTH, max(0.0, value))

    @staticmethod
    def _arrive_radius(kind: str) -> float:
        """Trades must land on their exact 25 px slot; other actions may stop nearby."""

        return TRADE_ARRIVE_RADIUS if kind in ("buy", "sell", "trade") else ARRIVE_RADIUS

    # -- jobs and homes --------------------------------------------------------

    def _workplace(self) -> dict[str, Any] | None:
        return next((b for b in self.buildings if b.get("type") == "workplace"), None)

    def _building_dict(self, building: dict[str, Any]) -> dict[str, Any]:
        """Snapshot a building, adding live occupancy for houses."""

        data = dict(building)
        if data.get("type") == "shelter":
            data["occupants"] = self._occupancy(str(data.get("id")))
            data["capacity"] = HOME_CAPACITY
        return data

    def _home_building(self, citizen: Citizen) -> dict[str, Any] | None:
        if not citizen.home_id:
            return None
        return next(
            (
                building
                for building in self.buildings
                if building.get("id") == citizen.home_id and building.get("type") == "shelter"
            ),
            None,
        )

    def _occupancy(self, building_id: str) -> int:
        return sum(1 for citizen in self.citizens if citizen.alive and citizen.home_id == building_id)

    def _is_homeless(self, citizen: Citizen) -> bool:
        """No roof of their own, or the roof they live under is over capacity."""

        home = self._home_building(citizen)
        return home is None or self._occupancy(str(home["id"])) > HOME_CAPACITY

    def _static_houses(self) -> list[dict[str, Any]]:
        """Map houses are shelters nobody owns; shelters a citizen builds have an owner."""

        return [
            building
            for building in self.buildings
            if building.get("type") == "shelter" and not building.get("owner_id")
        ]

    def _set_home(self, citizen: Citizen, building: dict[str, Any]) -> bool:
        """Move one villager into a house with room; silent, since callers log why."""

        if (
            not citizen.alive
            or citizen.home_id
            or citizen.age < ADULT_MIN_AGE
            or building.get("type") != "shelter"
        ):
            return False
        building_id = str(building["id"])
        if self._occupancy(building_id) >= HOME_CAPACITY:
            return False
        citizen.home_id = building_id
        return True

    def _bank_funded_house(
        self, citizen: Citizen, tick_number: int
    ) -> dict[str, Any] | None:
        """Spawn a public house for the Bank when every existing bed is taken."""

        spot = self._free_build_spot(citizen, "shelter")
        if spot is None:
            spot = self._nearest_free_tile(citizen.x, citizen.y)
        if spot is None:
            return None
        x, y, district_id = spot
        used = {str(building.get("id")) for building in self.buildings}
        number = len(self.buildings) + 1
        while f"b{number}" in used:
            number += 1
        building = {
            "id": f"b{number}",
            "type": "shelter",
            "name": "Bank-Funded House",
            "x": float(x),
            "y": float(y),
            "district_id": district_id,
            "market_id": int(self._zone_market_for_point(x, y)["id"]),
            "owner_id": "",
            "built_tick": tick_number,
        }
        self.buildings.append(building)
        try:
            persistence.save_building(building)
        except Exception as error:
            _LOGGER.warning("bank-funded building not persisted: %s", error)
        return building

    def _auto_assign_homes(self, tick_number: int | None = None) -> list[dict[str, Any]]:
        """Give every homeless villager a bed, with the Bank funding new roofs.

        Housing is a right, not a chore: a citizen spawns into a free bed and keeps
        it, so the birth rule's home requirement is never the thing that stops growth.
        When the beds are full, the Bank buys one bed per homeless adult for 15 coins
        and spawns a public house only when no existing roof has room.
        """

        events: list[dict[str, Any]] = []
        shelters = [b for b in self.buildings if b.get("type") == "shelter"]

        def note(citizen: Citizen, house_id: str, rule: str) -> None:
            if tick_number is None:
                return
            event = {
                "event": "housed",
                "id": citizen.id,
                "name": citizen.name,
                "building": house_id,
                "rule": rule,
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)

        # Occupancy once per house, then updated as beds are handed out. The old
        # loop filled the first house to ten before touching the second, and a
        # child joined a parent's roof with no capacity check at all: measured at
        # 300 people, every living citizen had home_id "b1", so every return trip
        # after a trade converged on one pixel (21 neighbours inside 10 units).
        # Even housing is the largest single anti-clump fix in this phase.
        counts = {str(house["id"]): self._occupancy(str(house["id"])) for house in shelters}

        # Children (under 16) deliberately have no home_id: they live with a parent
        # and are excluded from bed counts, so only adults own beds.
        # Everyone else takes the bed in the emptiest roof, so the town fills its
        # houses evenly instead of stacking the first ten villagers in one home.
        for citizen in self.citizens:
            if not citizen.alive or citizen.home_id or citizen.age < ADULT_MIN_AGE:
                continue
            open_houses = [
                house for house in shelters if counts.get(str(house["id"]), 0) < HOME_CAPACITY
            ]
            if not open_houses:
                break
            house = min(open_houses, key=lambda entry: counts.get(str(entry["id"]), 0))
            house_id = str(house["id"])
            citizen.home_id = house_id
            counts[house_id] = counts.get(house_id, 0) + 1
            note(citizen, house_id, "emptiest roof with a free bed")

        # Housing stimulus: a full town no longer leaves adults on the grass while
        # the Bank sits on tax revenue. Each citizen costs 15 coins, and a house is
        # spawned only when the existing roofs have no free bed.
        funded_tick = tick_number if tick_number is not None else self.tick_count + 1
        for citizen in self.citizens:
            if not citizen.alive or citizen.home_id or citizen.age < ADULT_MIN_AGE:
                continue
            if self.central_bank_reserve <= BANK_HOUSING_MIN_RESERVE:
                break
            open_houses = [
                house for house in shelters if counts.get(str(house["id"]), 0) < HOME_CAPACITY
            ]
            if not open_houses:
                house = self._bank_funded_house(citizen, funded_tick)
                if house is None:
                    break
                shelters.append(house)
                counts[str(house["id"])] = 0
                open_houses = [house]
            house = min(open_houses, key=lambda entry: counts.get(str(entry["id"]), 0))
            house_id = str(house["id"])
            self.central_bank_reserve -= BANK_HOUSING_COST
            citizen.home_id = house_id
            counts[house_id] = counts.get(house_id, 0) + 1
            event = {
                "event": "bank_intervention",
                "message": f"Bank funded housing for {citizen.name}.",
                "id": citizen.id,
                "name": citizen.name,
                "amount": BANK_HOUSING_COST,
                "reserve": self.central_bank_reserve,
                "building": house_id,
                "tick": funded_tick,
            }
            self.history.append(event)
            events.append(event)
        return events

    def _idle_work(self) -> list[dict[str, Any]]:
        """A villager with no decision yet works instead of standing around.

        At 10x the model answers only a handful of citizens per second, so the town
        starved beside a market holding grain: nobody had been told to farm, and
        nobody refilled the shelves. A real decision always wins; this fills silence.
        """

        events: list[dict[str, Any]] = []
        tick_number = self.tick_count + 1
        for citizen in self.citizens:
            if not citizen.alive or citizen.pending_action or citizen.travel_action:
                continue
            # Children are handled by _kid_decision: no work orders, no market.
            if citizen.age < ADULT_MIN_AGE:
                continue
            # PART A: idle work follows the same personal clock; it must not become
            # a second synchronized batch. Walkers were skipped above and keep the
            # route they already chose.
            if tick_number < citizen.next_think_tick:
                continue
            if self._distance(citizen.x, citizen.y, citizen.target_x, citizen.target_y) > 2.0:
                continue
            if citizen.grain == 0 and citizen.hunger > AUTO_EAT_THRESHOLD:
                if citizen.coins >= self.grain_price and self.grain_supply > 0:
                    action = {
                        "action": "buy",
                        "resource": "grain",
                        "emergency": "survival",
                        "reason": "idle: hungry, buy grain",
                    }
                else:
                    action = {
                        "action": "gather",
                        "resource": "grain",
                        "emergency": "survival",
                        "reason": "idle: hungry, forage grain",
                    }
            elif citizen.grain < 5:
                action = {"action": "gather", "resource": "grain", "reason": "idle: grow food"}
            elif citizen.hunger < FORCE_SELL_HUNGER and self.grain_supply < 60:
                action = {"action": "sell", "resource": "grain", "reason": "idle: stock the market"}
            elif citizen.wood < 5:
                action = {"action": "gather", "resource": "wood", "reason": "idle: cut wood"}
            else:
                action = {"action": "gather", "resource": "grain", "reason": "idle: grow food"}
            citizen.pending_action = action
            event = {
                "event": "idle_work",
                "id": citizen.id,
                "name": citizen.name,
                "action": action["action"],
                "resource": action["resource"],
                "hunger": citizen.hunger,
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)
        return events

    def _shelter_capacity(self) -> int:
        """Beds in the village: every shelter, map house or built, holds five."""

        return sum(1 for building in self.buildings if building.get("type") == "shelter") * HOME_CAPACITY

    def _auto_build_homes(self) -> list[dict[str, Any]]:
        """While there are more people than beds, every adult works on the next shelter.

        PART C: this used to arm within five beds of capacity and to raise a roof on
        credit, which hid the real bottleneck. A villager with no wood waited for the
        handout instead of cutting any, and a villager with wood but no coins built
        for free. The override is now strict and materials-only: more people than
        beds, gather wood below five logs, build at five logs and ten coins, sell
        grain to raise the coins otherwise. It sets pending_action, so the decision
        is in place before the model's answer is read and the model cannot veto it.
        """

        events: list[dict[str, Any]] = []
        beds = self._total_beds()
        # PART B: no roof may be raised past the tile plan; the town expands instead.
        shelters = sum(1 for b in self.buildings if b.get("type") == "shelter")
        if shelters >= self.tile_count_x * HOUSES_PER_TILE:
            return events
        # Trigger on a completely full town, not only on a visible homeless villager.
        # A village sitting exactly on its bed count can neither breed nor build:
        # _births refuses a child when population == beds, and a strict "more people
        # than beds" test would never arm. Measured: pop 20 with 20 beds froze from
        # tick ~400 to 500 with no growth and no roofs. "Full" therefore includes
        # equality; the moment a roof is free, the override stops on its own.
        if self.population < beds:
            return events
        tick_number = self.tick_count + 1
        cost = BUILD_COSTS["shelter"]
        # PART C (Phase 93): one roof holds HOME_CAPACITY people, so a town of P with
        # B beds only needs ceil((P - B) / HOME_CAPACITY) builders. Arming every adult
        # at once built 39 shelters inside a single 500-tick window -- 620 beds for
        # 233 people -- and put the whole workforce on woodcutting duty. The fields
        # were left unworked and 387 people starved. Only the hands the deficit needs
        # are drafted; everyone else keeps farming, and the makers come first.
        builders_needed = max(
            1, math.ceil(max(1, self.population - beds) / HOME_CAPACITY)
        )
        drafted = 0
        candidates = sorted(
            self.citizens,
            key=lambda c: (c.wood < cost["wood"] or c.coins < cost["coins"], c.id),
        )
        for citizen in candidates:
            if not citizen.alive or citizen.age < ADULT_MIN_AGE:
                continue
            if drafted >= builders_needed:
                break
            current = citizen.pending_action or {}
            if current.get("emergency") == "farming":
                # An empty market outranks construction for a hungry villager.
                continue
            if citizen.wood >= cost["wood"] and citizen.coins >= cost["coins"]:
                action = {
                    "action": "build",
                    "resource": "shelter",
                    "emergency": "build",
                    "reason": "beds full: build a shelter",
                }
            elif citizen.wood < cost["wood"]:
                action = {
                    "action": "gather",
                    "resource": "wood",
                    "emergency": "build_materials",
                    "reason": "beds full: gather wood for a shelter",
                }
            elif citizen.grain > FORCE_SELL_STOCK:
                action = {
                    "action": "sell",
                    "resource": "grain",
                    "emergency": "build_materials",
                    "reason": "beds full: sell grain to fund a shelter",
                }
            else:
                action = {
                    "action": "gather",
                    "resource": "wood",
                    "emergency": "build_materials",
                    "reason": "beds full: cut wood to earn the coins for a shelter",
                }
            if (
                current.get("emergency") == action["emergency"]
                and current.get("resource") == action["resource"]
            ):
                drafted += 1
                continue
            citizen.pending_action = action
            drafted += 1
            event = {
                "event": "forced_housing",
                "id": citizen.id,
                "name": citizen.name,
                "action": action["action"],
                "resource": action["resource"],
                "rule": action["reason"],
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)
        return events

    def _cap_hoarding(self) -> list[dict[str, Any]]:
        """Grain rules that run before actions are applied.

        A villager holding more than HOARD_GRAIN_LIMIT may not gather grain again:
        the decision becomes a sale, so stock leaves the purse for the market. And
        once the shelves are past OVERFARM_SUPPLY, every gather-grain decision
        becomes a wood run instead, so the fields get a rest.
        """

        events: list[dict[str, Any]] = []
        tick_number = self.tick_count + 1
        for citizen in self.citizens:
            if not citizen.alive or citizen.grain <= HOARD_GRAIN_LIMIT:
                continue
            action = citizen.pending_action or {}
            if str(action.get("action", "")).lower() != "gather":
                continue
            if str(action.get("resource", "grain")).lower() != "grain":
                continue
            citizen.pending_action = {
                "action": "sell",
                "resource": "grain",
                "emergency": "hoard_cap",
                "reason": f"hoarding {citizen.grain} grain: sell instead of farming",
            }
            event = {
                "event": "hoard_cap",
                "id": citizen.id,
                "name": citizen.name,
                "grain": citizen.grain,
                "action": "sell",
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)
        overfarm_limit = max(OVERFARM_SUPPLY, self.population * OVERFARM_PER_CITIZEN)
        if self.grain_supply <= overfarm_limit:
            return events
        for citizen in self.citizens:
            if not citizen.alive:
                continue
            action = citizen.pending_action or {}
            if str(action.get("action", "")).lower() != "gather":
                continue
            if str(action.get("resource", "grain")).lower() != "grain":
                continue
            citizen.pending_action = {
                "action": "gather",
                "resource": "wood",
                "emergency": "overfarm",
                "reason": (
                    f"market holds {self.grain_supply} grain, over the "
                    f"{overfarm_limit} glut line: cut wood instead"
                ),
            }
            event = {
                "event": "overfarm",
                "id": citizen.id,
                "name": citizen.name,
                "supply": self.grain_supply,
                "action": "gather",
                "resource": "wood",
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)
        return events

    def _auto_partner(self, tick_number: int) -> list[dict[str, Any]]:
        """Pair single adults who already have a roof.

        The model has no way to propose, so waiting for it meant nobody ever married
        and the birth rule's partner requirement could never be met.
        """

        events: list[dict[str, Any]] = []
        singles = [
            citizen
            for citizen in self.citizens
            if citizen.alive
            and citizen.partner_id is None
            and citizen.home_id
            and ADULT_MIN_AGE <= citizen.age <= ADULT_MAX_AGE
        ]
        while len(singles) >= 2:
            first = singles.pop(0)
            second = next((other for other in singles if other.id != first.id), None)
            if second is None:
                break
            singles.remove(second)
            first.partner_id, second.partner_id = second.id, first.id
            event = {
                "event": "partnered",
                "id1": first.id,
                "id2": second.id,
                "names": [first.name, second.name],
                "reason": "auto: single adults with a home",
                "tick": tick_number,
            }
            self.history.append(event)
            events.append(event)
        return events

    def _assign_home(self, building: dict[str, Any], builder: Citizen) -> None:
        """Move the builder and as many other homeless villagers in as the house holds."""

        if building.get("type") != "shelter":
            return
        building_id = str(building["id"])
        for candidate in (builder, *self.citizens):
            if self._occupancy(building_id) >= HOME_CAPACITY:
                return
            if not candidate.alive or candidate.home_id:
                continue
            candidate.home_id = building_id

    # -- market line -----------------------------------------------------------

    @staticmethod
    def _tile_number_at(x: float) -> int:
        """The 1-based tile column containing an x coordinate."""

        return max(1, int(float(x) // TILE_WIDTH) + 1)

    def _market_for_tile(self, tile_number: int) -> dict[str, Any] | None:
        """The counter that belongs to a tile. One tile has one market."""

        for market in self.markets:
            if self._tile_number_at(float(market["x"])) == tile_number:
                return market
        return None

    def _in_market_district(self, citizen: Citizen) -> bool:
        """Whether the citizen is standing at *their* zoned counter."""

        market = self._citizen_market(citizen)
        return self._distance(
            citizen.x, citizen.y, float(market["x"]), float(market["y"])
        ) <= MARKET_DISTRICT_RADIUS

    def _nearest_market(self, x: float, y: float) -> dict[str, Any]:
        """The closest counter to a point: no trip is longer than it has to be."""

        if not self.markets:
            return {"id": 1, "x": MARKET_X, "y": MARKET_Y}
        return min(
            self.markets,
            key=lambda market: self._distance(x, y, float(market["x"]), float(market["y"])),
        )

    def _citizen_market(self, citizen: Citizen) -> dict[str, Any]:
        """The counter a villager must use, decided by tile rather than distance.

        A housed citizen trades in the tile that contains their home; a homeless
        citizen trades in whichever tile they are currently standing in. This is
        what keeps the second block's trade at Market 2 instead of leaking into
        Market 1 simply because it is nearby.
        """

        home = self._home_building(citizen)
        if home is not None:
            tile = self._tile_number_at(float(home["x"]))
            market = self._market_for_tile(tile)
            if market is not None:
                return market
            return self._nearest_market(float(home["x"]), float(home["y"]))

        tile = self._tile_number_at(citizen.x)
        market = self._market_for_tile(tile)
        if market is not None:
            return market
        return self._nearest_market(citizen.x, citizen.y)

    def _queue_index(self, citizen_id: str) -> int | None:
        try:
            return self.market_queue.index(citizen_id)
        except ValueError:
            return None

    def _join_queue(self, citizen: Citizen) -> int:
        """Join the line and freeze this villager's slot and standing spot.

        The slot and its pixel are assigned once. Recomputing them every tick (as
        the old code did) made the queue a moving target: the ring re-sized with
        the crowd and a fresh jitter was drawn on every call, so villagers orbited
        the counter instead of ever reaching it.
        """

        if citizen.id not in self.market_queue:
            self.market_queue.append(citizen.id)
        if citizen.queue_x is not None and citizen.queue_y is not None:
            return int(citizen.queue_slot_index or 0)
        taken = {
            int(other.queue_slot_index)
            for other in self.citizens
            if other is not citizen
            and other.alive
            and other.id in self.market_queue
            and other.queue_slot_index is not None
        }
        slot = 0
        while slot in taken:
            slot += 1
        # The counter is chosen once, from where they stand, and frozen with the slot.
        market = self._citizen_market(citizen)
        citizen.market_id = int(market["id"])
        crowd = max(len(self.market_queue), slot + 1)
        point_x, point_y = self._queue_point(slot, crowd, market)
        citizen.queue_slot_index = slot
        # The only jitter draw this slot will ever get.
        citizen.queue_x = self._clamp(point_x + self.rng.uniform(-QUEUE_JITTER, QUEUE_JITTER))
        citizen.queue_y = self._clamp(point_y + self.rng.uniform(-QUEUE_JITTER, QUEUE_JITTER))
        return slot

    def _leave_queue(self, citizen: Citizen) -> None:
        """Step out of the line and forget the slot, so the next visit is fresh."""

        if citizen.id in self.market_queue:
            self.market_queue.remove(citizen.id)
        citizen.queue_slot_index = None
        citizen.queue_x = None
        citizen.queue_y = None

    def _queue_position(self, citizen: Citizen) -> tuple[float, float]:
        """The frozen spot this villager walks to, joining the line if needed."""

        if citizen.queue_x is None or citizen.queue_y is None:
            self._join_queue(citizen)
        return float(citizen.queue_x), float(citizen.queue_y)

    def _prune_queue(self) -> None:
        """Dead villagers (age, hunger or the god hand) must not hold a place in line."""

        living = {citizen.id for citizen in self.citizens if citizen.alive}
        self.market_queue = [citizen_id for citizen_id in self.market_queue if citizen_id in living]

    def _queue_point(
        self, index: int, crowd: int, market: dict[str, Any] | None = None
    ) -> tuple[float, float]:
        """Ring position for one slot at one counter: slot i owns i * 360 / slots degrees.

        Pure geometry with no randomness. The jitter is applied once, in
        _join_queue, so a slot never moves while a villager is holding it.
        """

        market = market or (self.markets[0] if self.markets else {"x": MARKET_X, "y": MARKET_Y})
        market_x, market_y = float(market["x"]), float(market["y"])
        # PART C: concentric rings 12 units apart, each holding as many slots as a
        # 10-unit arc spacing allows. A single ring packed 100 villagers shoulder to
        # shoulder around the counter; rings keep the line under MAX_CLUMP without
        # spilling the crowd into one hoop.
        wall = min(
            market_x,
            market_y,
            max(0.0, self.world_width - market_x),
            max(0.0, self.world_height - market_y),
        )
        max_radius = min(MAX_QUEUE_RADIUS, max(QUEUE_RADIUS, wall - 2.0))
        ring_radii: list[float] = []
        radius = QUEUE_RADIUS
        while radius <= max_radius + 1e-6:
            ring_radii.append(radius)
            radius += QUEUE_RING_GAP
        if not ring_radii:
            ring_radii = [max(QUEUE_RADIUS, max_radius)]
        capacities = [
            max(MIN_QUEUE_SLOTS, int((2.0 * math.pi * ring) / QUEUE_SLOT_SPACING))
            for ring in ring_radii
        ]
        remaining = max(0, index)
        ring_index = 0
        while ring_index < len(ring_radii) - 1 and remaining >= capacities[ring_index]:
            remaining -= capacities[ring_index]
            ring_index += 1
        slots_here = capacities[ring_index]
        angle = math.radians((remaining % slots_here) * (360.0 / slots_here))
        ring_radius = ring_radii[ring_index]
        return (
            self._clamp(market_x + math.cos(angle) * ring_radius),
            self._clamp(market_y + math.sin(angle) * ring_radius),
        )

    def _send_home(self, citizen: Citizen) -> None:
        """After a trade, walk out of the line to their house (or the workplace)."""

        if not citizen.alive:
            return
        anchor = self._home_building(citizen) or self._workplace()
        if anchor is None:
            citizen.target_x, citizen.target_y = citizen.x, citizen.y
        else:
            # PART C: a stable per-villager offset around the roof, so ten residents
            # do not all walk back to the same pixel (destination jitter, home edition).
            digits = "".join(ch for ch in str(citizen.id) if ch.isdigit())
            slot = int(digits) if digits else sum(ord(ch) for ch in str(citizen.id))
            angle = math.radians((slot * 137.508) % 360.0)
            radius = 3.0 + (slot % 5) * 1.0
            citizen.target_x = self._clamp(float(anchor["x"]) + math.cos(angle) * radius)
            citizen.target_y = self._clamp(float(anchor["y"]) + math.sin(angle) * radius)
        citizen.travel_action = {"action": "return", "resource": "grain"}

    def _continue_travel(self, citizen: Citizen, tick_number: int) -> list[dict[str, Any]]:
        """Walk one step toward the target, then run the action that waited for it."""

        journey = citizen.travel_action or {}
        kind = str(journey.get("action", "rest"))
        # PART C: a congested market serves the villager where they stand instead of
        # forcing them to push into the crowd for a slot they cannot reach.
        if (
            kind in ("buy", "sell", "trade")
            and self._in_market_district(citizen)
            and self._crowd_size(citizen) > MAX_CLUMP
        ):
            citizen.travel_action = None
            event = self._execute_action(
                citizen,
                kind,
                str(journey.get("resource", "grain")),
                journey,
                tick_number,
            )
            citizen.target_x, citizen.target_y = citizen.x, citizen.y
            self._send_home(citizen)
            return [event] if event is not None else []
        if kind in ("buy", "sell", "trade"):
            # Take a slot only on arrival in the district; the frozen slot is then
            # re-aimed every tick so the villager walks straight to it.
            if citizen.queue_x is None and self._in_market_district(citizen):
                self._join_queue(citizen)
            if citizen.queue_x is not None:
                citizen.target_x, citizen.target_y = self._queue_position(citizen)
        if self._distance(citizen.x, citizen.y, citizen.target_x, citizen.target_y) > self._arrive_radius(kind):
            return [self._step_toward(citizen, citizen.target_x, citizen.target_y)]

        citizen.travel_action = None
        # A decision made during the walk used to be dropped when it matched the
        # action just completed, which quietly threw away fresh model intents (the
        # "decision_discarded" rows). It now stays pending and runs on a later tick;
        # the arrival action and the queued intent are two separate acts.
        event = self._execute_action(
            citizen,
            kind,
            str(journey.get("resource", "grain")),
            journey,
            tick_number,
        )
        citizen.target_x, citizen.target_y = citizen.x, citizen.y
        if kind in ("buy", "sell", "trade"):
            self._send_home(citizen)
        return [event] if event is not None else []

    def _build_spatial_grid(self) -> None:
        """PART C: bucket living citizens by (int(x/10), int(y/10)). One pass, O(n)."""

        grid: dict[tuple[int, int], list[Citizen]] = {}
        for citizen in self.citizens:
            if not citizen.alive:
                continue
            key = (int(citizen.x // SPATIAL_CELL), int(citizen.y // SPATIAL_CELL))
            grid.setdefault(key, []).append(citizen)
        self.spatial_grid = grid

    def _nearby(self, citizen: Citizen) -> list[Citizen]:
        """The 9 buckets around a citizen: the only neighbours separation tests.

        With 10-unit cells a 10-unit radius cannot reach a bucket two cells away,
        so nine buckets are complete and the check stays O(n) for the whole town.
        """

        cell_x = int(citizen.x // SPATIAL_CELL)
        cell_y = int(citizen.y // SPATIAL_CELL)
        found: list[Citizen] = []
        for offset_x in (-1, 0, 1):
            for offset_y in (-1, 0, 1):
                bucket = self.spatial_grid.get((cell_x + offset_x, cell_y + offset_y))
                if bucket:
                    found.extend(bucket)
        return found

    def _separate(self, citizen: Citizen) -> None:
        """PART C: boids separation, weighted by distance, plus the clump rule.

        Straight-line walking let villagers on the same bearing hold the exact same
        pixel for a whole trip. Every neighbour inside SEPARATION_DISTANCE pushes
        this citizen away along the vector between them, weighted by
        (1 - distance / SEPARATION_DISTANCE) so the closest pairs push hardest.
        A local crowd above MAX_CLUMP also gets a hard repulsion away from its own
        centroid, steered toward the emptiest direction, until density drops.
        """

        push_x = 0.0
        push_y = 0.0
        close: list[Citizen] = []
        for other in self._nearby(citizen):
            if other is citizen or not other.alive:
                continue
            dx = citizen.x - other.x
            dy = citizen.y - other.y
            distance = math.hypot(dx, dy)
            if distance >= CLUMP_RADIUS:
                continue
            close.append(other)
            if distance >= SEPARATION_DISTANCE:
                continue
            if distance < 1e-6:
                # Exactly stacked: any bearing will do, as long as it is not zero.
                angle = self.rng.uniform(0.0, math.tau)
                dx, dy, distance = math.cos(angle), math.sin(angle), 1.0
            weight = 1.0 - distance / SEPARATION_DISTANCE
            push_x += dx / distance * weight
            push_y += dy / distance * weight
        crowd = len(close)
        if crowd > MAX_CLUMP:
            # MAX_CLUMP is a hard ceiling. Push away from every neighbour inside
            # CLUMP_RADIUS, weighted by (1 - distance / CLUMP_RADIUS), and add a
            # stronger bias away from the single closest body: in a symmetric blob
            # the pairwise sum cancels to zero at the centre, while the nearest
            # neighbour always gives a definite direction out of the crowd.
            clump_x = 0.0
            clump_y = 0.0
            nearest_x = 0.0
            nearest_y = 0.0
            nearest_distance = float("inf")
            for other in close:
                dx = citizen.x - other.x
                dy = citizen.y - other.y
                distance = math.hypot(dx, dy)
                if distance < 1e-6:
                    angle = self.rng.uniform(0.0, math.tau)
                    dx, dy, distance = math.cos(angle), math.sin(angle), 1.0
                weight = 1.0 - distance / CLUMP_RADIUS
                clump_x += dx / distance * weight
                clump_y += dy / distance * weight
                if distance < nearest_distance:
                    nearest_x, nearest_y, nearest_distance = dx, dy, distance
            clump_x += nearest_x / nearest_distance
            clump_y += nearest_y / nearest_distance
            # A small random component breaks any remaining tie.
            jitter_angle = self.rng.uniform(0.0, math.tau)
            clump_x += math.cos(jitter_angle) * 0.35
            clump_y += math.sin(jitter_angle) * 0.35
            strength = (crowd - MAX_CLUMP) / MAX_CLUMP
            push_x += clump_x * strength
            push_y += clump_y * strength
        magnitude = math.hypot(push_x, push_y)
        if magnitude <= 0.0:
            return crowd
        step = CLUMP_PUSH if crowd > MAX_CLUMP else SEPARATION_PUSH
        citizen.x = self._clamp(citizen.x + push_x / magnitude * step)
        citizen.y = self._clamp(citizen.y + push_y / magnitude * step)
        return crowd

    def _crowd_size(self, citizen: Citizen) -> int:
        """How many living neighbours this citizen has inside CLUMP_RADIUS."""

        return sum(
            1
            for other in self._nearby(citizen)
            if other is not citizen
            and other.alive
            and self._distance(citizen.x, citizen.y, other.x, other.y) < CLUMP_RADIUS
        )

    def _resolve_clumps(self) -> None:
        """PART C: apply separation to every living body, not only to walkers.

        Separation in _step_toward only covers citizens on the road. Villagers who
        have arrived at a queue slot, a node ring or their own front door could still
        stand in a crowd bigger than MAX_CLUMP for as long as the crowd existed. This
        pass relaxes the whole town up to three times per tick: each pass rebuilds
        the hash, pushes every over-crowded body away from its local centroid, and
        stops early once no crowd is above the threshold.
        """

        for _ in range(24):
            self._build_spatial_grid()
            crowded = 0
            for citizen in self.citizens:
                if citizen.alive and self._separate(citizen) > MAX_CLUMP:
                    crowded += 1
            if crowded == 0:
                # Pre-push counts were clean; verify the settled positions before
                # stopping, because a push can nudge somebody into a new crowd.
                if self.clump_stats()["over"] == 0:
                    break

    def clump_stats(self) -> dict[str, float]:
        """Proof for the handover: the largest local crowd within CLUMP_RADIUS."""

        self._build_spatial_grid()
        worst = 0
        total = 0
        over = 0
        for citizen in self.citizens:
            if not citizen.alive:
                continue
            count = sum(
                1
                for other in self._nearby(citizen)
                if other is not citizen
                and other.alive
                and self._distance(citizen.x, citizen.y, other.x, other.y) < CLUMP_RADIUS
            )
            worst = max(worst, count)
            total += count
            if count > MAX_CLUMP:
                over += 1
        population = max(1, self.population)
        return {"max": worst, "mean": round(total / population, 2), "over": over}

    @staticmethod
    def _citizen_speed(citizen: Citizen) -> float:
        """The safe per-tick walking speed for this body."""

        return min(MAX_SPEED, max(0.1, float(citizen.walk_speed)))

    def _step_toward(self, citizen: Citizen, target_x: float, target_y: float) -> dict[str, Any]:
        """Move this citizen's own speed along the straight line, after making room."""

        crowd = self._separate(citizen)
        distance = self._distance(citizen.x, citizen.y, target_x, target_y)
        if distance > 0:
            # PART C: congested bodies advance at half speed, so a walking crowd
            # does not keep packing itself into the same ten units every tick.
            speed = self._citizen_speed(citizen)
            step = min(speed, distance) * (0.5 if crowd > MAX_CLUMP else 1.0)
            citizen.x = min(WORLD_WIDTH, max(0.0, citizen.x + (target_x - citizen.x) / distance * step))
            citizen.y = min(WORLD_HEIGHT, max(0.0, citizen.y + (target_y - citizen.y) / distance * step))
        return {
            "citizen": citizen.id,
            "event": "move",
            "id": citizen.id,
            "target_x": round(target_x, 1),
            "target_y": round(target_y, 1),
            "x": round(citizen.x, 1),
            "y": round(citizen.y, 1),
        }

    def _execute_action(
        self,
        citizen: Citizen,
        kind: str,
        resource: str,
        action: dict[str, Any],
        tick_number: int,
    ) -> dict[str, Any] | None:
        """Apply an action's effect; any walking has already been done by the caller."""

        if kind == "return":
            # Arriving home after a trade is a no-op; the walk itself was the action.
            return None
        if kind == "play":
            self._nudge(citizen, 0.5, 1.5)
            return {"citizen": citizen.id, "event": "played", "id": citizen.id, "tick": tick_number}
        if kind == "follow":
            return {"citizen": citizen.id, "event": "followed", "id": citizen.id, "tick": tick_number}
        event: dict[str, Any] | None = None
        if kind == "build":
            event = self._build(citizen, resource)
        elif kind in ("rest", "wander"):
            event = self._wander(citizen, kind)
        elif kind == "socialize":
            partner = str(action.get("partner") or "")
            other = next(
                (candidate for candidate in self.citizens if candidate.alive and candidate.id == partner),
                None,
            )
            social = {
                "event": "socialized",
                "id": citizen.id,
                "with": partner,
                "name": other.name if other else None,
                "tick": tick_number,
            }
            self.history.append(social)
            event = {"citizen": citizen.id, **social}
        elif kind not in ACTIONS or resource not in RESOURCES:
            event = {"citizen": citizen.id, "event": "invalid", "action": action}
        elif kind == "gather":
            event = self._gather(citizen, resource)
        elif kind == "buy":
            event = self._buy(citizen, resource)
            self._leave_queue(citizen)
            if event.get("event") == "buy_rejected":
                self._log_action_failure(citizen, "buy", event, tick_number)
            else:
                # Market receipts must reach world.history: the viewer's 💰 bubble reads it.
                self.history.append({**event, "id": citizen.id, "tick": tick_number})
        elif kind == "trade":
            event = self._trade(citizen, resource, action, tick_number)
            self._leave_queue(citizen)
            if event.get("event") == "trade_rejected":
                self._log_action_failure(citizen, "trade", event, tick_number)
        else:
            event = self._sell(citizen, resource)
            self._leave_queue(citizen)
            if event.get("event") == "sold":
                self.history.append({**event, "id": citizen.id, "tick": tick_number})
        return event

    def _log_action_failure(
        self, citizen: Citizen, action_name: str, event: dict[str, Any], tick_number: int
    ) -> None:
        """Why a market order could not be filled, kept in history for diagnosis."""

        resource = str(event.get("resource", "grain"))
        supply = getattr(self, f"{resource}_supply", 0)
        reason = str(event.get("reason") or ("no_supply" if supply <= 0 else "insufficient_coins"))
        self.history.append(
            {
                "event": "action_failed",
                "id": citizen.id,
                "action": action_name,
                "reason": reason,
                "resource": resource,
                "price": event.get("price"),
                "coins": citizen.coins,
                "tick": tick_number,
            }
        )

    def _nudge(self, citizen: Citizen, low: float, high: float) -> None:
        """Move a citizen 1-2 units in a random direction, clamped to the world bounds."""

        angle = self.rng.uniform(0.0, math.tau)
        step = self.rng.uniform(low, high)
        citizen.x = min(WORLD_WIDTH, max(0.0, citizen.x + math.cos(angle) * step))
        citizen.y = min(WORLD_HEIGHT, max(0.0, citizen.y + math.sin(angle) * step))

    def _passive_wander(self, busy_ids: set[str]) -> list[dict[str, Any]]:
        """One unlogged unit of drift is too quiet; these are the only wander events logged."""

        events: list[dict[str, Any]] = []
        tick_number = self.tick_count + 1
        for citizen in self.citizens:
            if not citizen.alive or citizen.id in busy_ids:
                continue
            self._nudge(citizen, 1.0, 1.0)
            entry = {
                "event": "wander",
                "id": citizen.id,
                "x": round(citizen.x, 1),
                "y": round(citizen.y, 1),
                "tick": tick_number,
            }
            self.history.append(entry)
            events.append(dict(entry))
        return events

    def _has_shelter(self, citizen: Citizen) -> bool:
        """A roof is a home assignment, not merely having built the walls."""

        return self._home_building(citizen) is not None

    def _next_citizen_id(self) -> str:
        """The lowest free c-number, so a founding party never shadows a villager."""

        taken = {citizen.id for citizen in self.citizens}
        index = len(self.citizens) + 1
        while f"c{index}" in taken:
            index += 1
        return f"c{index}"

    def _tile_is_free(self, gx: int, gy: int) -> bool:
        """Snapped ground: off the dirt roads and 80 px clear of every building."""

        # PART A: grass only. The roof art is three tiles across, so its entire
        # 3 x 3 footprint must sit on open grass: never on an avenue, a dirt road
        # or the forest that owns the outer tiles.
        if not (3 <= gx <= GRID_TILES_X - 4 and 3 <= gy <= GRID_TILES_Y - 4):
            return False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (gx + dx, gy + dy) in self.road_tiles:
                    return False
        x, y = tile_center_unit(gx, gy)
        if self._distance(x, y, MARKET_X, MARKET_Y) <= CENTER_BUILD_CLEARANCE:
            # The square stays open ground: no roof is raised on the plaza.
            return False
        return all(
            self._distance(x, y, float(building["x"]), float(building["y"])) >= BUILD_MIN_DISTANCE
            for building in self.buildings
        )

    def _quadrant_build_tile(self, quadrant: int) -> tuple[float, float, int] | None:
        """Nearest free plot inside one corner of the square, or None when it is full."""

        center_gx, center_gy = tile_of_x(MARKET_X), tile_of_y(MARKET_Y)
        best: tuple[float, float, int] | None = None
        best_distance: float | None = None
        for gx in range(GRID_TILES_X):
            for gy in range(GRID_TILES_Y):
                x, y = tile_center_unit(gx, gy)
                if not _in_housing_quadrant(x, y) or _quadrant_of(x, y) != quadrant:
                    continue
                if not self._tile_is_free(gx, gy):
                    continue
                distance = math.hypot(gx - center_gx, gy - center_gy)
                if best_distance is None or distance < best_distance:
                    best, best_distance = (x, y, 1), distance
        return best

    def _district_build_tile(self, district_id: int = 1) -> tuple[float, float, int] | None:
        """Nearest free snapped tile to the village square, or None when it is full.

        Village roofs follow the quadrant plan: the four corners around the market,
        never the square itself, the avenues or a neighbour's yard.
        """

        center_x, center_y = DISTRICT_1_CENTER
        center_gx, center_gy = tile_of_x(center_x), tile_of_y(center_y)
        candidates = sorted(
            (
                (math.hypot(gx - center_gx, gy - center_gy), gx, gy)
                for gx in range(GRID_TILES_X)
                for gy in range(GRID_TILES_Y)
            )
        )
        for _, gx, gy in candidates:
            x, y = tile_center_unit(gx, gy)
            if district_id == 1 and not _in_housing_quadrant(x, y):
                continue
            if self._tile_is_free(gx, gy):
                return x, y, district_id
        return None

    # -- market zoning ---------------------------------------------------------

    def _market_housing_counts(self) -> dict[int, int]:
        """How many roofs each counter already carries."""

        counts: dict[int, int] = {int(market["id"]): 0 for market in self.markets}
        for building in self.buildings:
            if building.get("type") != "shelter":
                continue
            market_id = building.get("market_id")
            if market_id is None:
                continue
            counts[int(market_id)] = counts.get(int(market_id), 0) + 1
        return counts

    def _zoned_market_for(
        self, citizen: Citizen, skip: set[int] | frozenset[int] = frozenset()
    ) -> dict[str, Any] | None:
        """The closest counter still under MAX_HOUSES_PER_MARKET, or None when all are full."""

        counts = self._market_housing_counts()
        open_markets = [
            market
            for market in self.markets
            if int(market["id"]) not in skip
            and counts.get(int(market["id"]), 0) < MAX_HOUSES_PER_MARKET
        ]
        if not open_markets:
            return None
        return min(
            open_markets,
            key=lambda market: self._distance(
                citizen.x, citizen.y, float(market["x"]), float(market["y"])
            ),
        )

    def _zoned_build_tile(
        self, market: dict[str, Any], radius: float = MARKET_ZONE_RADIUS
    ) -> tuple[float, float, int] | None:
        """The nearest free plot inside one counter's zone, or None when it is packed."""

        center_x, center_y = float(market["x"]), float(market["y"])
        best: tuple[float, float, int] | None = None
        best_distance: float | None = None
        for gx in range(GRID_TILES_X):
            for gy in range(GRID_TILES_Y):
                x, y = tile_center_unit(gx, gy)
                distance = self._distance(x, y, center_x, center_y)
                if distance > radius or not self._tile_is_free(gx, gy):
                    continue
                if best_distance is None or distance < best_distance:
                    best, best_distance = (x, y, 1), distance
        return best

    def _zone_market_for_point(self, x: float, y: float) -> dict[str, Any]:
        """The counter a roof at (x, y) is zoned to: the closest one whose zone holds it."""

        in_zone = [
            market
            for market in self.markets
            if self._distance(x, y, float(market["x"]), float(market["y"]))
            <= MARKET_ZONE_RADIUS
        ]
        if in_zone:
            return min(
                in_zone,
                key=lambda market: self._distance(
                    x, y, float(market["x"]), float(market["y"])
                ),
            )
        return self._nearest_market(x, y)

    def _market_ground(self, x: float, y: float) -> bool:
        """Free ground for a new counter: inside the map, off a roof, clear of the rest."""

        if not (6.0 <= x <= self.world_width - 6.0 and 6.0 <= y <= self.world_height - 6.0):
            return False
        if any(
            self._distance(x, y, float(market["x"]), float(market["y"]))
            < MARKET_ZONE_RADIUS + 6.0
            for market in self.markets
        ):
            return False
        return all(
            self._distance(x, y, float(building["x"]), float(building["y"])) >= 5.0
            for building in self.buildings
        )

    def _spawn_zoning_market(self, citizen: Citizen) -> dict[str, Any] | None:
        """Open a counter near the builders, because every existing zone is full.

        PART C: this is the second door into the market list and it used to ignore
        MARKET_HARD_CAP entirely. Measured on a 4,000-tick run: the five permitted
        counters filled, and four more opened in nine ticks (market 6 to 9), each
        seeding a fresh ring of houses. The town then had 650 beds for 178 people,
        spent its labour cutting wood, and starved down to 27. Five counters is the
        ceiling, so with every zone packed a roof simply waits for a bed to free up.
        """

        if len(self.markets) >= MARKET_HARD_CAP:
            return None
        best: tuple[float, float] | None = None
        best_distance: float | None = None
        step = 4.0
        x = 6.0
        while x <= self.world_width - 6.0:
            y = 6.0
            while y <= self.world_height - 6.0:
                if self._market_ground(x, y):
                    distance = self._distance(citizen.x, citizen.y, x, y)
                    if best_distance is None or distance < best_distance:
                        best, best_distance = (x, y), distance
                y += step
            x += step
        if best is None:
            return None
        market = {
            "id": self._next_market_id(),
            "x": round(best[0], 1),
            "y": round(best[1], 1),
        }
        self.markets.append(market)
        self.markets.sort(key=lambda entry: int(entry["id"]))
        event = {
            "event": "zone_full",
            "market_id": market["id"],
            "x": market["x"],
            "y": market["y"],
            "population": self.population,
            "tick": self.tick_count + 1,
            "reason": f"every counter already carries {MAX_HOUSES_PER_MARKET} houses",
        }
        self.history.append(event)
        print(
            f"[ZONE] every market full: market {market['id']} opened at "
            f"({market['x']:.0f}, {market['y']:.0f}) at tick {self.tick_count + 1}"
        )
        return market

    def _frontier_house_count(self) -> int:
        """Shelters already standing inside the newest tile."""

        start = (self.tile_count_x - 1) * self.tile_width
        return sum(
            1
            for building in self.buildings
            if building.get("type") == "shelter"
            and float(building["x"]) >= start
        )

    def _market_spacing_ok(self, x: float, y: float, near: dict[int, int]) -> bool:
        """A plot inside a counter's clear ring is open only while that ring is quiet."""

        market = self._nearest_market(x, y)
        if self._distance(x, y, float(market["x"]), float(market["y"])) >= MARKET_CLEAR_RADIUS:
            return True
        return near.get(int(market["id"]), 0) < MAX_HOUSES_NEAR_MARKET

    def _free_build_spot(
        self, citizen: Citizen, building_type: str = "shelter"
    ) -> tuple[float, float, int] | None:
        """A snapped grass tile for a new building, edge of the map first.

        PART C: the search now considers every empty grass tile and sorts them by
        distance from the map centre, furthest first, so citizens clear the forest
        edge and build inward instead of crowding the square. PART B caps a counter's
        clear ring at MAX_HOUSES_NEAR_MARKET roofs, and PART D confines the search to
        the newest tile until it holds FRONTIER_HOUSES_REQUIRED shelters.
        """

        if building_type == "shelter" and self.needs_frontier_build:
            if self._frontier_house_count() >= FRONTIER_HOUSES_REQUIRED:
                self.needs_frontier_build = False

        near: dict[int, int] = {}
        if building_type == "shelter":
            for market in self.markets:
                near[int(market["id"])] = sum(
                    1
                    for building in self.buildings
                    if building.get("type") == "shelter"
                    and self._distance(
                        float(building["x"]),
                        float(building["y"]),
                        float(market["x"]),
                        float(market["y"]),
                    )
                    < MARKET_CLEAR_RADIUS
                )

        frontier_start = (self.tile_count_x - 1) * self.tile_width
        candidates: list[tuple[float, float]] = []
        for gx in range(GRID_TILES_X):
            for gy in range(GRID_TILES_Y):
                spot_x, spot_y = tile_center_unit(gx, gy)
                if (
                    building_type == "shelter"
                    and self.needs_frontier_build
                    and spot_x < frontier_start
                ):
                    continue
                if not self._tile_is_free(gx, gy):
                    continue
                if building_type == "shelter" and not self._market_spacing_ok(
                    spot_x, spot_y, near
                ):
                    continue
                candidates.append((spot_x, spot_y))

        if not candidates:
            return None
        center_x = self.world_width / 2.0
        center_y = self.world_height / 2.0
        candidates.sort(
            key=lambda spot: self._distance(spot[0], spot[1], center_x, center_y),
            reverse=True,
        )
        spot_x, spot_y = candidates[0]
        return spot_x, spot_y, 1

    def _overflow_build_tile(self, citizen: Citizen) -> tuple[float, float, int] | None:
        """PART C: a house must be built, so the zoning cap is ignored.

        Every market zone is packed and no new counter can open. Sweep the whole map
        for the nearest free tile; _tile_is_free already rejects roads, the plaza and
        anything within BUILD_MIN_DISTANCE of a building, so the plot never overlaps
        a road or another roof.
        """

        fallback = self._nearest_free_tile(citizen.x, citizen.y)
        if fallback is None:
            print(
                f"[HOUSING] no free tile anywhere at tick {self.tick_count + 1}: "
                f"{citizen.name} cannot build"
            )
            return None
        overflow_event = {
            "event": "zoning_cap_ignored",
            "id": citizen.id,
            "name": citizen.name,
            "reason": "every market zone is full: roof placed outside the cap",
            "tick": self.tick_count + 1,
        }
        self.history.append(overflow_event)
        print(
            f"[HOUSING] zoning cap ignored at tick {self.tick_count + 1}: "
            f"shelter for {citizen.name} placed at ({fallback[0]:.0f}, {fallback[1]:.0f})"
        )
        return fallback

    def _market_neighborhood_tile(
        self, market: dict[str, Any], radius: float = MARKET_NEIGHBORHOOD_RADIUS
    ) -> tuple[float, float, int] | None:
        """Nearest free plot around a counter, so a new market grows its own block."""

        center_x, center_y = float(market["x"]), float(market["y"])
        best: tuple[float, float, int] | None = None
        best_distance: float | None = None
        for gx in range(GRID_TILES_X):
            for gy in range(GRID_TILES_Y):
                x, y = tile_center_unit(gx, gy)
                distance = self._distance(x, y, center_x, center_y)
                if distance > radius:
                    continue
                if not self._tile_is_free(gx, gy):
                    continue
                if best_distance is None or distance < best_distance:
                    best, best_distance = (x, y, 1), distance
        return best

    def _frontier_build_tile(self, citizen: Citizen) -> tuple[float, float, int] | None:
        """Nearest free plot in the land added by expansion, or None on the base map."""

        if self.world_width <= BASE_WORLD_WIDTH and self.world_height <= BASE_WORLD_HEIGHT:
            return None
        origin_gx, origin_gy = tile_of_x(citizen.x), tile_of_y(citizen.y)
        best: tuple[float, float, int] | None = None
        best_distance: float | None = None
        for gx in range(GRID_TILES_X):
            for gy in range(GRID_TILES_Y):
                x, y = tile_center_unit(gx, gy)
                if x <= BASE_WORLD_WIDTH + 1.0 and y <= BASE_WORLD_HEIGHT + 1.0:
                    # Still the original village: the quadrant plan owns that ground.
                    continue
                if not self._tile_is_free(gx, gy):
                    continue
                distance = math.hypot(gx - origin_gx, gy - origin_gy)
                if best_distance is None or distance < best_distance:
                    best, best_distance = (x, y, 1), distance
        return best

    def _nearest_free_tile(self, x: float, y: float) -> tuple[float, float, int] | None:
        """The closest free plot anywhere on the map, with no plan attached."""

        origin_gx, origin_gy = tile_of_x(x), tile_of_y(y)
        best: tuple[float, float, int] | None = None
        best_distance: float | None = None
        for gx in range(GRID_TILES_X):
            for gy in range(GRID_TILES_Y):
                if not self._tile_is_free(gx, gy):
                    continue
                distance = math.hypot(gx - origin_gx, gy - origin_gy)
                if best_distance is None or distance < best_distance:
                    spot_x, spot_y = tile_center_unit(gx, gy)
                    best, best_distance = (spot_x, spot_y, 1), distance
        return best

    def _build(self, citizen: Citizen, building_type: str) -> dict[str, Any]:
        """Raise a shelter or granary next to the citizen; failures cost nothing."""

        if building_type not in BUILD_COSTS:
            return {
                "action": "build_failed",
                "citizen": citizen.id,
                "event": "build_failed",
                "reason": f"unknown building type '{building_type}' (use shelter or granary)",
            }
        cost = BUILD_COSTS[building_type]
        # PART B: a tile is zoned for HOUSES_PER_TILE roofs. Once every existing tile
        # is full the town must grow east before another roof can go up; that ceiling
        # is what makes "population over beds" the expansion trigger.
        if building_type == "shelter":
            shelters = sum(1 for b in self.buildings if b.get("type") == "shelter")
            if shelters >= self.tile_count_x * HOUSES_PER_TILE:
                return {
                    "action": "build_failed",
                    "citizen": citizen.id,
                    "event": "build_failed",
                    "reason": "every tile is full: the town must expand east first",
                }
        spot = self._free_build_spot(citizen, building_type)
        if spot is None:
            return {
                "action": "build_failed",
                "citizen": citizen.id,
                "event": "build_failed",
                "reason": "no free tile left; move away from other buildings and roads",
            }
        desperate = self.population > self._total_beds()
        if (citizen.wood < cost["wood"] or citizen.coins < cost["coins"]) and not desperate:
            return {
                "action": "build_failed",
                "citizen": citizen.id,
                "event": "build_failed",
                "reason": (
                    f"{building_type} costs {cost['wood']} wood + {cost['coins']} coins; "
                    f"you have {citizen.wood} wood, {citizen.coins} coins"
                ),
            }

        # A town short of beds may pay only what it has: the roof is partly subsidised
        # rather than borrowing coins that do not exist, so no purse goes negative.
        citizen.wood = max(0, citizen.wood - cost["wood"])
        citizen.coins -= min(citizen.coins, cost["coins"])
        x, y, district_id = spot
        building = {
            "id": f"b{len(self.buildings) + 1}",
            "type": building_type,
            "x": float(x),
            "y": float(y),
            "district_id": district_id,
            # The counter this house belongs to, frozen at build time. Everyone who
            # lives here shops at it, however far they wander.
            "market_id": int(self._zone_market_for_point(x, y)["id"]),
            "owner_id": citizen.id,
            "built_tick": self.tick_count + 1,
        }
        self.buildings.append(building)
        if building_type == "granary":
            citizen.storage_bonus += 5
        if building_type == "shelter":
            # The builder moves in first, then up to four other homeless villagers.
            self._assign_home(building, citizen)

        entry = {
            "event": "built",
            "id": building["id"],
            "type": building_type,
            "x": building["x"],
            "y": building["y"],
            "district": district_id,
            "tick": building["built_tick"],
            "citizen": citizen.id,
        }
        self.history.append(entry)
        try:
            persistence.save_building(building)
        except Exception as error:
            _LOGGER.warning("building not persisted: %s", error)
        return entry

    def _tile_node_positions(self, tile_number: int, count: int) -> list[tuple[float, float]]:
        """A spread-out grid of node spots inside one 100 x 100 tile."""

        left = (tile_number - 1) * self.tile_width
        columns = 8
        rows = max(1, math.ceil(count / columns))
        margin = 8.0
        x_step = (self.tile_width - 2.0 * margin) / (columns - 1)
        y_step = (self.tile_height - 2.0 * margin) / max(1, rows - 1)
        positions: list[tuple[float, float]] = []
        for index in range(count):
            row, column = divmod(index, columns)
            x = left + margin + column * x_step + self.rng.uniform(-1.5, 1.5)
            y = margin + row * y_step + self.rng.uniform(-1.5, 1.5)
            positions.append(
                (
                    round(min(self.world_width - 1.0, max(left + 1.0, x)), 1),
                    round(min(self.world_height - 1.0, max(0.0, y)), 1),
                )
            )
        return positions

    def _append_tile_nodes(
        self, tile_number: int, node_type: str, count: int, skip: int = 0
    ) -> list[str]:
        """Append resource nodes to an existing tile and return their ids."""

        spawned: list[str] = []
        for x, y in self._tile_node_positions(tile_number, count)[skip:]:
            node_id = f"{node_type}-{self._next_node_index(node_type)}"
            self.resource_nodes.append(
                {
                    "id": node_id,
                    "type": node_type,
                    "x": x,
                    "y": y,
                    "amount": NODE_AMOUNT,
                    "depleted": False,
                }
            )
            spawned.append(node_id)
        return spawned

    def _ensure_specialized_nodes(self) -> None:
        """Make Tile 1 wood-only and Tile 2 grain-only, including old saves.

        Existing wrong-type nodes are removed from those two tiles; any shortage is
        topped up to the full 32, so the resource geography stays consistent after
        a restart instead of reflecting the old mixed map.
        """

        kept: list[dict[str, Any]] = []
        for node in self.resource_nodes:
            tile = self._tile_number_at(float(node.get("x", 0.0)))
            spec = SPECIALIZED_TILE_NODES.get(tile)
            if spec is not None and node.get("type") != spec[0]:
                continue
            kept.append(dict(node))
        self.resource_nodes = kept

        for tile, (node_type, count) in SPECIALIZED_TILE_NODES.items():
            tile_start = (tile - 1) * self.tile_width
            if tile_start >= self.world_width:
                continue
            have = sum(
                1
                for node in self.resource_nodes
                if node.get("type") == node_type
                and tile_start <= float(node.get("x", -1.0)) < tile_start + self.tile_width
            )
            if have < count:
                self._append_tile_nodes(tile, node_type, count, skip=have)

    def _spawn_nodes(self) -> list[dict[str, Any]]:
        """A fresh world opens with 24 wood and 8 starter grain fields.

        Tile 1 used to be wood-only and the east farmland opened at population 10.
        Holding the map at 100 x 100 until population 150 requires a small food
        source on the starting tile; the full 32-field grain tile still arrives with
        the 200 x 100 expansion.
        """

        positions = self._tile_node_positions(1, TILE_NODE_COUNT)
        nodes: list[dict[str, Any]] = []
        for index, (x, y) in enumerate(positions, start=1):
            node_type = "grain" if index > TILE_NODE_COUNT - 8 else "wood"
            nodes.append(
                {
                    "id": f"{node_type}-{index}",
                    "type": node_type,
                    "x": x,
                    "y": y,
                    "amount": NODE_AMOUNT,
                    "depleted": False,
                }
            )
        return nodes

    def _regrow_nodes(self, tick_number: int) -> list[dict[str, Any]]:
        """Every ten ticks the fields and woods put back some of what was taken.

        A fixed 400-grain map fed a village for about four hundred ticks; regrowth
        is what makes a large population's scaled harvest sustainable.
        """

        if tick_number % NODE_REGROWTH_INTERVAL != 0:
            return []
        events: list[dict[str, Any]] = []
        for node in self.resource_nodes:
            if node["amount"] >= NODE_AMOUNT:
                continue
            was_depleted = bool(node["depleted"])
            node["amount"] = min(NODE_AMOUNT, node["amount"] + NODE_REGROWTH_AMOUNT)
            node["depleted"] = node["amount"] <= 0
            if was_depleted and not node["depleted"]:
                event = {
                    "event": "node_recovered",
                    "id": node["id"],
                    "amount": node["amount"],
                    "tick": tick_number,
                }
                self.history.append(event)
                events.append(event)
        return events

    # -- map expansion ---------------------------------------------------------

    def set_world_size(self, width: float, height: float) -> None:
        """Resize the map in one place, so bounds, tile grid and instance agree."""

        global WORLD_WIDTH, WORLD_HEIGHT, GRID_TILES_X, GRID_TILES_Y, GRID_TILES
        WORLD_WIDTH, WORLD_HEIGHT = float(width), float(height)
        GRID_TILES_X = max(1, round(WORLD_WIDTH * PX_PER_UNIT / TILE_PX))
        GRID_TILES_Y = max(1, round(WORLD_HEIGHT * PX_PER_UNIT / TILE_PX))
        GRID_TILES = GRID_TILES_X
        self.world_width = WORLD_WIDTH
        self.world_height = WORLD_HEIGHT

    def _total_beds(self) -> int:
        """Every bed under every roof in the settlement."""

        return HOME_CAPACITY * sum(
            1 for building in self.buildings if building.get("type") == "shelter"
        )

    def _next_market_id(self) -> int:
        """The next free counter number, so a new market never reuses an old id."""

        return max((int(market.get("id", 0)) for market in self.markets), default=0) + 1

    def _check_market_expansion(self) -> list[dict[str, Any]]:
        """Open another counter only when a counter is full and the town is big.

        PART B: a counter used to arrive at population 30/65/95 whether or not the
        previous one had room, and every map expansion appended one too, so a
        4,000-tick run carried 14 counters for 500 people. A counter now needs a
        town of MARKET_MIN_POPULATION and an existing counter already holding
        MAX_HOUSES_PER_MARKET roofs. One counter per tick at most.
        """

        events: list[dict[str, Any]] = []
        # PART C: never more than five counters, however full they are.
        if len(self.markets) >= MARKET_HARD_CAP:
            return events
        if self.population < MARKET_MIN_POPULATION:
            return events
        counts = self._market_housing_counts()
        if not any(
            counts.get(int(market["id"]), 0) >= MAX_HOUSES_PER_MARKET
            for market in self.markets
        ):
            return events
        for milestone, x, y in MARKET_FOUNDINGS:
            if self.population < milestone:
                continue
            # Counter ids follow opening order (zoning can open one first), so a
            # milestone is already served when a counter stands on its corner.
            if any(
                self._distance(float(market["x"]), float(market["y"]), x, y)
                <= MARKET_ZONE_RADIUS
                for market in self.markets
            ):
                continue
            market_id = self._next_market_id()
            self.markets.append({"id": market_id, "x": x, "y": y})
            self.markets.sort(key=lambda entry: int(entry["id"]))
            event = {
                "event": "market_founded",
                "id": market_id,
                "x": x,
                "y": y,
                "tick": self.tick_count + 1,
                "population": self.population,
            }
            self.history.append(event)
            events.append(event)
            print(
                f"[MARKET] market {market_id} opened at ({x:.0f}, {y:.0f})"
                f" at tick {self.tick_count + 1} (pop {self.population})",
                flush=True,
            )
            # One counter per tick: a milestone backlog cannot open three at once.
            break

        # Zoning lockout: the four corner counters carry MAX_HOUSES_PER_MARKET roofs
        # each, so past FRONTIER_MARKET_HOUSE_TRIGGER roofs no new house may be zoned
        # and the town stops growing. Open a frontier counter on free land instead.
        houses = sum(1 for building in self.buildings if building.get("type") == "shelter")
        if houses < FRONTIER_MARKET_HOUSE_TRIGGER:
            return events
        # Test capacity, not len(self.markets) == 4: map expansion can open a fifth
        # counter before the corner blocks fill, and a literal count test never fires
        # while the town stays locked at 40 roofs. Any town with no spare zoning room
        # gets a frontier counter.
        counts = self._market_housing_counts()
        if not all(
            counts.get(int(market["id"]), 0) >= MAX_HOUSES_PER_MARKET
            for market in self.markets
        ):
            return events
        spot = self._free_market_spot()
        if spot is None:
            # No free ground far enough from every counter: the map must expand first.
            return events
        x, y = spot
        market_id = self._next_market_id()
        self.markets.append({"id": market_id, "x": x, "y": y})
        self.markets.sort(key=lambda entry: int(entry["id"]))
        event = {
            "event": "market_founded",
            "id": market_id,
            "x": x,
            "y": y,
            "tick": self.tick_count + 1,
            "population": self.population,
            "houses": houses,
            "frontier": True,
        }
        self.history.append(event)
        events.append(event)
        print(
            f"[MARKET] frontier market {market_id} opened at ({x:.0f}, {y:.0f})"
            f" at tick {self.tick_count + 1} ({houses} houses)"
        )
        return events

    def _free_market_spot(self) -> tuple[float, float] | None:
        """A random free tile far enough from every counter to own its own zone."""

        free: list[tuple[float, float]] = []
        for gx in range(GRID_TILES_X):
            for gy in range(GRID_TILES_Y):
                if self._tile_is_free(gx, gy):
                    free.append(tile_center_unit(gx, gy))
        candidates = [
            (x, y)
            for x, y in free
            if all(
                self._distance(x, y, float(market["x"]), float(market["y"]))
                > MARKET_ZONE_RADIUS
                for market in self.markets
            )
        ]
        self.rng.shuffle(candidates)
        for x, y in candidates:
            # Only a counter with at least one free plot in its own zone is worth opening.
            if any(
                other != (x, y)
                and self._distance(x, y, other[0], other[1]) <= MARKET_ZONE_RADIUS
                for other in free
            ):
                return x, y
        return None

    def _check_map_expansion(self) -> list[dict[str, Any]]:
        """Staggered growth: 60 -> tile 2, 150 -> tile 3, 300 -> tile 4."""

        if self.tile_count_x == 1 and self.population > 60:
            return [self._expand_world(self._total_beds())]
        if self.tile_count_x == 2 and self.population > 150:
            return [self._expand_world(self._total_beds())]
        if self.tile_count_x == 3 and self.population > 300:
            return [self._expand_world(self._total_beds())]
        return []

    def _expand_world(self, beds: int) -> dict[str, Any]:
        """PART B: add one 100 x 100 tile east, with a market, fields and a road.

        The new tile is a self-contained block: one market at (new_width - 50, 50),
        sixteen grain and sixteen wood nodes strictly inside its bounds, and the
        existing avenues extended into it so the town can walk to the new land.
        """

        old_width = self.world_width
        self.tile_count_x += 1
        self.set_world_size(self.tile_count_x * self.tile_width, self.tile_height)
        new_x = self.tile_count_x * self.tile_width - self.tile_width / 2.0
        new_y = self.tile_height / 2.0

        market_id = self._next_market_id()
        self.markets.append({"id": market_id, "x": new_x, "y": new_y})
        self.markets.sort(key=lambda entry: int(entry["id"]))

        # Roads: extend the east-west avenue into the new land and run a north-south
        # street through the new market, so the tiles are physically connected.
        old_gx = max(1, round(old_width * PX_PER_UNIT / TILE_PX))
        center_gx = max(0, min(GRID_TILES_X - 1, int(new_x * PX_PER_UNIT // TILE_PX)))
        for row in ROAD_ROWS:
            for column in range(old_gx, GRID_TILES_X):
                self.road_tiles.add((column, row))
        for column in (center_gx - 1, center_gx):
            if 0 <= column < GRID_TILES_X:
                for row in range(GRID_TILES_Y):
                    self.road_tiles.add((column, row))

        spawned = self._spawn_tile_nodes(old_width)
        self.last_expansion_tick = self.tick_count
        self.expansion_count += 1
        # PART D: the new tile must be settled before building resumes elsewhere.
        self.needs_frontier_build = True
        event = {
            "event": "world_expanded",
            "tick": self.tick_count + 1,
            "tile": self.tile_count_x,
            "new_width": self.world_width,
            "new_height": self.world_height,
            "population": self.population,
            "beds": beds,
            "market": market_id,
            "market_x": new_x,
            "market_y": new_y,
            "nodes": spawned,
        }
        self.history.append(event)
        print(
            f"[EXPAND] tile {self.tile_count_x} added: world {self.world_width:.0f} x "
            f"{self.world_height:.0f} at tick {self.tick_count} (pop {self.population}, "
            f"{beds} beds, market {market_id} at {new_x:.0f},{new_y:.0f})"
        )
        return event

    def _spawn_tile_nodes(self, old_width: float) -> list[str]:
        """Spawn the resources of the tile just added.

        Tile 2 is the grain tile: 32 grain and no wood. Later tiles keep a balanced
        16 grain + 16 wood grid so the town can still grow beyond the first pair.
        """

        if self.tile_count_x == 2:
            return self._append_tile_nodes(2, "grain", TILE_NODE_COUNT)

        spawned: list[str] = []
        column_step = (self.tile_width - 24.0) / 3.0
        for node_type in ("wood", "grain"):
            rows = (6.0, 18.0, 30.0, 42.0) if node_type == "wood" else (58.0, 70.0, 82.0, 94.0)
            for row_index, row_y in enumerate(rows):
                for column_index in range(4):
                    x = old_width + 12.0 + column_index * column_step
                    y = row_y + (2.0 if (row_index + column_index) % 2 else -2.0)
                    node_id = f"{node_type}-{self._next_node_index(node_type)}"
                    self.resource_nodes.append(
                        {
                            "id": node_id,
                            "type": node_type,
                            "x": round(x, 1),
                            "y": round(y, 1),
                            "amount": NODE_AMOUNT,
                            "depleted": False,
                        }
                    )
                    spawned.append(node_id)
        return spawned

    def _next_node_index(self, node_type: str) -> int:
        """The next free grain- or wood-N number, so ids never collide."""

        taken = 0
        for node in self.resource_nodes:
            if node.get("type") != node_type:
                continue
            try:
                taken = max(taken, int(str(node.get("id", "")).split("-")[-1]))
            except ValueError:
                continue
        return taken + 1

    def _expansion_node_positions(
        self, old_width: float, old_height: float
    ) -> dict[str, list[tuple[float, float]]]:
        """Spread the new fields over the whole band of land just added.

        A grid of candidate cells runs down the new eastern strip and across the new
        southern strip; each node takes the cell farthest from every other field on
        the map, so the woods and the fields ring the new market instead of piling
        into one corner. Wood stays north of the square, grain south, as before.
        """

        width, height = self.world_width, self.world_height
        half = height / 2.0
        steps = 6
        candidates: list[tuple[float, float]] = []
        for column in range(steps):
            for row in range(steps):
                candidates.append(
                    (
                        old_width + (column + 0.5) * (width - old_width) / steps,
                        (row + 0.5) * height / steps,
                    )
                )
                candidates.append(
                    (
                        (column + 0.5) * old_width / steps,
                        old_height + (row + 0.5) * (height - old_height) / steps,
                    )
                )

        placed = [(float(node["x"]), float(node["y"])) for node in self.resource_nodes]
        chosen: dict[str, list[tuple[float, float]]] = {"wood": [], "grain": []}
        for node_type in ("wood", "grain"):
            for _ in range(MAP_EXPANSION_NODES):
                pool = [
                    (x, y)
                    for x, y in candidates
                    if (node_type == "wood" and y < half - 5.0)
                    or (node_type == "grain" and y > half + 5.0)
                ]
                if not pool:
                    chosen[node_type].append(
                        self._expansion_node_position(node_type, old_width, old_height)
                    )
                    continue
                best = max(
                    pool,
                    key=lambda point: min(
                        (math.hypot(point[0] - x, point[1] - y) for x, y in placed),
                        default=float(width),
                    ),
                )
                candidates.remove(best)
                placed.append(best)
                chosen[node_type].append(
                    (
                        round(best[0] + self.rng.uniform(-2.0, 2.0), 1),
                        round(best[1] + self.rng.uniform(-2.0, 2.0), 1),
                    )
                )
        return chosen

    def _expansion_node_position(
        self, node_type: str, old_width: float, old_height: float
    ) -> tuple[float, float]:
        """A node in the land that was just added, not back in the old village."""

        half = self.world_height / 2.0
        for _ in range(300):
            x = self.rng.uniform(0.0, self.world_width)
            if node_type == "wood":
                y = self.rng.uniform(0.0, max(1.0, half - 5.0))
            else:
                y = self.rng.uniform(min(half + 5.0, self.world_height), self.world_height)
            if x < old_width and y < old_height:
                # Both coordinates inside the old map: that land already has fields.
                continue
            if all(
                math.hypot(x - node["x"], y - node["y"]) >= NODE_MIN_DISTANCE
                for node in self.resource_nodes
            ):
                return round(x, 1), round(y, 1)
        return round(self.rng.uniform(0.0, self.world_width), 1), round(
            self.rng.uniform(0.0, self.world_height), 1
        )

    def _free_node_position(
        self, nodes: list[dict[str, Any]], node_type: str = "grain"
    ) -> tuple[int, int]:
        """A node in its own half of the map: wood north of the square, grain south."""

        if node_type == "wood":
            y_low, y_high = 0, max(1, int(WORLD_HEIGHT / 2) - 5)
        else:
            y_low, y_high = min(int(WORLD_HEIGHT / 2) + 5, WORLD_HEIGHT), WORLD_HEIGHT
        for _ in range(500):
            x = self.rng.randint(0, WORLD_WIDTH)
            y = self.rng.randint(y_low, y_high)
            if all(
                math.hypot(x - node["x"], y - node["y"]) >= NODE_MIN_DISTANCE
                for node in nodes
            ):
                return x, y
        return self.rng.randint(0, WORLD_WIDTH), self.rng.randint(y_low, y_high)

    @staticmethod
    def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
        return math.hypot(x1 - x2, y1 - y2)

    def _nearest_node(self, citizen: Citizen, resource: str) -> dict[str, Any] | None:
        candidates = [
            node for node in self.resource_nodes if node["type"] == resource and not node["depleted"]
        ]
        if not candidates:
            return None
        # Plain nearest-neighbour selection sent the whole crowd to one field: every
        # farmer computed the same minimum and marched to the same pixel. The
        # occupancy term makes a lightly used node win over a crowded one.
        return min(
            candidates,
            key=lambda node: self._distance(citizen.x, citizen.y, node["x"], node["y"])
            + NODE_OCCUPANCY_PENALTY * self._node_pressure(node),
        )

    def _node_pressure(self, node: dict[str, Any]) -> int:
        """How many living villagers are already standing at this node."""

        return sum(
            1
            for other in self.citizens
            if other.alive
            and self._distance(other.x, other.y, node["x"], node["y"]) <= GATHER_RADIUS
        )

    def _move_toward(self, citizen: Citizen, node: dict[str, Any], reason: str) -> dict[str, Any]:
        distance = self._distance(citizen.x, citizen.y, node["x"], node["y"])
        if distance > 0:
            step = min(self._citizen_speed(citizen), distance)
            citizen.x += (node["x"] - citizen.x) / distance * step
            citizen.y += (node["y"] - citizen.y) / distance * step
        return {
            "citizen": citizen.id,
            "event": "move",
            "id": citizen.id,
            "toward": node["id"],
            "reason": reason,
            "x": round(citizen.x, 1),
            "y": round(citizen.y, 1),
        }

    def _gather(self, citizen: Citizen, resource: str) -> dict[str, Any]:
        """Gather only works inside GATHER_RADIUS; otherwise the citizen walks to the node."""

        node = self._nearest_node(citizen, resource)
        if node is None:
            return {
                "citizen": citizen.id,
                "event": "gather_failed",
                "resource": resource,
                "reason": "no living nodes of that type",
            }
        spot_x, spot_y = self._gather_spot(citizen, node)
        # A fresh offset every approach so villagers arrive at the node from all
        # directions instead of tracing one shared path in.
        approach_x = self._clamp(spot_x + self.rng.uniform(-GATHER_SPREAD, GATHER_SPREAD))
        approach_y = self._clamp(spot_y + self.rng.uniform(-GATHER_SPREAD, GATHER_SPREAD))
        if self._distance(citizen.x, citizen.y, node["x"], node["y"]) > GATHER_RADIUS:
            approach = {**node, "x": approach_x, "y": approach_y}
            return self._move_toward(citizen, approach, reason=f"gather {resource}")
        # Everyone stands on their own place in the ring around the node instead of
        # on the centre pixel, so a crowd of gatherers never collapses into a stack.
        citizen.x, citizen.y = spot_x, spot_y
        return self._gather_from_node(citizen, resource, node)

    def _gather_spot(self, citizen: Citizen, node: dict[str, Any]) -> tuple[float, float]:
        """A fixed standing place for one villager around one node.

        The slot comes from the citizen id and turns by the golden angle, so
        neighbours in the id list land on opposite sides of the node rather than
        jostling for the same pixel, and a villager keeps the same place every trip.
        """

        digits = "".join(ch for ch in str(citizen.id) if ch.isdigit())
        slot = int(digits) if digits else sum(ord(ch) for ch in str(citizen.id))
        angle = math.radians((slot * 137.508) % 360.0)
        # PART C: spread the standing ring over most of GATHER_RADIUS. A tight
        # 2-3.8 unit ring put every farmer on one node within 10 units of every
        # other farmer; a 2.5-7.5 unit ring gives the crowd room to breathe while
        # staying inside the radius that still counts as "at the node".
        radius = 2.5 + (slot % 10) * 0.55
        return (
            self._clamp(float(node["x"]) + math.cos(angle) * radius),
            self._clamp(float(node["y"]) + math.sin(angle) * radius),
        )

    def _harvest_yield(self, resource: str, citizen: Citizen | None = None) -> int:
        """Four per trip for an adult, one for a child, halved while a market is glutted.

        Grain used to scale with the village (max(2, population // 5)), which let a big
        town feed a private hoard without ever selling; a flat yield keeps the fields
        and the shelves in step. The yield also has to answer the shelves: once a
        market holds more than MARKET_GLUT_SUPPLY of a resource, a trip brings back
        half, so gathering cannot keep flooding it.

        PART C (Phase 93): the flat two made every child a net loss. A town of 213
        children and 19 adults needed 232 grain a tick and could not bring it in.
        Strength now sets the load: an adult carries ADULT_GATHER_YIELD, a child
        CHILD_GATHER_YIELD, so 19 adults work like 76 children.
        """

        base = GATHER_YIELD
        if citizen is not None:
            base = ADULT_GATHER_YIELD if citizen.age >= ADULT_MIN_AGE else CHILD_GATHER_YIELD
        supply = getattr(self, f"{resource}_supply")
        if supply > MARKET_GLUT_SUPPLY:
            return max(1, base // 2)
        return base

    def _gather_from_node(self, citizen: Citizen, resource: str, node: dict[str, Any]) -> dict[str, Any]:
        # The harvest itself happens on this villager's own place in the ring, so a
        # crowd at one node ends up spread around it instead of on the centre pixel.
        citizen.x, citizen.y = self._gather_spot(citizen, node)
        per_trip = self._harvest_yield(resource, citizen)
        take = min(per_trip, node["amount"])
        node["amount"] -= take
        if node["amount"] <= 0:
            node["amount"] = 0
            node["depleted"] = True
        setattr(citizen, resource, getattr(citizen, resource) + take)
        # Basic income on every harvest: produce is still only worth full price once
        # sold (see _sell), but a broke villager has to be able to earn the fare that
        # buys food. This is what broke the starve-beside-grain loop from Phase 80.
        citizen.coins += GATHER_WAGE
        # Gathering is the apprenticeship: the first harvest defines the job.
        citizen.job = JOB_BY_RESOURCE.get(resource, citizen.job)

        event = {
            "citizen": citizen.id,
            "event": "gathered",
            "resource": resource,
            "node": node["id"],
            "took": take,
            "amount": node["amount"],
            "depleted": node["depleted"],
            "wage": GATHER_WAGE,  # token pay per trip; the full wage is paid on sale
            "coins": citizen.coins,
        }
        event["yield"] = per_trip
        if take < per_trip:
            event["event"] = "gather_warning"
            event["message"] = "node too depleted for a full gather; took what was left"
        return event

    def _wander(self, citizen: Citizen, event_name: str = "rest") -> dict[str, Any]:
        """Rest and wander always drift two units, unless a starving citizen is foraging."""

        if citizen.grain == 0 and citizen.hunger > EAT_THRESHOLD:
            node = self._nearest_node(citizen, "grain")
            if node is not None:
                if self._distance(citizen.x, citizen.y, node["x"], node["y"]) > GATHER_RADIUS:
                    return self._move_toward(citizen, node, reason="foraging")
                return self._gather_from_node(citizen, "grain", node)

        angle = self.rng.uniform(0.0, math.tau)
        citizen.x = min(WORLD_WIDTH, max(0.0, citizen.x + math.cos(angle) * WANDER_STEP))
        citizen.y = min(WORLD_HEIGHT, max(0.0, citizen.y + math.sin(angle) * WANDER_STEP))
        return {
            "citizen": citizen.id,
            "event": event_name,
            "id": citizen.id,
            "x": round(citizen.x, 1),
            "y": round(citizen.y, 1),
        }

    def _surplus_price(self, resource: str, supply: int) -> float:
        """Force a surplus grain market down to MIN_PRICE before a trade is priced.

        20 coins for grain while 1,600 units sat unsold kept every broke villager
        broke; the price now follows the stock instead of ignoring it.
        """

        price = float(getattr(self, f"{resource}_price"))
        if resource == "grain" and supply > SURPLUS_SUPPLY:
            price = float(MIN_PRICE)
            self.grain_price = price
        return price

    def _buy(self, citizen: Citizen, resource: str) -> dict[str, Any]:
        price = self._surplus_price(resource, getattr(self, f"{resource}_supply"))
        supply = getattr(self, f"{resource}_supply")
        if supply <= 0 or citizen.coins < price:
            return {
                "citizen": citizen.id,
                "event": "buy_rejected",
                "resource": resource,
                "price": price,
                "reason": "insufficient_funds" if citizen.coins < price else "no_supply",
            }

        # Grain is bought in bulk so the walk home does not end in starvation.
        if resource == "grain" and price > 0:
            amount = min(BULK_BUY_AMOUNT, supply, int(citizen.coins // price))
        else:
            amount = 1
        if amount < 1:
            return {"citizen": citizen.id, "event": "buy_rejected", "resource": resource, "price": price}
        total = round(price * amount, 2)
        citizen.coins -= total
        setattr(citizen, resource, getattr(citizen, resource) + amount)
        setattr(self, f"{resource}_supply", supply - amount)
        # Per unit, so a bulk purchase moves the price as far as a batch sale does.
        setattr(
            self, f"{resource}_price", min(MAX_PRICE, round(price + PRICE_IMPACT * amount, 2))
        )
        market = self._citizen_market(citizen)
        market_x, market_y = float(market["x"]), float(market["y"])
        return {
            "citizen": citizen.id,
            "name": citizen.name,
            "event": "bought",
            "resource": resource,
            "price": price,
            "amount": amount,
            "total": total,
            "coins": citizen.coins,
            "market_x": round(market_x),
            "market_y": round(market_y),
        }

    def _trade(self, citizen: Citizen, resource: str, action: dict[str, Any], tick_number: int) -> dict[str, Any]:
        """Barter directly with another villager: give ``offer``, receive ``resource``.

        A partner must be able to pay the wanted amount out of surplus and must be
        short of the offered resource, so both sides end up better fed or stocked.
        """

        offer = str(action.get("offer") or "wood").lower()
        if offer not in RESOURCES or resource not in RESOURCES or offer == resource:
            return {"citizen": citizen.id, "event": "trade_rejected", "resource": resource, "offer": offer, "reason": "invalid_pair"}
        try:
            offer_amount = max(1, int(action.get("amount", TRADE_OFFER_DEFAULT)))
            want_amount = max(1, int(action.get("want", TRADE_WANT_DEFAULT)))
        except (TypeError, ValueError):
            return {"citizen": citizen.id, "event": "trade_rejected", "resource": resource, "offer": offer, "reason": "invalid_amount"}
        if getattr(citizen, offer) < offer_amount:
            return {"citizen": citizen.id, "event": "trade_rejected", "resource": resource, "offer": offer, "reason": "missing_offer"}

        partner = next(
            (
                other
                for other in sorted(self.citizens, key=lambda candidate: (candidate.hunger, candidate.id))
                if other.alive
                and other.id != citizen.id
                and getattr(other, resource) > want_amount
                and getattr(other, offer) < offer_amount
            ),
            None,
        )
        if partner is None:
            return {"citizen": citizen.id, "event": "trade_rejected", "resource": resource, "offer": offer, "reason": "no_partner"}

        setattr(citizen, offer, getattr(citizen, offer) - offer_amount)
        setattr(citizen, resource, getattr(citizen, resource) + want_amount)
        setattr(partner, resource, getattr(partner, resource) - want_amount)
        setattr(partner, offer, getattr(partner, offer) + offer_amount)
        # Barter happens at the counter whose zone the trader lives in, so the
        # viewer's 💰 lands on that market instead of the old square.
        market = self._citizen_market(citizen)
        trade = {
            "event": "traded",
            "id": citizen.id,
            "with": partner.id,
            "name": partner.name,
            "gave": offer,
            "gave_amount": offer_amount,
            "got": resource,
            "got_amount": want_amount,
            "market_x": round(float(market["x"])),
            "market_y": round(float(market["y"])),
            "tick": tick_number,
        }
        self.history.append(trade)
        return {"citizen": citizen.id, **trade}

    def _sell(self, citizen: Citizen, resource: str) -> dict[str, Any]:
        price = self._surplus_price(resource, getattr(self, f"{resource}_supply"))
        # During a grain crisis the central bank pays double to pull private hoards
        # onto the market shelf.
        if resource == "grain" and self.grain_buyback_active:
            price *= 2
        supply = getattr(self, f"{resource}_supply")
        if getattr(citizen, resource) <= 0:
            return {"citizen": citizen.id, "event": "sell_rejected", "resource": resource, "price": price}

        # Sell in batches: one market trip has to be worth the walk.
        amount = min(SELL_BATCH, getattr(citizen, resource))
        # The wage is earned here, on a completed sale; a harvest on its own pays 0.
        citizen.coins += price * amount + WAGE
        setattr(citizen, resource, getattr(citizen, resource) - amount)
        setattr(self, f"{resource}_supply", supply + amount)
        # Symmetric with _buy: PRICE_IMPACT per unit, not one point per unit. A
        # three-unit sale used to cut the price three times as fast as a three-unit
        # purchase raised it, which drove every market down to MIN_PRICE.
        setattr(
            self,
            f"{resource}_price",
            max(MIN_PRICE, round(price - PRICE_IMPACT * amount, 2)),
        )
        market = self._citizen_market(citizen)
        market_x, market_y = float(market["x"]), float(market["y"])
        return {
            "citizen": citizen.id,
            "event": "sold",
            "resource": resource,
            "price": price,
            "amount": amount,
            "paid": price * amount,
            "coins": citizen.coins,
            "market_x": round(market_x),
            "market_y": round(market_y),
        }


def new_world() -> World:
    """Fresh world state; the server uses this for POST /reset."""

    return World()
