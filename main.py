"""
Plane Loading Simulator
=======================
Animates different boarding strategies for a 10-row × 2-seat plane.
Run:  python main.py  (inside the .venv)
"""

import pygame
import random
import sys
import math

# ──────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────
WIN_W, WIN_H = 1200, 800
FPS = 60
NUM_ROWS = 10
SEATS_PER_ROW = 2  # 0 = window, 1 = aisle

# States
QUEUED, WALKING, STORING, WAITING, SEATED = range(5)

# ── Colors ────────────────────────────────────────────────────
C_BG         = (18, 18, 32)
C_PANEL      = (28, 32, 50)
C_BORDER     = (52, 58, 82)
C_TEXT       = (210, 215, 235)
C_TEXT_DIM   = (115, 120, 148)
C_TEXT_BRT   = (240, 244, 255)
C_ACCENT     = (88, 130, 255)
C_ACCENT_HI  = (115, 158, 255)
C_BTN_GO     = (46, 164, 96)
C_BTN_GO_HI  = (60, 190, 115)
C_BTN_RST    = (195, 72, 72)
C_BTN_RST_HI = (220, 95, 95)
C_SEAT_EMPTY = (44, 48, 68)
C_AISLE_BG   = (34, 38, 56)
C_FUSE       = (38, 42, 62)
C_FUSE_BD    = (58, 64, 88)
C_SLIDER_BG  = (50, 55, 78)
C_SLIDER_FG  = (88, 130, 255)
C_SLIDER_KNB = (200, 210, 240)

# State colours
SC = {
    WALKING: (66, 133, 244),
    STORING: (255, 167, 38),
    WAITING: (239, 83, 80),
    SEATED:  (76, 175, 80),
    QUEUED:  (70, 78, 105),
}
STATE_LABELS = {
    WALKING: "Walking",
    STORING: "Storing Bags",
    WAITING: "Waiting for Row",
    SEATED:  "Seated",
}

STRATEGIES = [
    ("random",        "Random Order"),
    ("back_to_front", "Back to Front"),
    ("front_to_back", "Front to Back"),
    ("one_per_row",   "One Per Row"),
]

SPEEDS = [1, 2, 5, 10]

# ── Layout constants ──────────────────────────────────────────
CELL       = 46
CELL_PAD   = 5
ROW_H      = CELL + CELL_PAD
AISLE_W    = 46

PLANE_X    = 120          # left edge of window-seat column
PLANE_Y    = 130          # top of row 0
WSEAT_X    = PLANE_X
ASEAT_X    = PLANE_X + CELL + CELL_PAD
AISLE_X    = ASEAT_X + CELL + CELL_PAD
BODY_L     = WSEAT_X - 10
BODY_R     = AISLE_X + AISLE_W + 10
BODY_W     = BODY_R - BODY_L

CTRL_X     = 480
CTRL_Y     = 110
CTRL_W     = WIN_W - CTRL_X - 40


# ══════════════════════════════════════════════════════════════
#  Passenger
# ══════════════════════════════════════════════════════════════
class Passenger:
    __slots__ = ("row", "seat", "state", "aisle_pos", "prog", "timer")

    def __init__(self, row: int, seat: int):
        self.row = row          # target row 0-9
        self.seat = seat        # 0=window 1=aisle
        self.state = QUEUED
        self.aisle_pos = -1     # -1 = not on board
        self.prog = 0.0         # 0-1 interpolation toward next row
        self.timer = 0.0

    @property
    def vis_pos(self) -> float:
        if self.state == WALKING:
            return self.aisle_pos + self.prog
        return float(self.aisle_pos)

    @property
    def color(self):
        return SC[self.state]


