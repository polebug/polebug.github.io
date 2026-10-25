"""Shared dimensions of the companion house (metres, Z up).

Origin = centre of the front face of the house at ground level; the house opens toward -Y.
Used by build_whitebox.py (stage 1) and build_architecture.py (stage 2). Values were fixed in
whitebox v2, approved 2026-10-19; see docs/3d-modeling-plan.md section 3.
"""
import math

HALF_W = 5.0            # outer face of the corner posts
POST = 0.28
WALL_T = 0.14
DEPTH = 5.0             # front plane -> interior face of back wall
IN_X = HALF_W - POST    # interior face of the side walls (4.72)
BASE_H = 0.5            # stone plinth
FLOOR = {1: 0.60, 2: 2.95, 3: 5.30}   # top of each floor
SLAB = 0.26             # floor 2/3 slab + beam depth
CLEAR = 2.09            # floor top -> slab underside (floors 1, 2)
RIDGE = 9.18            # roof top at the ridge
PITCH = math.radians(27)
ROOF_T = 0.28
EAVE_X = 5.95           # horizontal reach of the roof each side
OVER_F, OVER_B = 1.0, 0.6
CHAR_H = 1.35

# roof carrying chain: deck -> purlins -> front truss / back gable -> posts
PURLIN = 0.24
EAVE_PX = HALF_W - POST / 2
MID_PX = 2.6
RAFTER = 0.22           # principal rafters of the front truss
COLLAR = FLOOR[3] + 2.2
TRUSS_Y = POST / 2

# window openings: back wall (x0, x1, sill, head) above each floor; side walls centre y per floor
# 10-20: floor-1 back window enlarged for daylight (user): 2.8 x 1.53 m instead of 1.3 x 1.1 m
# floors 2-3 enlarged the same day (user: big windows on every floor)
WIN_BACK = {1: (-4.15, -1.35, 0.45, 1.98), 2: (-2.2, 1.9, 0.45, 1.98), 3: (-1.6, 1.4, 0.75, 1.95)}
# 10-20: the floor-1 left window was removed (user): the TV hangs on that wall now
SIDE_WIN = {(1, 1): 2.75, (2, -1): 2.0, (2, 1): 3.4}
SIDE_WIN_W, SIDE_WIN_SILL, SIDE_WIN_HEAD = 0.8, 0.8, 1.85
SIDE_WIN_SILL_AT = {(1, 1): 0.98}   # kitchen window sits above the 0.84 m side counter
SIDE_WIN_W_AT = {(1, 1): 1.5, (2, -1): 1.4, (2, 1): 1.4}   # 10-20: widened for daylight (user)
SIDE_WIN_HEAD_AT = {(1, 1): 1.98, (2, -1): 1.98, (2, 1): 1.98}


def side_win_w(f, sx):
    return SIDE_WIN_W_AT.get((f, sx), SIDE_WIN_W)


def side_win_head(f, sx):
    return SIDE_WIN_HEAD_AT.get((f, sx), SIDE_WIN_HEAD)


def side_win_sill(f, sx):
    return SIDE_WIN_SILL_AT.get((f, sx), SIDE_WIN_SILL)

# flues: fireplace chimney (back-left corner); kitchen hood duct
FX, FW, FD = -4.12, 0.6, 0.5
# 10-20 refit: the cast-iron range and its external steel flue are gone; a built-in cooktop with a
# stainless hood stands at SX and the hood's duct leaves through the back wall at (FLUE_X, FLUE_Z)
# into a louvred vent cap (no flue up the wall any more)
SX = 1.95               # cooktop / hood centre
FLUE_X = SX             # hood duct through the back wall
# work heights, lowered on 10-19 (footprints unchanged); worktops stay a little above the tables
TABLE_H = 0.68          # dining table and desk
COUNTER_H = 0.78        # kitchen worktops, range and island
BAR_STOOL_H = 0.56      # island stools
FLUE_Z = 1.86           # height above floor 1 of the hood duct (inside the wall cabinet over the hood)


def roof_under(x):
    """Roof deck underside height at |x| (top of the purlins)."""
    return RIDGE - ROOF_T / math.cos(PITCH) - math.tan(PITCH) * abs(x)


def roof_top(x):
    return RIDGE - math.tan(PITCH) * abs(x)


def chimney_top():
    """0.9 m above where it leaves the roof and 0.6 m above any roof within 3 m."""
    return max(roof_top(FX + FW / 2) + 0.9, roof_top(FX + FW / 2 + 3.0) + 0.6)
