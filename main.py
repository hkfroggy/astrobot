#!/usr/bin/env .venv/bin/python3
"""
AstroBot Dashboard — 1024×600 full-screen Raspberry Pi display
Run:  python main.py               (full-screen, default)
      python main.py --windowed    (start in windowed mode)
Keys: F = toggle full-screen / windowed
      S = open settings
      Q / Esc = quit
"""
import sys
import pygame
import config

from widgets.clock    import ClockWidget
from widgets.weather  import WeatherWidget
from widgets.deep_sky import DeepSkyWidget
from widgets.moon     import MoonWidget
from widgets.tides    import TidesWidget
from settings         import SettingsOverlay, draw_gear_button

# Gear button position: top-right corner, sits over the weather panel
_GEAR_RECT = pygame.Rect(config.SCREEN_WIDTH - 46, 6, 36, 36)


def _make_icon():
    """
    Generate a 64×64 app icon: white robot on a blue background.
    Drawn entirely with pygame primitives — no image file needed.
    """
    S  = 64
    BG = ( 30, 100, 220)   # blue background
    W  = (230, 235, 245)   # off-white robot body
    EY = ( 20,  70, 180)   # dark-blue eye / detail colour

    surf = pygame.Surface((S, S))
    surf.fill(BG)

    # ── Antenna ──────────────────────────────────────────────────────────────
    pygame.draw.rect(surf,   W,  pygame.Rect(30,  3,  4, 10))   # stem
    pygame.draw.circle(surf, W,  (32, 3), 4)                     # ball

    # ── Head ─────────────────────────────────────────────────────────────────
    pygame.draw.rect(surf,   W,  pygame.Rect(11, 13, 42, 22), border_radius=4)
    # Eyes
    pygame.draw.circle(surf, EY, (23, 24), 6)
    pygame.draw.circle(surf, EY, (41, 24), 6)
    pygame.draw.circle(surf, W,  (23, 24), 3)   # highlight
    pygame.draw.circle(surf, W,  (41, 24), 3)
    # Mouth — five short segments
    for i in range(5):
        pygame.draw.rect(surf, EY, pygame.Rect(18 + i * 6, 31, 4, 2))

    # ── Neck ─────────────────────────────────────────────────────────────────
    pygame.draw.rect(surf, W, pygame.Rect(27, 35, 10, 5))

    # ── Body ─────────────────────────────────────────────────────────────────
    pygame.draw.rect(surf, W, pygame.Rect( 9, 40, 46, 18), border_radius=3)
    # Chest panel detail
    pygame.draw.rect(surf, EY, pygame.Rect(20, 44, 24,  8), border_radius=2)
    pygame.draw.circle(surf, W, (32, 48), 4)   # centre button

    # ── Arms ─────────────────────────────────────────────────────────────────
    pygame.draw.rect(surf, W, pygame.Rect( 1, 41,  7, 13), border_radius=2)
    pygame.draw.rect(surf, W, pygame.Rect(56, 41,  7, 13), border_radius=2)

    # ── Legs ─────────────────────────────────────────────────────────────────
    pygame.draw.rect(surf, W, pygame.Rect(14, 58, 12,  6), border_radius=2)
    pygame.draw.rect(surf, W, pygame.Rect(38, 58, 12,  6), border_radius=2)

    return surf


def main():
    is_fullscreen = "--windowed" not in sys.argv   # full-screen by default

    pygame.init()
    pygame.mouse.set_visible(True)
    pygame.display.set_caption("AstroBot")
    pygame.display.set_icon(_make_icon())

    def _make_screen(fullscreen):
        flags = pygame.FULLSCREEN if fullscreen else 0
        return pygame.display.set_mode(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), flags
        )

    screen = _make_screen(is_fullscreen)

    clock = pygame.time.Clock()

    # ── Widgets ───────────────────────────────────────────────────────────────
    widgets = [
        ClockWidget  (screen, config.LAYOUT["clock"]),
        WeatherWidget(screen, config.LAYOUT["weather"]),
        DeepSkyWidget(screen, config.LAYOUT["deep_sky"]),
        MoonWidget   (screen, config.LAYOUT["moon"]),
        TidesWidget  (screen, config.LAYOUT["tides"]),
    ]
    for w in widgets:
        w.start_data_fetch()

    # ── Settings overlay ──────────────────────────────────────────────────────
    settings = SettingsOverlay(screen)

    # ── Static background (background colour + dividers, rendered once) ───────
    DIVIDERS = [
        ((0,   300), (1024, 300)),
        ((280,   0), (280,  300)),
        ((360, 300), (360,  600)),
        ((580, 300), (580,  600)),
    ]

    def _make_bg():
        bg = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        bg.fill(config.BG_COLOR)
        for p1, p2 in DIVIDERS:
            pygame.draw.line(bg, config.DIVIDER, p1, p2, 1)
        return bg

    _bg_surf   = _make_bg()
    gear_hover = False

    # ── Main loop ─────────────────────────────────────────────────────────────
    running = True
    while running:
        mx, my = pygame.mouse.get_pos()
        gear_hover = _GEAR_RECT.collidepoint(mx, my)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            # Settings overlay intercepts all events while open
            if settings.is_open:
                result = settings.handle_event(event)
                if result == "saved":
                    # Clear stale data, re-fetch, and invalidate caches
                    for w in widgets:
                        with w._lock:
                            w.data = {}
                        w.invalidate()
                        w.force_refresh()
                continue

            # Global keys (only when settings closed)
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_s:
                    settings.open()
                elif event.key == pygame.K_f:
                    is_fullscreen = not is_fullscreen
                    screen    = _make_screen(is_fullscreen)
                    _bg_surf  = _make_bg()
                    for w in widgets:
                        w.surface = screen
                        w.invalidate()
                    settings.surface = screen

            # Gear button click
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if _GEAR_RECT.collidepoint(event.pos):
                    settings.open()

        # ── Draw ──────────────────────────────────────────────────────────────
        # Paint the pre-rendered static background (cheap blit, no fill loop)
        screen.blit(_bg_surf, (0, 0))

        for w in widgets:
            needs_draw = w._ALWAYS_DIRTY or w._dirty or w._cache_surf is None
            try:
                if needs_draw:
                    w.draw()
                    # Snapshot the widget region so we can replay it cheaply
                    w._cache_surf = screen.subsurface(w.rect).copy()
                    w._dirty      = False
                else:
                    screen.blit(w._cache_surf, w.rect.topleft)
            except Exception as exc:
                print(f"[draw] {w.__class__.__name__}: {exc}")

        draw_gear_button(screen, _GEAR_RECT, hovered=gear_hover)

        settings.draw()

        pygame.display.flip()
        clock.tick(config.FPS)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
