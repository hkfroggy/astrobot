"""
Satellite loop widget — page 2 bottom-left slot (0, 300, 360, 300).

Data: NICT Himawari-8/9 true-colour satellite imagery.
      https://himawari8.nict.go.jp/img/D531106/latest.json
      No API key required.  Updated every ~10 minutes.

Downloads a 2×2 tile grid at zoom-4 (each tile ~40°, grid ~80°×80°),
then crops an 800×800 px region centered on config.LATITUDE/LONGITUDE
so the configured location always sits in the middle of the frame.
"""
import pygame
import math
import io
import time
import threading
from datetime import datetime, timedelta, timezone
import requests
import config
from .base import BaseWidget

# ── Constants ─────────────────────────────────────────────────────────────────
_BASE_URL    = "https://himawari8.nict.go.jp/img/D531106"
_LATEST_URL  = f"{_BASE_URL}/latest.json"
_TILE_PX     = 550      # pixel size of each downloaded tile
_ZOOM        = 4        # Himawari tile-grid zoom level (4 = 4×4 full-disk grid)
_GRID        = 2        # download a _GRID×_GRID block of tiles per frame
_CROP_SIZE   = 580      # crop a square this many px from the stitched image
_FRAME_MINS  = 10       # Himawari update cadence (minutes)
_HOURS_BACK  = 4        # loop window (hours)
_FRAME_COUNT = (_HOURS_BACK * 60) // _FRAME_MINS   # 24 frames
_FRAME_SEC   = 0.8      # seconds per animation frame

# ── City labels shown on the map ─────────────────────────────────────────────
_CITIES = [
    ("Sydney",    -33.87,  151.21),
    ("Brisbane",  -27.47,  153.03),
    ("Melbourne", -37.81,  144.96),
]

# ── Proper Himawari geostationary projection ──────────────────────────────────
# Based on CGMS LRIT/HRIT specification (equal-angle scan mapping).
_LON0   = math.radians(140.7)   # Himawari sub-satellite longitude
_H      = 42164.0                # km — satellite distance from Earth centre
_A      = 6378.137               # km — Earth equatorial radius
_B      = 6356.752               # km — Earth polar radius
_E2     = 1.0 - (_B / _A) ** 2  # first eccentricity squared
# Angular radius of the Earth disk as seen from the satellite (radians).
# Used as the half-FOV for the equal-angle pixel mapping.
_SCAN_MAX = math.asin(_A / _H)   # ≈ 0.1517 rad ≈ 8.69°


