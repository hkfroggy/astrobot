#!/usr/bin/env .venv/bin/python3
"""
AstroBot Dashboard — 1024×600 full-screen Raspberry Pi display
Run:  python main.py               (full-screen, default)
      python main.py --windowed    (start in windowed mode)
Keys: F = toggle full-screen / windowed
      S = open settings
      P = switch page
      Q / Esc = quit
"""
import sys
import math
import pygame
import config

from widgets.clock     import ClockWidget
from widgets.weather   import WeatherWidget
from widgets.deep_sky  import DeepSkyWidget
from widgets.moon      import MoonWidget
from widgets.tides     import TidesWidget
from widgets.satellite import SatelliteWidget
from settings          import SettingsOverlay, draw_gear_button

# ── Button rects (top-right corner) ──────────────────────────────────────────
_GEAR_RECT = pygame.Rect(config.SCREEN_WIDTH - 46,  6, 36, 36)
_PAGE_RECT = pygame.Rect(config.SCREEN_WIDTH - 46, 48, 36, 36)

_TOTAL_PAGES = 2


def _make_icon():
    """
    Generate a 64×64 app icon: white robot on a blue background.
    Drawn entirely with pygame primitives — no image file needed.
    """
    S  = 64
    BG = ( 30, 100, 220)
    W  = (230, 235, 245)
    EY = ( 20,  70, 180)

    surf = pygame.Surface((S, S))
    surf.fill(BG)

    pygame.draw.rect(surf,   W,  pygame.Rect(30,  3,  4, 10))
    pygame.draw.circle(surf, W,  (32, 3), 4)

    pygame.draw.rect(surf,   W,  pygame.Rect(11, 13, 42, 22), border_radius=4)
    pygame.draw.circle(surf, EY, (23, 24), 6)
    pygame.draw.circle(surf, EY, (41, 24), 6)
    pygame.draw.circle(surf, W,  (23, 24), 3)
    pygame.draw.circle(surf, W,  (41, 24), 3)
    for i in range(5):
        pygame.draw.rect(surf, EY, pygame.Rect(18 + i * 6, 31, 4, 2))

    pygame.draw.rect(surf, W, pygame.Rect(27, 35, 10, 5))
    pygame.draw.rect(surf, W, pygame.Rect( 9, 40, 46, 18), border_radius=3)
    pygame.draw.rect(surf, EY, pygame.Rect(20, 44, 24,  8), border_radius=2)
    pygame.draw.circle(surf, W, (32, 48), 4)

    pygame.draw.rect(surf, W, pygame.Rect( 1, 41,  7, 13), border_radius=2)
    pygame.draw.rect(surf, W, pygame.Rect(56, 41,  7, 13), border_radius=2)

    pygame.draw.rect(surf, W, pygame.Rect(14, 58, 12,  6), border_radius=2)
    pygame.draw.rect(surf, W, pygame.Rect(38, 58, 12,  6), border_radius=2)

    return surf


def draw_page_button(surf, rect, current_page, total_pages, hovered=False):
    """Draw a small page-switch button showing current/total."""
    cx, cy = rect.centerx, rect.centery
    r_btn  = rect.width // 2
    bg_clr = (30, 44, 80) if hovered else (18, 26, 50)
    pygame.draw.circle(surf, bg_clr, (cx, cy), r_btn)
    pygame.draw.circle(surf, (38, 58, 105), (cx, cy), r_btn, 1)

    path = pygame.font.match_font("dejavusans,freesans,liberationsans,arial,sans")
    f    = pygame.font.Font(path, 10)
    clr  = (225, 235, 255) if hovered else (145, 165, 210)
    # Arrow indicator
    next_page = (current_page % total_pages) + 1
    lbl = f.render(f"p{next_page}", True, clr)
    surf.blit(lbl, lbl.get_rect(center=(cx, cy - 4)))
    # Small right-arrow chevron
    ax = cx + 1
    ay = cy + 7
    pygame.draw.line(surf, clr, (ax - 3, ay - 3), (ax + 3, ay), 1)
    pygame.draw.line(surf, clr, (ax - 3, ay + 3), (ax + 3, ay), 1)



