#!/usr/bin/env python3
"""Sorter Mk2 card-drop simulation (2D rigid bodies, pymunk).

Two cross-sections:
  bed   (y-z, side view): the card slides off the 30 degree scan bed when the stop drops and must
        land flat in the sort tray's pocket.
  bins  (x-z, front view): from the tray to each of the four bins. Outer bins: the tray tips 25
        degrees and the card slides off its edge, down a ramp on the divider, into the bin.
        Inner bins: the splitter flap under the trapdoors is set first, then both doors open, the
        card drops onto the flap and slides off into the bin on that side.

Every case runs over a spread of friction, card start offset and servo speed; a case passes when
the card ends inside the right bin's walls (or flat in the tray pocket), below the bin top.
Units: mm, g, s.  python3 drops.py [--draw out.png case]   (pip install pymunk pillow)
"""
import math, sys, itertools, json
import pymunk

G = 9810.0
CARD_W, CARD_L, CARD_T, CARD_M = 63.0, 88.0, 0.6, 1.75

# ---- the numbers under test (kept in step with layout.scad / sort.scad) ---------------------------
L = dict(
    pivot_z=242.0, tray_half=100.0, floor_t=2.5,
    hinge_x=36.6, door_in=0.25, door_out=36.0, door_open=88.0,
    split_z=150.0, split_half=31.0, split_tilt=32.0,
    bin_top=186.0, bin_pitch=82.0, bin_in=68.0, bin_wall=2.0,
    ramp_x0=58.0, ramp_z0=211.0, ramp_a=28.0, ramp_x1=101.0,
    tilt=25.0, ramps=0, splitter=0, inner_tilt=10.0, inner_lead=0.0,
    # side view
    bed_a=30.0, bed_e=(50.0, 296.0), stop_s=2.0, tray_in=45.5, front_h=30.0, back_h=6.0, back_y1=51.5,
)

def card_body(space, pos, angle, length, mu):
    m = CARD_M / 1000.0 * 1000  # grams
    moment = pymunk.moment_for_box(m, (length, CARD_T))
    b = pymunk.Body(m, moment)
    b.position = pos; b.angle = angle
    s = pymunk.Poly.create_box(b, (length, CARD_T), radius=0.1)
    s.friction = mu; s.elasticity = 0.05
    space.add(b, s)
    return b, s

AIR = 0.5 * 1.2e-6 * 1.2 * CARD_W * CARD_L   # 0.5 rho Cd A: a falling card's broadside drag (g/mm)
def air_drag(card, length, n=8):
    nrm = card.rotation_vector.perpendicular()
    for k in range(n):
        u = -length / 2 + (k + 0.5) * length / n
        w = card.local_to_world((u, 0))
        vn = card.velocity_at_world_point(w).dot(nrm)
        card.apply_force_at_world_point(-nrm * (AIR / n * vn * abs(vn)), w)

def seg(space, body, a, b, mu, r=0.6):
    s = pymunk.Segment(body, a, b, r); s.friction = mu; s.elasticity = 0.05
    space.add(s); return s

def ramp_angle(t, t0, dur, a0, a1):
    if t <= t0: return a0
    if t >= t0 + dur: return a1
    u = (t - t0) / dur
    return a0 + (a1 - a0) * (0.5 - 0.5 * math.cos(math.pi * u))

