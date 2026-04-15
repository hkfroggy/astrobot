#!/usr/bin/env .venv/bin/python3
"""
AstroBot Dashboard — 1024×640 full-screen Raspberry Pi display
Run:  python main.py
      python main.py --windowed    (dev / desktop mode)
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


def main():
    windowed = "--windowed" in sys.argv

    pygame.init()
    pygame.mouse.set_visible(True)
    pygame.display.set_caption("AstroBot")

    flags = 0 if windowed else pygame.FULLSCREEN
    screen = pygame.display.set_mode(
        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), flags
    )

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

    # ── Divider lines ─────────────────────────────────────────────────────────
    DIVIDERS = [
        ((0,   320), (1024, 320)),
        ((280,   0), (280,  320)),
        ((360, 320), (360,  640)),
        ((580, 320), (580,  640)),
    ]

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
                    # Clear stale data and re-fetch with new location/units
                    for w in widgets:
                        with w._lock:
                            w.data = {}
                        w.force_refresh()
                continue

            # Global keys (only when settings closed)
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_s:
                    settings.open()

            # Gear button click
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if _GEAR_RECT.collidepoint(event.pos):
                    settings.open()

        # ── Draw ──────────────────────────────────────────────────────────────
        screen.fill(config.BG_COLOR)

        for w in widgets:
            try:
                w.draw()
            except Exception as exc:
                print(f"[draw] {w.__class__.__name__}: {exc}")

        for p1, p2 in DIVIDERS:
            pygame.draw.line(screen, config.DIVIDER, p1, p2, 1)

        draw_gear_button(screen, _GEAR_RECT, hovered=gear_hover)

        settings.draw()

        pygame.display.flip()
        clock.tick(config.FPS)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