def main():
    is_fullscreen = "--windowed" not in sys.argv

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

    clock_tick = pygame.time.Clock()

    # ── Widgets ───────────────────────────────────────────────────────────────
    widgets = [
        ClockWidget    (screen, config.LAYOUT["clock"]),
        WeatherWidget  (screen, config.LAYOUT["weather"]),
        DeepSkyWidget  (screen, config.LAYOUT["deep_sky"]),
        MoonWidget     (screen, config.LAYOUT["moon"]),
        TidesWidget    (screen, config.LAYOUT["tides"]),
        SatelliteWidget(screen, config.LAYOUT["deep_sky"]),  # page 2 only
    ]
    for w in widgets:
        w.start_data_fetch()

    # ── Settings overlay ──────────────────────────────────────────────────────
    settings = SettingsOverlay(screen)

    # ── Static backgrounds (rendered once per page layout) ───────────────────
    _DIVIDERS_P1 = [
        ((0,   300), (1024, 300)),
        ((280,   0), (280,  300)),
        ((360, 300), (360,  600)),   # DSO | Moon
        ((580, 300), (580,  600)),
    ]
    _DIVIDERS_P2 = [
        ((0,   300), (1024, 300)),
        ((280,   0), (280,  300)),
        # no x=360 divider — DSO slot is empty on page 2
        ((580, 300), (580,  600)),
    ]

    def _make_bg(dividers=_DIVIDERS_P1):
        bg = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        bg.fill(config.BG_COLOR)
        for p1, p2 in dividers:
            pygame.draw.line(bg, config.DIVIDER, p1, p2, 1)
        return bg

    _bg_p1       = _make_bg(_DIVIDERS_P1)
    _bg_p2       = _make_bg(_DIVIDERS_P2)
    current_page = 1
    gear_hover   = False
    page_hover   = False

    # ── Main loop ─────────────────────────────────────────────────────────────
    running = True
    while running:
        mx, my = pygame.mouse.get_pos()
        gear_hover = _GEAR_RECT.collidepoint(mx, my)
        page_hover = _PAGE_RECT.collidepoint(mx, my)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            # Settings overlay intercepts all events while open
            if settings.is_open:
                result = settings.handle_event(event)
                if result == "terminate":
                    running = False
                elif result == "saved":
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
                elif event.key == pygame.K_p:
                    current_page = (current_page % _TOTAL_PAGES) + 1
                    for w in widgets:
                        w.invalidate()
                elif event.key == pygame.K_f:
                    is_fullscreen = not is_fullscreen
                    screen  = _make_screen(is_fullscreen)
                    _bg_p1  = _make_bg(_DIVIDERS_P1)
                    _bg_p2  = _make_bg(_DIVIDERS_P2)
                    for w in widgets:
                        w.surface = screen
                        w.invalidate()
                    settings.surface = screen

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if _GEAR_RECT.collidepoint(event.pos):
                    settings.open()
                elif _PAGE_RECT.collidepoint(event.pos):
                    current_page = (current_page % _TOTAL_PAGES) + 1
                    for w in widgets:
                        w.invalidate()

        # ── Draw ──────────────────────────────────────────────────────────────
        screen.blit(_bg_p1 if current_page == 1 else _bg_p2, (0, 0))

        # Propagate page to widgets that adapt their layout per page
        for w in widgets:
            if hasattr(w, '_page') and w._page != current_page:
                w._page = current_page
                w.invalidate()

        for w in widgets:
            # Each widget only appears on its designated page(s)
            if current_page == 1 and isinstance(w, SatelliteWidget):
                continue
            if current_page == 2 and isinstance(w, DeepSkyWidget):
                continue
            needs_draw = w._ALWAYS_DIRTY or w._dirty or w._cache_surf is None
            try:
                if needs_draw:
                    w.draw()
                    w._cache_surf = screen.subsurface(w.rect).copy()
                    w._dirty      = False
                else:
                    screen.blit(w._cache_surf, w.rect.topleft)
            except Exception as exc:
                print(f"[draw] {w.__class__.__name__}: {exc}")

        draw_gear_button(screen, _GEAR_RECT, hovered=gear_hover)
        draw_page_button(screen, _PAGE_RECT, current_page, _TOTAL_PAGES,
                         hovered=page_hover)

        settings.draw()

        pygame.display.flip()
        clock_tick.tick(config.FPS)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