# ------------------------------------------------------------------------------------------------
def bins_case(target, mu_pla, x_off, servo_t, draw=None, fill=120):
    """target: 0..3 = bins left to right (x -123, -41, 41, 123)."""
    p = L
    sp = pymunk.Space(); sp.gravity = (0, -G); sp.iterations = 40
    st = sp.static_body
    P = p["pivot_z"]
    centres = [(-1.5 + i) * p["bin_pitch"] for i in range(4)]
    half_in = p["bin_in"] / 2
    # bins: walls from the floor (bin_top - 120 is enough to see where it goes) to bin_top
    walls_x = sorted(set([c - half_in for c in centres] + [c + half_in for c in centres]))
    floor_z = p["bin_top"] - fill
    for c in centres:
        seg(sp, st, (c - half_in, floor_z), (c + half_in, floor_z), mu_pla)
    for c in centres:
        for x in (c - half_in, c + half_in):
            seg(sp, st, (x, floor_z), (x, p["bin_top"]), mu_pla)
    # caps on the walls between bins
    for i in range(3):
        a = centres[i] + half_in; b = centres[i + 1] - half_in
        seg(sp, st, (a, p["bin_top"]), (b, p["bin_top"]), mu_pla)
    # divider fins up to the ramps (x = +-82), and the ramps on top of them
    for m in ((-1, 1) if p["ramps"] else ()):
        x0, z0 = m * p["ramp_x0"], p["ramp_z0"]
        x1 = m * p["ramp_x1"]; z1 = z0 - (p["ramp_x1"] - p["ramp_x0"]) * math.tan(math.radians(p["ramp_a"]))
        seg(sp, st, (x0, z0), (x1, z1), mu_pla)
        zr = z0 - (p["bin_pitch"] - p["ramp_x0"]) * math.tan(math.radians(p["ramp_a"]))   # ramp height over the divider
        seg(sp, st, (m * p["bin_pitch"], p["bin_top"]), (m * p["bin_pitch"], zr), mu_pla, r=2)
        seg(sp, st, (x0, z0), (m * p["bin_pitch"], zr), mu_pla, r=2)       # the ramp's underside, filled to the divider
    # centre divider top: a ridge under the splitter
    seg(sp, st, (-3, p["bin_top"]), (0, p["bin_top"] + 4), mu_pla); seg(sp, st, (0, p["bin_top"] + 4), (3, p["bin_top"]), mu_pla)
    # walls of the machine (x = +-160)
    for m in (-1, 1): seg(sp, st, (m * 160, floor_z), (m * 160, 400), mu_pla)

    # tray: kinematic, pivot at (0, P)
    tray = pymunk.Body(body_type=pymunk.Body.KINEMATIC); tray.position = (0, P); sp.add(tray)
    hx, di, do = p["hinge_x"], p["door_in"], p["door_out"]
    for m in (-1, 1):
        seg(sp, tray, (m * (do + 0.25), -0.6), (m * p["tray_half"], -0.6), mu_pla)   # the fixed wings
    doors = []
    for m in (-1, 1):
        d = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        d.position = (m * hx, P - 3.0); sp.add(d)
        seg(sp, d, (-m * (hx - di), 2.4), (-m * (hx - do), 2.4), mu_pla)
        doors.append((m, d))
    # splitter flap
    spl = pymunk.Body(body_type=pymunk.Body.KINEMATIC); spl.position = (0, p["split_z"]); sp.add(spl)
    if p["splitter"]: seg(sp, spl, (-p["split_half"], 0), (p["split_half"], 0), mu_pla, r=1.2)

    card, cs = card_body(sp, (x_off, P + CARD_T / 2 + 0.2), 0, CARD_W, mu_pla)
    side = -1 if target < 2 else 1
    outer = target in (0, 3)
    split_a = side * -p["split_tilt"] if not outer else 0.0    # low on the target side
    dt = 1 / 2000.0; t = 0; T = 1.6
    trace = []
    while t < T:
        def pose(tt):
            if outer:
                ta = ramp_angle(tt, 0.05, servo_t * p["tilt"] / 60, 0, side * -p["tilt"]); dl = dr = 0.0
            else:
                ta = ramp_angle(tt, 0.05, servo_t * max(p["inner_tilt"], 1) / 60, 0, side * -p["inner_tilt"])
                d = ramp_angle(tt, 0.05 + p["inner_lead"], servo_t * p["door_open"] / 60, 0, p["door_open"])
                if p["splitter"]: dl = dr = d
                else: dl, dr = (d, 0.0) if side < 0 else (0.0, d)
            return math.radians(ta), (math.radians(dl), math.radians(dr))
        ta, das = pose(t); ta2, das2 = pose(t + dt)
        tray.angle = ta; tray.angular_velocity = (ta2 - ta) / dt
        spl.angle = math.radians(split_a) if p["splitter"] else 0
        for m, d in doors:
            da = das[0] if m < 0 else das[1]; da2 = das2[0] if m < 0 else das2[1]
            def hpos(a_):
                hx_, hz_ = m * hx, -3.0
                return (hx_ * math.cos(a_) - hz_ * math.sin(a_), P + hx_ * math.sin(a_) + hz_ * math.cos(a_))
            h1 = hpos(ta); h2 = hpos(ta2)
            d.position = h1; d.velocity = ((h2[0] - h1[0]) / dt, (h2[1] - h1[1]) / dt)
            d.angle = ta + m * da; d.angular_velocity = ((ta2 + m * da2) - (ta + m * da)) / dt
        air_drag(card, CARD_W)
        sp.step(dt); t += dt
        if int(t / dt) % 40 == 0: trace.append((t, card.position.x, card.position.y, math.degrees(card.angle)))
    x, z = card.position
    c = centres[target]
    ang = abs((math.degrees(card.angle) + 90) % 180 - 90)
    ends = [card.local_to_world((u, 0)).x for u in (-CARD_W / 2, CARD_W / 2)]
    inside = min(ends) > c - half_in - 0.5 and max(ends) < c + half_in + 0.5 and z < p["bin_top"] - 5 and ang < 20
    if draw: draw_case(sp, trace, draw, CARD_W)
    return inside, dict(x=round(x, 1), z=round(z, 1), ang=round(ang, 1))