# ══════════════════════════════════════════════════════════════
#  Simulation
# ══════════════════════════════════════════════════════════════
class Simulation:
    def __init__(self):
        self.passengers: list[Passenger] = []
        self.queue: list[Passenger] = []
        self.aisle: dict[int, Passenger] = {}   # aisle_pos -> Passenger
        self.seats: dict[tuple, Passenger] = {}  # (row,seat) -> Passenger
        self.elapsed = 0.0
        self.running = False
        self.done = False
        self.t_move = 1.0
        self.t_store = 3.0
        self.t_pass = 2.0
        self.speed = 1.0

    # ── build queue in chosen order ───────────────────────────
    def setup(self, key: str):
        pool = [Passenger(r, s) for r in range(NUM_ROWS) for s in range(SEATS_PER_ROW)]

        if key == "random":
            random.shuffle(pool)
        elif key == "back_to_front":
            pool.sort(key=lambda p: (-p.row, p.seat))   # row 9→0, window first
        elif key == "front_to_back":
            pool.sort(key=lambda p: (p.row, p.seat))     # row 0→9, window first
        elif key == "one_per_row":
            # window seats 9→0, then aisle seats 9→0
            pool.sort(key=lambda p: (p.seat, -p.row))

        self.passengers = pool
        self.queue = list(pool)
        self.aisle.clear()
        self.seats.clear()
        self.elapsed = 0.0
        self.done = False

    # ── one simulation tick ───────────────────────────────────
    def update(self, dt: float):
        if not self.running or self.done:
            return
        dt *= self.speed
        self.elapsed += dt

        # process passengers in aisle, front-most first
        active = sorted(
            (p for p in self.passengers if p.state in (WALKING, STORING, WAITING)),
            key=lambda p: p.aisle_pos, reverse=True,
        )
        for p in active:
            self._tick(p, dt)

        # try boarding next passenger(s) from queue
        self._try_board()

        # check done
        if self.passengers and all(p.state == SEATED for p in self.passengers):
            self.done = True
            self.running = False

    def _tick(self, p: Passenger, dt: float):
        if p.state == WALKING:
            nxt = p.aisle_pos + 1
            # Don't accumulate visual progress if the next row is blocked
            if nxt > p.row:
                p.prog = 0.0
                return
            if nxt in self.aisle:
                p.prog = 0.0
                return
            # Next position is free — accumulate walking progress
            p.prog += dt / self.t_move
            while p.prog >= 1.0:
                # Move into the next position
                self.aisle.pop(p.aisle_pos, None)
                p.aisle_pos = nxt
                self.aisle[nxt] = p
                # Arrived at target row?
                if nxt == p.row:
                    p.prog = 0.0
                    p.state = STORING
                    p.timer = self.t_store
                    return
                p.prog -= 1.0
                # Check if we can continue moving
                nxt = p.aisle_pos + 1
                if nxt > p.row or nxt in self.aisle:
                    p.prog = 0.0
                    return

        elif p.state == STORING:
            p.timer -= dt
            if p.timer <= 0:
                other = (p.row, 1 - p.seat)
                if other in self.seats:
                    p.state = WAITING
                    p.timer = self.t_pass
                else:
                    self._seat(p)

        elif p.state == WAITING:
            p.timer -= dt
            if p.timer <= 0:
                self._seat(p)

    def _seat(self, p: Passenger):
        p.state = SEATED
        self.aisle.pop(p.aisle_pos, None)
        self.seats[(p.row, p.seat)] = p

    def _try_board(self):
        # entrance is aisle position -1; first real row is 0
        if not self.queue:
            return
        if -1 not in self.aisle:
            p = self.queue.pop(0)
            p.state = WALKING
            p.aisle_pos = -1
            p.prog = 0.0
            self.aisle[-1] = p


# ══════════════════════════════════════════════════════════════
#  UI Helpers
# ══════════════════════════════════════════════════════════════
class Slider:
    def __init__(self, x, y, w, lo, hi, val, label, fmt="{:.1f}s"):
        self.rect = pygame.Rect(x, y, w, 28)
        self.lo, self.hi, self.val = lo, hi, val
        self.label = label
        self.fmt = fmt
        self.dragging = False

    @property
    def knob_x(self):
        t = (self.val - self.lo) / (self.hi - self.lo)
        return self.rect.x + int(t * self.rect.w)

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            kx = self.knob_x
            if abs(ev.pos[0] - kx) < 14 and abs(ev.pos[1] - self.rect.centery) < 16:
                self.dragging = True
        elif ev.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif ev.type == pygame.MOUSEMOTION and self.dragging:
            t = (ev.pos[0] - self.rect.x) / self.rect.w
            t = max(0.0, min(1.0, t))
            self.val = round(self.lo + t * (self.hi - self.lo), 1)

    def draw(self, surf, font):
        # label
        lbl = font.render(self.label, True, C_TEXT)
        surf.blit(lbl, (self.rect.x, self.rect.y - 22))
        # track
        pygame.draw.rect(surf, C_SLIDER_BG, self.rect, border_radius=6)
        # filled portion
        fill = pygame.Rect(self.rect.x, self.rect.y, self.knob_x - self.rect.x, self.rect.h)
        pygame.draw.rect(surf, C_SLIDER_FG, fill, border_radius=6)
        # knob
        pygame.draw.circle(surf, C_SLIDER_KNB, (self.knob_x, self.rect.centery), 10)
        pygame.draw.circle(surf, C_ACCENT, (self.knob_x, self.rect.centery), 10, 2)
        # value text
        vtxt = font.render(self.fmt.format(self.val), True, C_TEXT_BRT)
        surf.blit(vtxt, (self.rect.right + 10, self.rect.y + 2))