def _latlon_to_scan(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    """
    Geographic (geodetic) lat/lon → geostationary scan angles in radians.
    x > 0 = East of nadir;  y > 0 = North of nadir.
    """
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    # Normal-section radius of curvature (prime vertical)
    N   = _A / math.sqrt(1.0 - _E2 * math.sin(lat) ** 2)
    dlon = lon - _LON0
    # Geocentric Cartesian components of the surface point
    r1 = _H - N * math.cos(lat) * math.cos(dlon)
    r2 = -N  * math.cos(lat) * math.sin(dlon)
    r3 =  N  * (1.0 - _E2)   * math.sin(lat)
    rn = math.sqrt(r1 * r1 + r2 * r2 + r3 * r3)
    x  = math.atan(-r2 / r1)      # E–W   (East = positive)
    y  = math.asin( r3 / rn)      # N–S   (North = positive)
    return x, y


def _scan_to_composite_px(x: float, y: float) -> tuple[float, float]:
    """Scan angles → pixel in the full (_ZOOM × _TILE_PX) composite canvas."""
    total = _ZOOM * _TILE_PX
    scale = (total / 2.0) / _SCAN_MAX
    col   = total / 2.0 + x * scale
    row   = total / 2.0 - y * scale   # row increases southward
    return col, row


def _tile_origin(lat: float, lon: float) -> tuple[int, int]:
    """Top-left (col0, row0) of the _GRID×_GRID block that best centres lat/lon."""
    col, row = _scan_to_composite_px(*_latlon_to_scan(lat, lon))
    col0 = int(max(0, min(_ZOOM - _GRID, round(col / _TILE_PX - _GRID / 2))))
    row0 = int(max(0, min(_ZOOM - _GRID, round(row / _TILE_PX - _GRID / 2))))
    return col0, row0


def _pixel_in_grid(lat: float, lon: float,
                   col0: int, row0: int) -> tuple[int, int]:
    """Pixel position of lat/lon inside the stitched _GRID×_GRID image."""
    col, row = _scan_to_composite_px(*_latlon_to_scan(lat, lon))
    return int(col - col0 * _TILE_PX), int(row - row0 * _TILE_PX)


class SatelliteWidget(BaseWidget):

    _ALWAYS_DIRTY = True   # animation advances every frame

    def __init__(self, surface, rect):
        super().__init__(surface, rect)
        self._refresh_interval = 600   # re-fetch frame list every 10 min

        # Thread-shared frame store:
        #   list of (label_str, [bytes_or_None × _GRID*_GRID])
        #   tile order: row-major (row0+0,col0+0), (row0+0,col0+1), ...
        self._frames: list  = []
        self._bytes_lock    = threading.Lock()

        # Main-thread surface cache: frame_idx → cropped pygame.Surface
        self._surf_cache: dict = {}

        self._frame_idx    = 0
        self._last_advance = time.time()
        self._spin_tick    = 0

        self._f_hdr   = self.make_font(12)
        self._f_small = self.make_font(11)
        self._f_tiny  = self.make_font(10)

    # ── Background fetch loop ─────────────────────────────────────────────────

    def _loop(self):
        """Override: kick off frame downloads after each successful fetch."""
        from .base import _ERROR_SLEEP
        while True:
            ok = self._attempt_fetch()
            if ok:
                threading.Thread(
                    target=self._load_frames, daemon=True
                ).start()
                time.sleep(self._refresh_interval)
            else:
                time.sleep(_ERROR_SLEEP)

    def fetch_data(self):
        """
        Fetch the latest Himawari timestamp; return the list of _FRAME_COUNT
        UTC datetimes (one every _FRAME_MINS minutes, oldest first).
        """
        r = requests.get(_LATEST_URL, timeout=10)
        r.raise_for_status()
        latest_str = r.json().get("date", "")
        latest = datetime.strptime(latest_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        frames = [
            latest - timedelta(minutes=_FRAME_MINS * i)
            for i in range(_FRAME_COUNT - 1, -1, -1)
        ]
        return {"frames": frames}

    def _load_frames(self):
        """
        Download _GRID×_GRID tiles for every frame in a background thread.
        Each frame entry: (label, [bytes_or_None * _GRID*_GRID]) row-major.
        """
        with self._lock:
            d = dict(self.data)

        frame_times = d.get("frames", [])
        if not frame_times:
            return

        col0, row0 = _tile_origin(config.LATITUDE, config.LONGITUDE)

        new_frames = []
        for dt in frame_times:
            local_dt = dt.astimezone()
            label    = local_dt.strftime("%-I:%M %p")
            tile_bytes = []
            for dr in range(_GRID):
                for dc in range(_GRID):
                    tc = col0 + dc
                    tr = row0 + dr
                    url = (
                        f"{_BASE_URL}/{_ZOOM}d/{_TILE_PX}/"
                        f"{dt.year}/{dt.month:02d}/{dt.day:02d}/"
                        f"{dt.hour:02d}{dt.minute:02d}{dt.second:02d}"
                        f"_{tc}_{tr}.png"
                    )
                    try:
                        resp = requests.get(url, timeout=20)
                        resp.raise_for_status()
                        raw = resp.content if len(resp.content) > 500 else None
                    except Exception as e:
                        print(f"[Sat] {label} tile({tc},{tr}): {e}")
                        raw = None
                    tile_bytes.append(raw)
            new_frames.append((label, tile_bytes))

        with self._bytes_lock:
            self._frames     = new_frames
            self._surf_cache.clear()
            self._frame_idx  = 0
        self._dirty = True

    # ── Surface construction (main thread) ───────────────────────────────────

    def _get_frame_surf(self, idx) -> "pygame.Surface | None":
        if idx in self._surf_cache:
            return self._surf_cache[idx]

        with self._bytes_lock:
            if idx >= len(self._frames):
                return None
            _label, tile_bytes = self._frames[idx]

        col0, row0 = _tile_origin(config.LATITUDE, config.LONGITUDE)
        stitch_w   = _GRID * _TILE_PX
        stitch_h   = _GRID * _TILE_PX

        stitched = pygame.Surface((stitch_w, stitch_h))
        stitched.fill((0, 0, 0))

        for i, raw in enumerate(tile_bytes):
            if not raw:
                continue
            dr, dc = divmod(i, _GRID)
            try:
                tile_surf = pygame.image.load(io.BytesIO(raw), "tile.png")
                stitched.blit(tile_surf, (dc * _TILE_PX, dr * _TILE_PX))
            except Exception as e:
                print(f"[Sat] decode tile {i}: {e}")

        # Crop _CROP_SIZE × _CROP_SIZE centered on the configured location
        px, py   = _pixel_in_grid(config.LATITUDE, config.LONGITUDE, col0, row0)
        cx0      = max(0, min(stitch_w - _CROP_SIZE, px - _CROP_SIZE // 2))
        cy0      = max(0, min(stitch_h - _CROP_SIZE, py - _CROP_SIZE // 2))
        crop_r   = pygame.Rect(cx0, cy0, _CROP_SIZE, _CROP_SIZE)
        cropped  = pygame.Surface((_CROP_SIZE, _CROP_SIZE))
        cropped.blit(stitched, (0, 0), crop_r)

        # Store (surface, crosshair pixel within crop)
        hx = px - cx0
        hy = py - cy0
        self._surf_cache[idx] = (cropped, hx, hy)
        return self._surf_cache[idx]

    # ── Draw ─────────────────────────────────────────────────────────────────

    def draw(self):
        self.draw_bg()
        if self._fetch_failed:
            self.draw_error()
            return

        self._spin_tick += 1

        rx = self.rect.x
        ry = self.rect.y
        cx = self.rect.centerx

        # Header
        self.text("SATELLITE  4h → Now", self._f_hdr, config.TEXT_LO,
                  rx + 6, ry + 5)

        IMG_TOP  = ry + 22
        IMG_BOT  = self.rect.bottom - 44
        IMG_H    = IMG_BOT - IMG_TOP
        IMG_W    = self.rect.width - 6
        img_rect = pygame.Rect(rx + 3, IMG_TOP, IMG_W, IMG_H)

        with self._bytes_lock:
            n_frames = len(self._frames)

        if n_frames == 0:
            pygame.draw.rect(self.surface, (6, 10, 22), img_rect)
            self._draw_spinner(img_rect)
            self.text("Downloading satellite frames…",
                      self._f_small, config.TEXT_LO, cx, IMG_BOT + 6, "midtop")
            return

        # Advance frame on timer
        now_t = time.time()
        if now_t - self._last_advance >= _FRAME_SEC:
            self._frame_idx    = (self._frame_idx + 1) % n_frames
            self._last_advance = now_t

        result = self._get_frame_surf(self._frame_idx)

        if result:
            surf, hx, hy = result
            fw, fh = surf.get_size()
            scale  = min(IMG_W / fw, IMG_H / fh)
            dw, dh = int(fw * scale), int(fh * scale)
            scaled = pygame.transform.smoothscale(surf, (dw, dh))

            bx = rx + 3 + (IMG_W - dw) // 2
            by = IMG_TOP + (IMG_H - dh) // 2
            self.surface.blit(scaled, (bx, by))

            # Crosshair at configured location (centered in crop)
            mx = bx + max(4, min(dw - 4, int(hx * scale)))
            my = by + max(4, min(dh - 4, int(hy * scale)))
            arm = 7
            pygame.draw.line(self.surface, (255, 80, 80),
                             (mx - arm, my), (mx + arm, my), 1)
            pygame.draw.line(self.surface, (255, 80, 80),
                             (mx, my - arm), (mx, my + arm), 1)
            pygame.draw.circle(self.surface, (255, 80, 80), (mx, my), 3, 1)

            # ── City dot + label for fixed Australian cities ──────────────
            col0_, row0_ = _tile_origin(config.LATITUDE, config.LONGITUDE)
            stitch_sz    = _GRID * _TILE_PX
            px0, py0     = _pixel_in_grid(config.LATITUDE, config.LONGITUDE,
                                          col0_, row0_)
            _cx0 = max(0, min(stitch_sz - _CROP_SIZE, px0 - _CROP_SIZE // 2))
            _cy0 = max(0, min(stitch_sz - _CROP_SIZE, py0 - _CROP_SIZE // 2))

            for cname, clat, clon in _CITIES:
                cpx, cpy = _pixel_in_grid(clat, clon, col0_, row0_)
                chx = cpx - _cx0
                chy = cpy - _cy0
                # Skip if outside the visible crop
                if not (0 <= chx <= _CROP_SIZE and 0 <= chy <= _CROP_SIZE):
                    continue
                cmx = bx + max(2, min(dw - 2, int(chx * scale)))
                cmy = by + max(2, min(dh - 2, int(chy * scale)))
                # City name only — no dot marker
                c_surf = self._f_tiny.render(cname, True, (255, 255, 255))
                cw, ch = c_surf.get_size()
                pad    = 2
                clx    = cmx - cw // 2          # horizontally centred on position
                cly    = cmy - ch // 2
                # Keep inside image bounds
                clx = max(bx + 2, min(bx + dw - cw - 2, clx))
                cly = max(by + 2, min(by + dh - ch - 2, cly))
                cpill = pygame.Rect(clx - pad, cly - pad,
                                    cw + pad * 2, ch + pad * 2)
                ps = pygame.Surface((cpill.w, cpill.h), pygame.SRCALPHA)
                ps.fill((0, 0, 0, 150))
                self.surface.blit(ps, cpill.topleft)
                self.surface.blit(c_surf, (clx, cly))

            # ── Configured location label ─────────────────────────────────────
            city = config.LOCATION_NAME
            lbl_surf = self._f_tiny.render(city, True, (255, 220, 200))
            lw, lh  = lbl_surf.get_size()
            pad     = 3
            lx      = mx + arm + 4
            ly      = my - lh // 2
            # Keep label inside image bounds
            if lx + lw + pad > bx + dw:
                lx = mx - arm - lw - pad - 4
            pill = pygame.Rect(lx - pad, ly - pad, lw + pad * 2, lh + pad * 2)
            pill_surf = pygame.Surface((pill.w, pill.h), pygame.SRCALPHA)
            pill_surf.fill((0, 0, 0, 160))
            self.surface.blit(pill_surf, pill.topleft)
            self.surface.blit(lbl_surf, (lx, ly))
        else:
            pygame.draw.rect(self.surface, (6, 10, 22), img_rect)
            self._draw_spinner(img_rect)

        pygame.draw.rect(self.surface, config.DIVIDER, img_rect, 1)

        # ── Footer ────────────────────────────────────────────────────────────
        with self._bytes_lock:
            if self._frame_idx < len(self._frames):
                frame_label = self._frames[self._frame_idx][0]
            else:
                frame_label = "--"

        is_latest = (self._frame_idx == n_frames - 1)
        lbl_clr   = config.CYAN if is_latest else config.TEXT_HI
        lbl_text  = frame_label + ("  ◀ NOW" if is_latest else "")
        self.text(lbl_text, self._f_small, lbl_clr, cx, IMG_BOT + 4, "midtop")

        # Progress bar
        bar_y  = IMG_BOT + 20
        bar_x0 = rx + 8
        bar_w  = self.rect.width - 16
        bar_h  = 4
        pygame.draw.rect(self.surface, (22, 32, 58),
                         pygame.Rect(bar_x0, bar_y, bar_w, bar_h), border_radius=2)
        filled = int(bar_w * (self._frame_idx + 1) / max(n_frames, 1))
        if filled:
            pygame.draw.rect(self.surface, config.CYAN,
                             pygame.Rect(bar_x0, bar_y, filled, bar_h), border_radius=2)

        self.text("4h ago", self._f_tiny, config.TEXT_LO, bar_x0,     bar_y + 7)
        self.text("Now",    self._f_tiny, config.TEXT_LO,
                  bar_x0 + bar_w, bar_y + 7, "topright")

        cached = len(self._surf_cache)
        if cached < n_frames:
            self.text(f"loading {cached}/{n_frames}",
                      self._f_tiny, (100, 130, 160), cx, bar_y + 7, "midtop")

    def _draw_spinner(self, rect):
        cx, cy = rect.centerx, rect.centery
        for i in range(8):
            a   = math.radians(i * 45 + self._spin_tick * 8)
            age = (self._spin_tick - i * 3) % 24
            alp = max(40, 220 - age * 22)
            px  = cx + int(18 * math.cos(a))
            py  = cy + int(18 * math.sin(a))
            pygame.draw.circle(self.surface, (*config.TEXT_MID, alp), (px, py), 3)