# ------------------------------------------------------------------------------------------------
def bed_case(mu_bed, mu_pla, s_off, stop_t, draw=None):
    p = L
    sp = pymunk.Space(); sp.gravity = (0, -G); sp.iterations = 40
    st = sp.static_body
    a = math.radians(p["bed_a"]); ey, ez = p["bed_e"]
    # the bed runs from its front edge up the slope (y increases backwards: draw y as the x axis)
    top = (ey + 100 * math.cos(a), ez + 100 * math.sin(a))
    bed = seg(sp, st, (ey, ez - 0.6), (top[0], top[1] - 0.6), mu_bed)
    P = p["pivot_z"]; ti = p["tray_in"]
    tray = [seg(sp, st, (-ti, P - 0.6), (ti, P - 0.6), mu_pla),
            seg(sp, st, (-ti, P), (-ti, P + p["front_h"]), mu_pla),
            seg(sp, st, (ti, P), (p["back_y1"], P + p["back_h"]), mu_pla),      # back rail with its ramp
            seg(sp, st, (p["back_y1"], P + p["back_h"]), (p["back_y1"], P - 20), mu_pla)]
    s0 = p["stop_s"] + s_off
    cpos = (ey + (s0 + CARD_L / 2) * math.cos(a) - (CARD_T / 2 + 0.3) * math.sin(a), ez + (s0 + CARD_L / 2) * math.sin(a) + (CARD_T / 2 + 0.3) * math.cos(a))
    card, cs = card_body(sp, cpos, a, CARD_L, mu_bed)
    stop = pymunk.Body(body_type=pymunk.Body.KINEMATIC); sp.add(stop)
    sseg = seg(sp, stop, (ey + p["stop_s"] * math.cos(a), ez + p["stop_s"] * math.sin(a)), (ey + p["stop_s"] * math.cos(a) - 10 * math.sin(a), ez + p["stop_s"] * math.sin(a) + 10 * math.cos(a)), mu_pla)
    dt = 1 / 2000.0; t = 0; trace = []
    removed = False
    while t < 1.5:
        if not removed and t > stop_t:
            sp.remove(sseg); removed = True
        # card touching the tray gets PLA friction
        if card.position.y < ez - 10: cs.friction = mu_pla
        air_drag(card, CARD_L)
        sp.step(dt); t += dt
        if int(t / dt) % 40 == 0: trace.append((t, card.position.x, card.position.y, math.degrees(card.angle)))
    y, z = card.position
    ends = [card.local_to_world((u, 0)).x for u in (-CARD_L / 2, CARD_L / 2)]
    ang = abs((math.degrees(card.angle) + 90) % 180 - 90)
    ok = min(ends) > -ti - 0.5 and max(ends) < ti + 0.5 and abs(z - P) < 3 and ang < 3
    if draw: draw_case(sp, trace, draw, CARD_L)
    return ok, dict(y=round(y, 1), z=round(z, 1), ang=round(ang, 1), ends=[round(e, 1) for e in ends])

def draw_case(sp, trace, out, clen):
    from PIL import Image, ImageDraw
    xs = [x for _, x, _, _ in trace]; zs = [z for _, _, z, _ in trace]
    x0, x1 = -170, 170; z0, z1 = 40, 330
    sc = 3; W = int((x1 - x0) * sc); H = int((z1 - z0) * sc)
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    f = lambda x, z: ((x - x0) * sc, (z1 - z) * sc)
    for s in sp.shapes:
        if isinstance(s, pymunk.Segment):
            a = s.body.local_to_world(s.a); b = s.body.local_to_world(s.b)
            d.line([f(*a), f(*b)], fill=(60, 60, 60), width=3)
    for i, (t, x, z, ang) in enumerate(trace[::3]):
        L2 = clen / 2
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        d.line([f(x - L2 * c, z - L2 * s), f(x + L2 * c, z + L2 * s)], fill=(230, 110, 40), width=2)
    im.save(out)

if __name__ == "__main__":
    if "--set" in sys.argv:
        L.update(json.loads(sys.argv[sys.argv.index("--set") + 1]))
    res = {}
    fails = 0; n = 0
    for target in range(4):
        for mu, xo, sv, fill in itertools.product([0.2, 0.35, 0.5], [-4, 0, 4], [0.10, 0.18, 0.3], [150, 20]):
            ok, info = bins_case(target, mu, xo, sv, fill=fill)
            n += 1
            if not ok:
                fails += 1; print("FAIL bin", target + 1, "mu", mu, "x", xo, "servo", sv, "fill", fill, info)
        print("bin", target + 1, "done")
    for mub, mup, so, stt in itertools.product([0.1, 0.18, 0.28], [0.25, 0.45], [0, 1.5], [0.02, 0.06]):
        ok, info = bed_case(mub, mup, so, stt)
        n += 1
        if not ok:
            fails += 1; print("FAIL bed mu_bed", mub, "mu_pla", mup, "s", so, "stop", stt, info)
    print(f"{n - fails}/{n} drops pass")
