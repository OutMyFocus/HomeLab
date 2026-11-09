#!/usr/bin/env python3
"""Pusher drop test: a card on a flat platform is pushed sideways off its edge into a bin beside it."""
import math, itertools, sys
import pymunk
from drops import card_body, seg, air_drag, draw_case, CARD_W, G

def push_case(v, mu, fill, gap=3.0, edge=33.0, bin_w=68.0, wall_z=None, draw=None):
    sp = pymunk.Space(); sp.gravity = (0, -G); sp.iterations = 40
    st = sp.static_body
    P = 200.0
    seg(sp, st, (-edge, P - 0.6), (edge, P - 0.6), mu)
    x0 = edge + 1.0; x1 = x0 + bin_w; top = P - gap
    fl = top - fill
    seg(sp, st, (x0, fl), (x1, fl), mu); seg(sp, st, (x0, fl), (x0, top), mu); seg(sp, st, (x1, fl), (x1, wall_z or top + 30), mu)
    card, cs = card_body(sp, (0, P + 0.5), 0, CARD_W, mu)
    pusher = pymunk.Body(body_type=pymunk.Body.KINEMATIC); pusher.position = (-CARD_W / 2 - 1, P + 3); sp.add(pusher)
    seg(sp, pusher, (0, -2.5), (0, 8), 0.3)
    t = 0; dt = 1 / 2000.0; trace = []
    stroke = 2 * edge + 4
    while t < 1.5:
        x = pusher.position.x
        if x < -CARD_W / 2 - 1 + stroke and t > 0.02: pusher.velocity = (v, 0)
        else: pusher.velocity = (0, 0)
        air_drag(card, CARD_W)
        sp.step(dt); t += dt
        if int(t / dt) % 40 == 0: trace.append((t, card.position.x, card.position.y, math.degrees(card.angle)))
    ends = [card.local_to_world((u, 0)).x for u in (-CARD_W / 2, CARD_W / 2)]
    ang = abs((math.degrees(card.angle) + 90) % 180 - 90)
    ok = min(ends) > x0 - 0.5 and max(ends) < x1 + 0.5 and card.position.y < top
    if draw: draw_case(sp, trace, draw, CARD_W)
    return ok, dict(x=round(card.position.x, 1), z=round(card.position.y - fl, 1), ang=round(ang, 1))

if __name__ == "__main__":
    for v, mu, fill in itertools.product([80, 200, 400, 800], [0.25, 0.4], [150, 60, 15]):
        print(v, mu, fill, push_case(v, mu, fill))

def level_drop(mu, servo_t, x_off, drop=176.0, half=33.5, shaft=34.5, length=CARD_W, draw=None):
    """Card on level k's closed trapdoors (hinged at the pocket's outer edges); both open; it falls
    down the shaft between the bins onto level k+1's floor."""
    sp = pymunk.Space(); sp.gravity = (0, -G); sp.iterations = 40
    st = sp.static_body
    L1 = 300.0; L2 = L1 - drop
    seg(sp, st, (-half - 2, L2 - 0.6), (half + 2, L2 - 0.6), mu)              # level k+1 floor (closed doors)
    for m in (-1, 1):
        seg(sp, st, (m * shaft, L2 + 0.5), (m * shaft, L1 - 4), mu)           # shaft walls / paddles at rest
    doors = []
    for m in (-1, 1):
        d = pymunk.Body(body_type=pymunk.Body.KINEMATIC); d.position = (m * half, L1 - 2.5); sp.add(d)
        seg(sp, d, (0, 1.9), (-m * (half - 0.25), 1.9), mu); doors.append((m, d))
    card, cs = card_body(sp, (x_off, L1 + 0.5), 0, length, mu)
    from drops import ramp_angle
    t = 0; dt = 1 / 2000.0; trace = []
    while t < 1.5:
        a = ramp_angle(t, 0.02, servo_t * 90 / 60, 0, 90)
        a2 = ramp_angle(t + dt, 0.02, servo_t * 90 / 60, 0, 90)
        for m, d in doors:
            d.angle = math.radians(m * a); d.angular_velocity = math.radians(m * (a2 - a)) / dt
        air_drag(card, length)
        sp.step(dt); t += dt
        if int(t / dt) % 40 == 0: trace.append((t, card.position.x, card.position.y, math.degrees(card.angle)))
    ends = [card.local_to_world((u, 0)).x for u in (-length / 2, length / 2)]
    ang = abs((math.degrees(card.angle) + 90) % 180 - 90)
    ok = min(ends) > -half - 1 and max(ends) < half + 1 and abs(card.position.y - L2) < 2 and ang < 3
    if draw: draw_case(sp, trace, draw, length)
    return ok, dict(x=round(card.position.x, 1), z=round(card.position.y - L2, 1), ang=round(ang, 1))
