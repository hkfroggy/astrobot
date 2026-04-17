import pygame
import threading
import time
import config

_RETRY_COUNT  = 3     # attempts before giving up
_RETRY_DELAY  = 5     # seconds between retries
_ERROR_SLEEP  = 1800  # 30 min before retrying after total failure


class BaseWidget:
    """Threaded widget base. Subclasses override fetch_data() and draw()."""

    # Set True in subclasses whose visuals change every frame (e.g. clock hands).
    # False means the widget is only redrawn when new data arrives.
    _ALWAYS_DIRTY = False

    def __init__(self, surface, rect):
        self.surface      = surface
        self.rect         = pygame.Rect(rect)
        self.data         = {}
        self._lock        = threading.Lock()
        self._refresh_interval = 300
        self._dirty       = True   # draw on first frame
        self._cache_surf  = None   # last-rendered snapshot
        self._fetch_failed = False

    def start_data_fetch(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while True:
            success = self._attempt_fetch()
            if success:
                time.sleep(self._refresh_interval)
            else:
                time.sleep(_ERROR_SLEEP)

    def _attempt_fetch(self):
        """Try fetch_data() up to _RETRY_COUNT times. Returns True on success."""
        for attempt in range(_RETRY_COUNT):
            try:
                result = self.fetch_data()
                if result is not None:
                    with self._lock:
                        self.data = result
                    self._fetch_failed = False
                    self._dirty = True
                return True
            except Exception as exc:
                print(f"[{self.__class__.__name__}] fetch error "
                      f"(attempt {attempt + 1}/{_RETRY_COUNT}): {exc}")
                if attempt < _RETRY_COUNT - 1:
                    time.sleep(_RETRY_DELAY)
        # All retries exhausted
        self._fetch_failed = True
        self._dirty = True
        print(f"[{self.__class__.__name__}] all retries failed — "
              f"retrying in {_ERROR_SLEEP // 60} min")
        return False

    def fetch_data(self):
        """Override in subclasses — return a dict or None."""
        return {}

    def force_refresh(self):
        """Trigger an immediate out-of-cycle data fetch (e.g. after settings change)."""
        threading.Thread(target=self._single_fetch, daemon=True).start()

    def _single_fetch(self):
        self._attempt_fetch()

    def invalidate(self):
        """Force a full redraw on the next frame (e.g. after screen recreate)."""
        self._dirty      = True
        self._cache_surf = None

    def draw(self):
        raise NotImplementedError

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def draw_bg(self, margin=3):
        r = self.rect.inflate(-margin * 2, -margin * 2)
        pygame.draw.rect(self.surface, config.PANEL_BG, r, border_radius=6)

    def draw_error(self):
        """Render the 'unable to retrieve data' error state."""
        if not hasattr(self, '_f_err'):
            self._f_err    = self.make_font(13)
            self._f_err_sm = self.make_font(11)
        self.text("Unable to retrieve data", self._f_err, (200, 80, 70),
                  self.rect.centerx, self.rect.centery - 10, "center")
        self.text("Retrying in 30 min", self._f_err_sm, config.TEXT_LO,
                  self.rect.centerx, self.rect.centery + 8, "center")

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