def draw_rounded_rect(surf, color, rect, radius=8):
    pygame.draw.rect(surf, color, rect, border_radius=radius)


def btn_rect(x, y, w, h):
    return pygame.Rect(x, y, w, h)


# ══════════════════════════════════════════════════════════════
#  Main App
# ══════════════════════════════════════════════════════════════
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("✈  Plane Loading Simulator")
    clock = pygame.time.Clock()

    # Fonts
    try:
        font      = pygame.font.SysFont("segoeui", 16)
        font_sm   = pygame.font.SysFont("segoeui", 14)
        font_lg   = pygame.font.SysFont("segoeui", 26, bold=True)
        font_mid  = pygame.font.SysFont("segoeui", 18, bold=True)
        font_time = pygame.font.SysFont("consolas", 28, bold=True)
    except Exception:
        font      = pygame.font.Font(None, 20)
        font_sm   = pygame.font.Font(None, 17)
        font_lg   = pygame.font.Font(None, 32)
        font_mid  = pygame.font.Font(None, 22)
        font_time = pygame.font.Font(None, 32)

    sim = Simulation()
    sel_strategy = 0   # index into STRATEGIES
    sel_speed = 0      # index into SPEEDS
    started_once = False

    # ── Sliders ───────────────────────────────────────────────
    sl_x = CTRL_X + 30
    sl_w = 260
    sliders = [
        Slider(sl_x, CTRL_Y + 248, sl_w, 0.2, 5.0, 1.0, "Time to move 1 row"),
        Slider(sl_x, CTRL_Y + 318, sl_w, 0.5, 10.0, 3.0, "Time to store bags & take seat"),
        Slider(sl_x, CTRL_Y + 388, sl_w, 0.2, 5.0, 2.0, "Time to move past passenger"),
    ]

    # ── Buttons ───────────────────────────────────────────────
    btn_start = btn_rect(CTRL_X + 30, CTRL_Y + 470, 130, 42)
    btn_reset = btn_rect(CTRL_X + 180, CTRL_Y + 470, 130, 42)

    # ── Strategy checkbox rects ───────────────────────────────
    strat_rects = []
    for i in range(len(STRATEGIES)):
        strat_rects.append(pygame.Rect(CTRL_X + 30, CTRL_Y + 48 + i * 36, 20, 20))

    # ── Speed button rects ────────────────────────────────────
    spd_rects = []
    for i, s in enumerate(SPEEDS):
        spd_rects.append(pygame.Rect(CTRL_X + 30 + i * 70, CTRL_Y + 548, 56, 34))

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # ── Events ────────────────────────────────────────────
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            for sl in sliders:
                sl.handle(ev)
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # strategy checkboxes
                if not sim.running:
                    for i, r in enumerate(strat_rects):
                        if r.inflate(120, 8).collidepoint(mx, my):
                            sel_strategy = i
                # speed buttons
                for i, r in enumerate(spd_rects):
                    if r.collidepoint(mx, my):
                        sel_speed = i
                        sim.speed = SPEEDS[i]
                # start
                if btn_start.collidepoint(mx, my):
                    if not sim.running and not sim.done:
                        key = STRATEGIES[sel_strategy][0]
                        sim.t_move = sliders[0].val
                        sim.t_store = sliders[1].val
                        sim.t_pass = sliders[2].val
                        sim.speed = SPEEDS[sel_speed]
                        sim.setup(key)
                        sim.running = True
                        started_once = True
                # reset
                if btn_reset.collidepoint(mx, my):
                    sim.running = False
                    sim.done = False
                    sim.passengers.clear()
                    sim.queue.clear()
                    sim.aisle.clear()
                    sim.seats.clear()
                    sim.elapsed = 0.0
                    started_once = False

        # ── Update sim ────────────────────────────────────────
        sim.update(dt)

        # ── Draw ──────────────────────────────────────────────
        screen.fill(C_BG)

        # Title bar
        pygame.draw.rect(screen, C_PANEL, (0, 0, WIN_W, 64))
        pygame.draw.line(screen, C_BORDER, (0, 64), (WIN_W, 64))
        title = font_lg.render("✈  Plane Loading Simulator", True, C_TEXT_BRT)
        screen.blit(title, (28, 16))

        # Elapsed time (top right)
        time_str = f"{sim.elapsed:.1f}s"
        tw = font_time.render(time_str, True, C_ACCENT)
        screen.blit(tw, (WIN_W - tw.get_width() - 35, 18))
        tl = font_sm.render("Elapsed", True, C_TEXT_DIM)
        screen.blit(tl, (WIN_W - tw.get_width() - tl.get_width() - 50, 26))

        # ── Plane visualization ───────────────────────────────
        # Fuselage body
        body_top = PLANE_Y - 50
        body_bot = PLANE_Y + NUM_ROWS * ROW_H + 30
        fuselage = pygame.Rect(BODY_L, body_top, BODY_W, body_bot - body_top)
        draw_rounded_rect(screen, C_FUSE, fuselage, 18)
        pygame.draw.rect(screen, C_FUSE_BD, fuselage, 2, border_radius=18)

        # Nose (triangle-ish)
        nose_pts = [
            (BODY_L + BODY_W // 2, body_top - 40),
            (BODY_L + 8, body_top + 4),
            (BODY_R - 8, body_top + 4),
        ]
        pygame.draw.polygon(screen, C_FUSE, nose_pts)
        pygame.draw.polygon(screen, C_FUSE_BD, nose_pts, 2)

        # Entrance label
        ent = font_sm.render("ENTRANCE", True, C_TEXT_DIM)
        screen.blit(ent, (BODY_L + BODY_W // 2 - ent.get_width() // 2, body_top - 18))

        # Column headers
        screen.blit(font_sm.render("WIN", True, C_TEXT_DIM),
                     (WSEAT_X + CELL // 2 - 12, PLANE_Y - 24))
        screen.blit(font_sm.render("AISLE", True, C_TEXT_DIM),
                     (ASEAT_X + CELL // 2 - 16, PLANE_Y - 24))

        # Draw rows
        for r in range(NUM_ROWS):
            ry = PLANE_Y + r * ROW_H
            # Row label
            lbl = font_sm.render(f"R{r}" + (" ★" if r == 0 else ""), True, C_TEXT_DIM)
            screen.blit(lbl, (WSEAT_X - 40, ry + CELL // 2 - 8))

            # Window seat cell
            wr = pygame.Rect(WSEAT_X, ry, CELL, CELL)
            pax_w = sim.seats.get((r, 0))
            draw_rounded_rect(screen, pax_w.color if pax_w else C_SEAT_EMPTY, wr, 8)

            # Aisle seat cell
            ar = pygame.Rect(ASEAT_X, ry, CELL, CELL)
            pax_a = sim.seats.get((r, 1))
            draw_rounded_rect(screen, pax_a.color if pax_a else C_SEAT_EMPTY, ar, 8)

            # Aisle background
            aisle_r = pygame.Rect(AISLE_X, ry, AISLE_W, CELL)
            draw_rounded_rect(screen, C_AISLE_BG, aisle_r, 6)

        # Entrance aisle slot (position -1)
        ent_y = PLANE_Y - ROW_H
        ent_r = pygame.Rect(AISLE_X, ent_y, AISLE_W, CELL)
        draw_rounded_rect(screen, C_AISLE_BG, ent_r, 6)

        # Draw passengers in aisle
        for p in sim.passengers:
            if p.state in (WALKING, STORING, WAITING):
                vis = p.vis_pos
                py = PLANE_Y + vis * ROW_H + CELL // 2
                px = AISLE_X + AISLE_W // 2
                # glow
                glow_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
                gc = p.color + (60,)
                pygame.draw.circle(glow_surf, gc, (16, 16), 16)
                screen.blit(glow_surf, (px - 16, int(py) - 16))
                # dot
                pygame.draw.circle(screen, p.color, (px, int(py)), 12)
                pygame.draw.circle(screen, (255, 255, 255, 80), (px, int(py)), 12, 2)
                # row label on dot
                rt = font_sm.render(str(p.row), True, (255, 255, 255))
                screen.blit(rt, (px - rt.get_width() // 2, int(py) - rt.get_height() // 2))

        # Draw seated passengers in their seat cells
        for (r, s), p in sim.seats.items():
            sx = WSEAT_X if s == 0 else ASEAT_X
            sy = PLANE_Y + r * ROW_H
            cx = sx + CELL // 2
            cy = sy + CELL // 2
            pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 12, 2)

        # ── Queue area ────────────────────────────────────────
        queue_y = PLANE_Y + NUM_ROWS * ROW_H + 55
        ql = font_sm.render(f"Queue: {len(sim.queue)} waiting", True, C_TEXT_DIM)
        screen.blit(ql, (BODY_L, queue_y - 20))

        cols = 10
        for i, p in enumerate(sim.queue):
            qx = BODY_L + (i % cols) * 28
            qy = queue_y + (i // cols) * 28
            pygame.draw.circle(screen, SC[QUEUED], (qx + 10, qy + 10), 9)

        # ── Control panel ─────────────────────────────────────
        panel = pygame.Rect(CTRL_X, 80, CTRL_W, WIN_H - 120)
        draw_rounded_rect(screen, C_PANEL, panel, 14)
        pygame.draw.rect(screen, C_BORDER, panel, 1, border_radius=14)

        # Strategy section
        sec = font_mid.render("Boarding Strategy", True, C_TEXT_BRT)
        screen.blit(sec, (CTRL_X + 30, CTRL_Y + 10))

        for i, (key, name) in enumerate(STRATEGIES):
            r = strat_rects[i]
            # checkbox
            pygame.draw.rect(screen, C_BORDER, r, border_radius=4)
            if i == sel_strategy:
                inner = r.inflate(-6, -6)
                pygame.draw.rect(screen, C_ACCENT, inner, border_radius=3)
            t = font.render(name, True, C_TEXT if i == sel_strategy else C_TEXT_DIM)
            screen.blit(t, (r.right + 10, r.y))

        # Timing section
        sec2 = font_mid.render("Timing Controls", True, C_TEXT_BRT)
        screen.blit(sec2, (CTRL_X + 30, CTRL_Y + 200))

        for sl in sliders:
            sl.draw(screen, font)

        # Speed section
        sec3 = font_mid.render("Speed", True, C_TEXT_BRT)
        screen.blit(sec3, (CTRL_X + 30, CTRL_Y + 520))

        for i, r in enumerate(spd_rects):
            c = C_ACCENT if i == sel_speed else C_BORDER
            draw_rounded_rect(screen, c, r, 8)
            st = font.render(f"{SPEEDS[i]}×", True, C_TEXT_BRT if i == sel_speed else C_TEXT_DIM)
            screen.blit(st, (r.x + r.w // 2 - st.get_width() // 2,
                             r.y + r.h // 2 - st.get_height() // 2))

        # Buttons
        mx, my = pygame.mouse.get_pos()
        # Start
        go_c = C_BTN_GO_HI if btn_start.collidepoint(mx, my) else C_BTN_GO
        draw_rounded_rect(screen, go_c, btn_start, 10)
        gt = font_mid.render("▶  START", True, C_TEXT_BRT)
        screen.blit(gt, (btn_start.x + btn_start.w // 2 - gt.get_width() // 2,
                         btn_start.y + btn_start.h // 2 - gt.get_height() // 2))
        # Reset
        rs_c = C_BTN_RST_HI if btn_reset.collidepoint(mx, my) else C_BTN_RST
        draw_rounded_rect(screen, rs_c, btn_reset, 10)
        rt = font_mid.render("↺  RESET", True, C_TEXT_BRT)
        screen.blit(rt, (btn_reset.x + btn_reset.w // 2 - rt.get_width() // 2,
                         btn_reset.y + btn_reset.h // 2 - rt.get_height() // 2))

        # ── Done banner ───────────────────────────────────────
        if sim.done:
            banner = font_lg.render(f"✔  All seated in {sim.elapsed:.1f}s", True, SC[SEATED])
            bx = WIN_W // 2 - banner.get_width() // 2
            screen.blit(banner, (bx, WIN_H - 60))

        # ── Legend bar ────────────────────────────────────────
        legend_y = WIN_H - 46
        pygame.draw.rect(screen, C_PANEL, (0, legend_y - 10, WIN_W, 56))
        pygame.draw.line(screen, C_BORDER, (0, legend_y - 10), (WIN_W, legend_y - 10))

        lx = 30
        lt = font_sm.render("LEGEND:", True, C_TEXT_DIM)
        screen.blit(lt, (lx, legend_y + 4))
        lx += lt.get_width() + 20
        for state in (WALKING, STORING, WAITING, SEATED):
            pygame.draw.circle(screen, SC[state], (lx + 8, legend_y + 12), 8)
            n = font_sm.render(STATE_LABELS[state], True, C_TEXT)
            screen.blit(n, (lx + 22, legend_y + 4))
            lx += n.get_width() + 50

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
