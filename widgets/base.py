import pygame
import threading
import time
import config


class BaseWidget:
    """Threaded widget base. Subclasses override fetch_data() and draw()."""

    def __init__(self, surface, rect):
        self.surface = surface
        self.rect    = pygame.Rect(rect)
        self.data    = {}
        self._lock   = threading.Lock()
        self._refresh_interval = 300

    def start_data_fetch(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while True:
            try:
                result = self.fetch_data()
                if result is not None:
                    with self._lock:
                        self.data = result
            except Exception as exc:
                print(f"[{self.__class__.__name__}] fetch error: {exc}")
            time.sleep(self._refresh_interval)

    def fetch_data(self):
        """Override in subclasses — return a dict or None."""
        return {}

    def force_refresh(self):
        """Trigger an immediate out-of-cycle data fetch (e.g. after settings change)."""
        threading.Thread(target=self._single_fetch, daemon=True).start()

    def _single_fetch(self):
        try:
            result = self.fetch_data()
            if result is not None:
                with self._lock:
                    self.data = result
        except Exception as exc:
            print(f"[{self.__class__.__name__}] refresh error: {exc}")

    def draw(self):
        raise NotImplementedError

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def draw_bg(self, margin=3):
        r = self.rect.inflate(-margin * 2, -margin * 2)
        pygame.draw.rect(self.surface, config.PANEL_BG, r, border_radius=6)

    def text(self, txt, font, color, x, y, anchor="topleft"):
        surf = font.render(str(txt), True, color)
        r    = surf.get_rect(**{anchor: (x, y)})
        self.surface.blit(surf, r)
        return r

    def loading(self, font):
        self.text("Loading…", font, config.TEXT_LO,
                  self.rect.centerx, self.rect.centery, "center")

    @staticmethod
    def make_font(size, name="dejavusans,freesans,liberationsans,arial,sans"):
        path = pygame.font.match_font(name)
        return pygame.font.Font(path, size)
