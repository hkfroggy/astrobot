"""
Deep-sky object widget.

Images loaded from the local library in assets/dso/ (run download_dso_images.py
once to populate).  Falls back to CDS HiPS2FITS network fetch if a file is
missing, then saves it locally for future use.
Falls back to procedural placeholder art when offline.
"""
import pygame
import math
import io
import re
import datetime
import time
import threading
import requests
from pathlib import Path
import config
from .base import BaseWidget

try:
    import ephem
    _EPHEM = True
except ImportError:
    _EPHEM = False

# ── Layout inside the 360×300 widget ─────────────────────────────────────────
_MARGIN   =  3
_HDR_H    = 22      # "TONIGHT'S DSO" bar
_IMG_W    = 354     # 360 – 2×margin
_IMG_H    = 194     # image height
_INFO_TOP = _HDR_H + _IMG_H   # y-offset where info text starts

# ── CDS HiPS2FITS endpoints ────────────────────────────────────────────────────
_HIPS_BASE  = "https://alasky.cds.unistra.fr/hips-image-services/hips2fits"
_HIPS_BASE2 = "https://hips2fits.astropy.org/hips2fits"
_HIPS_SURVEY_PRIMARY  = "CDS/P/DSS2/color"
_HIPS_SURVEY_FALLBACK = "CDS/P/2MASS/color"

# ── Local image library ───────────────────────────────────────────────────────
_LOCAL_DIR = Path(__file__).parent.parent / "assets" / "dso"
_FOV_SCALE = 2.0   # zoom out by 50 %


def _local_path(name: str) -> Path:
    safe = name.replace(" ", "_").replace("/", "_")
    return _LOCAL_DIR / f"{safe}.jpg"


def _load_image_bytes(obj: dict) -> "bytes | None":
    """Return JPEG bytes for obj — local file first, then network."""
    name  = obj["name"]
    local = _local_path(name)

    if local.exists():
        try:
            return local.read_bytes()
        except Exception as e:
            print(f"[DSO img] local read {name}: {e}")

    # Network fallback
    ra  = _ra_to_deg(obj["ra"])
    dec = _dec_to_deg(obj["dec"])
    fov = obj.get("fov", 0.7) * _FOV_SCALE

    for base in (_HIPS_BASE, _HIPS_BASE2):
        for survey in (_HIPS_SURVEY_PRIMARY, _HIPS_SURVEY_FALLBACK):
            try:
                r = requests.get(base, params={
                    "hips": survey, "width": _IMG_W, "height": _IMG_H,
                    "fov": fov, "ra": f"{ra:.5f}", "dec": f"{dec:.5f}",
                    "projection": "TAN", "format": "jpg",
                }, timeout=20)
                r.raise_for_status()
                if len(r.content) > 500:
                    try:
                        _LOCAL_DIR.mkdir(parents=True, exist_ok=True)
                        local.write_bytes(r.content)
                    except Exception:
                        pass
                    return r.content
            except Exception as e:
                print(f"[DSO img] {name} {base} ({survey}): {e}")

    return None


# ── Catalog ───────────────────────────────────────────────────────────────────
# name, common, type, RA (h:m:s), Dec (±d:m:s), mag, const, fov_deg
_CATALOG = [
    ("M31",     "Andromeda Galaxy",       "Galaxy",     "0:42:44",  "+41:16:09",  3.4,  "And", 3.2),
    ("M33",     "Triangulum Galaxy",      "Galaxy",     "1:33:51",  "+30:39:37",  5.7,  "Tri", 1.2),
    ("M42",     "Orion Nebula",           "Nebula",     "5:35:17",  "-05:23:28",  4.0,  "Ori", 1.2),
    ("M45",     "Pleiades",               "Cluster",    "3:47:24",  "+24:07:00",  1.6,  "Tau", 2.2),
    ("M51",     "Whirlpool Galaxy",       "Galaxy",     "13:29:53", "+47:11:43",  8.4,  "CVn", 0.25),
    ("M57",     "Ring Nebula",            "Neb (PN)",   "18:53:35", "+33:01:45",  8.8,  "Lyr", 0.10),
    ("M81",     "Bode's Galaxy",          "Galaxy",     "9:55:33",  "+69:03:55",  6.9,  "UMa", 0.55),
    ("M82",     "Cigar Galaxy",           "Galaxy",     "9:55:52",  "+69:40:47",  8.4,  "UMa", 0.45),
    ("M101",    "Pinwheel Galaxy",        "Galaxy",     "14:03:13", "+54:20:57",  7.9,  "UMa", 0.40),
    ("M13",     "Hercules Cluster",       "Glob.Clust", "16:41:42", "+36:27:37",  5.8,  "Her", 0.14),
    ("M27",     "Dumbbell Nebula",        "Neb (PN)",   "19:59:36", "+22:43:16",  7.5,  "Vul", 0.14),
    ("M1",      "Crab Nebula",            "SNR",        "5:34:32",  "+22:00:52",  8.4,  "Tau", 0.14),
    ("M8",      "Lagoon Nebula",          "Nebula",     "18:03:37", "-24:23:12",  6.0,  "Sgr", 0.90),
    ("M16",     "Eagle Nebula",           "Nebula",     "18:18:48", "-13:47:00",  6.4,  "Ser", 0.55),
    ("M17",     "Omega Nebula",           "Nebula",     "18:20:26", "-16:10:36",  6.0,  "Sgr", 0.55),
    ("M104",    "Sombrero Galaxy",        "Galaxy",     "12:39:59", "-11:37:23",  8.0,  "Vir", 0.30),
    ("M106",    "NGC 4258",               "Galaxy",     "12:18:57", "+47:18:14",  8.4,  "CVn", 0.40),
    ("M64",     "Black Eye Galaxy",       "Galaxy",     "12:56:44", "+21:40:58",  8.5,  "Com", 0.30),
    ("NGC7000", "North America Nebula",   "Nebula",     "20:58:47", "+44:20:00",  4.0,  "Cyg", 2.8),
    ("NGC869",  "Double Cluster (h Per)", "Cluster",    "2:19:00",  "+57:08:00",  4.3,  "Per", 1.0),
    ("IC434",   "Horsehead Nebula",       "Dark Neb",   "5:40:59",  "-02:27:30",  None, "Ori", 0.40),
    ("M97",     "Owl Nebula",             "Neb (PN)",   "11:14:48", "+55:01:08",  9.9,  "UMa", 0.10),
    ("M63",     "Sunflower Galaxy",       "Galaxy",     "13:15:49", "+42:01:45",  8.6,  "CVn", 0.30),
    ("Veil E",  "Eastern Veil Nebula",    "SNR",        "20:56:29", "+31:43:00",  None, "Cyg", 2.0),
    ("M78",     "M78 Reflection Neb.",    "Nebula",     "5:46:46",  "+00:04:45",  8.3,  "Ori", 0.30),
    ("IC5070",  "Pelican Nebula",         "Nebula",     "20:50:48", "+44:21:00",  None, "Cyg", 2.0),
    ("NGC2244", "Rosette Cluster",        "Cluster",    "6:32:24",  "+04:52:00",  4.8,  "Mon", 1.4),
    ("NGC6888", "Crescent Nebula",        "Nebula",     "20:12:07", "+38:21:18",  None, "Cyg", 0.50),
]

_TYPE_COLOR = {
    "Galaxy":     (175, 100, 255),
    "Nebula":     ( 55, 210, 215),
    "Cluster":    (255, 205,  60),
    "Glob.Clust": (255, 155,  45),
    "Neb (PN)":   ( 75, 215, 115),
    "SNR":        (255,  85,  70),
    "Dark Neb":   (145, 165, 210),
}

SLIDE_SECONDS = 10


def _ra_to_deg(s: str) -> float:
    h, m, sec = (float(x) for x in s.split(":"))
    return (h + m / 60 + sec / 3600) * 15.0


def _dec_to_deg(s: str) -> float:
    neg = s.startswith("-")
    d, m, sec = (float(x) for x in s.lstrip("+-").split(":"))
    v = d + m / 60 + sec / 3600
    return -v if neg else v


# ── Widget ────────────────────────────────────────────────────────────────────

class DeepSkyWidget(BaseWidget):

    # Slides advance every 10 s and the spinner animates — must redraw every frame
    _ALWAYS_DIRTY = True

    def __init__(self, surface, rect):
        super().__init__(surface, rect)
        self._refresh_interval = config.ASTRO_REFRESH
        self._slide_idx   = 0
        self._slide_start = time.time()
        self._spin_tick   = 0
        self._surf_cache: dict[str, "pygame.Surface | None"] = {}

        self._f_hdr   = self.make_font(13)
        self._f_name  = self.make_font(18)
        self._f_comm  = self.make_font(13)
        self._f_small = self.make_font(13)
        self._f_tiny  = self.make_font(11)

    # ── Data fetch (runs in background thread) ────────────────────────────────

    def fetch_data(self):
        """Build tonight's object list and load all image bytes from disk."""
        self._surf_cache.clear()
        objects = _build_tonight_list()
        images  = {}
        for obj in objects:
            raw = _load_image_bytes(obj)
            if raw:
                images[obj["name"]] = raw
        return {"objects": objects, "images": images}

    # ── Draw (called every frame) ─────────────────────────────────────────────

    def draw(self):
        self.draw_bg()
        if self._fetch_failed:
            self.draw_error()
            return

        with self._lock:
            objects = list(self.data.get("objects") or [])
            images  = dict(self.data.get("images")  or {})

        self._spin_tick += 1

        rx = self.rect.x
        ry = self.rect.y

        # ── Header ────────────────────────────────────────────────────────────
        self.text("TONIGHT'S DSO", self._f_hdr, config.TEXT_LO,
                  self.rect.centerx, ry + 5, "midtop")

        if not objects:
            self.text("No visible objects tonight", self._f_small, config.TEXT_LO,
                      self.rect.centerx, self.rect.centery, "center")
            return

        # ── Advance slide ─────────────────────────────────────────────────────
        if time.time() - self._slide_start >= SLIDE_SECONDS:
            self._slide_idx   = (self._slide_idx + 1) % len(objects)
            self._slide_start = time.time()

        obj  = objects[self._slide_idx % len(objects)]
        name = obj["name"]

        # ── Convert bytes → Surface (lazy, cached per-instance) ───────────────
        if name not in self._surf_cache:
            raw = images.get(name)
            if raw:
                try:
                    self._surf_cache[name] = pygame.image.load(
                        io.BytesIO(raw)
                    ).convert()
                except Exception as e:
                    print(f"[DSO img] decode {name}: {e}")
                    self._surf_cache[name] = None
            else:
                self._surf_cache[name] = None

        surf_img = self._surf_cache[name]

        # ── Image area ────────────────────────────────────────────────────────
        img_x = rx + _MARGIN
        img_y = ry + _HDR_H
        img_r = pygame.Rect(img_x, img_y, _IMG_W, _IMG_H)

        if surf_img is not None:
            # Scale to fit widget dimensions in case local file is different size
            if surf_img.get_size() != (_IMG_W, _IMG_H):
                surf_img = pygame.transform.scale(surf_img, (_IMG_W, _IMG_H))
                self._surf_cache[name] = surf_img
            self.surface.blit(surf_img, (img_x, img_y))
        else:
            pygame.draw.rect(self.surface, (6, 10, 24), img_r)
            if not images.get(name):
                # Data not yet loaded — show spinner
                self._draw_spinner(img_r)
            else:
                # Image bytes present but decode failed — procedural art
                _draw_dso_art(self.surface, obj["type"],
                              img_r.centerx, img_r.centery, 52)

        pygame.draw.rect(self.surface, config.DIVIDER, img_r, 1)

        # ── Image overlays ────────────────────────────────────────────────────
        strip_h = 38
        ov = pygame.Surface((_IMG_W, strip_h), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 175))
        self.surface.blit(ov, (img_x, img_y + _IMG_H - strip_h))

        self.text(name, self._f_name, config.TEXT_HI,
                  img_x + 8, img_y + _IMG_H - strip_h + 2)
        self.text(obj["common"], self._f_comm, config.TEXT_MID,
                  img_x + 8, img_y + _IMG_H - strip_h + 21)

        const_bg = pygame.Surface((36, 17), pygame.SRCALPHA)
        const_bg.fill((0, 0, 0, 140))
        self.surface.blit(const_bg, (img_x + _IMG_W - 39, img_y + 4))
        self.text(obj["const"], self._f_tiny, config.GOLD,
                  img_x + _IMG_W - 6, img_y + 6, "topright")

        # ── Info below image ──────────────────────────────────────────────────
        iy = ry + _INFO_TOP + 6

        type_clr = _TYPE_COLOR.get(obj["type"], config.TEXT_MID)
        self.text(obj["type"], self._f_small, type_clr, rx + 8, iy)

        mag_s = f"Mag {obj['mag']:.1f}" if obj["mag"] is not None else "Mag --"
        self.text(mag_s, self._f_small, config.TEXT_MID, rx + 130, iy)

        if obj.get("max_alt") is not None:
            self.text(f"{obj['max_alt']:.0f}° alt", self._f_small, config.GREEN,
                      rx + 240, iy)

        iy += 18
        self.text(f"Best: {obj.get('window','--')}", self._f_tiny,
                  config.TEXT_MID, rx + 8, iy)

        iy += 15
        self.text(f"Transit: {obj.get('transit','--')}", self._f_tiny,
                  config.TEXT_LO, rx + 8, iy)

        self.text("DSS2 · CDS Strasbourg", self._f_tiny, config.TEXT_LO,
                  self.rect.right - 8, iy, "topright")

        # ── Page dots ─────────────────────────────────────────────────────────
        n       = len(objects)
        dot_r   = 3
        spacing = 9
        total_w = n * (dot_r * 2 + spacing) - spacing
        dot_x0  = self.rect.centerx - total_w // 2
        dots_y  = self.rect.bottom - 12
        for i in range(n):
            clr = config.GOLD if i == self._slide_idx else config.TEXT_LO
            pygame.draw.circle(self.surface, clr,
                               (dot_x0 + i * (dot_r * 2 + spacing) + dot_r, dots_y),
                               dot_r)

    def _draw_spinner(self, rect):
        cx, cy = rect.centerx, rect.centery
        n = 8
        for i in range(n):
            a   = math.radians(i * 360 / n + self._spin_tick * 8)
            age = (self._spin_tick - i * 3) % (n * 3)
            alpha = max(40, 220 - age * 22)
            px  = cx + int(18 * math.cos(a))
            py  = cy + int(18 * math.sin(a))
            pygame.draw.circle(self.surface, (*config.TEXT_MID, alpha), (px, py), 3)
        self.text("Loading image…", self._f_tiny, config.TEXT_LO,
                  cx, cy + 30, "midtop")


# ── Procedural placeholder art ────────────────────────────────────────────────

def _draw_dso_art(surf, obj_type, cx, cy, r):
    t = obj_type
    if "Galaxy" in t:
        for a in range(0, 360, 6):
            rad  = math.radians(a)
            fade = int(80 * abs(math.cos(math.radians(a * 2))))
            px   = cx + int(r * math.cos(rad))
            py   = cy + int(r * 0.35 * math.sin(rad))
            pygame.draw.circle(surf, (80 + fade, 50 + fade // 2, 140 + fade // 2), (px, py), 1)
        pygame.draw.ellipse(surf, (100, 70, 180),
                            pygame.Rect(cx - r // 2, cy - r // 6, r, r // 3))
    elif "Nebula" in t or "SNR" in t:
        import random
        rng = random.Random(hash(obj_type) & 0xFFFF)
        for _ in range(200):
            a   = rng.uniform(0, 2 * math.pi)
            d   = rng.gauss(0, r * 0.4)
            px  = cx + int(d * math.cos(a))
            py  = cy + int(d * math.sin(a) * 0.7)
            c   = rng.choice([(40, 180, 200), (200, 100, 40), (80, 200, 120)])
            pygame.draw.circle(surf, c, (px, py), rng.randint(1, 3))
    elif "Cluster" in t:
        import random
        rng = random.Random(42)
        for _ in range(25):
            px = cx + rng.randint(-r, r)
            py = cy + rng.randint(-r // 2, r // 2)
            pygame.draw.circle(surf, (255, 230, 100), (px, py), rng.randint(1, 3))
    else:
        pygame.draw.circle(surf, config.TEXT_LO, (cx, cy), r // 2, 1)


# ── Visibility computation ────────────────────────────────────────────────────

def _in_shoot_window(transit_str: str, start_h: float, end_h: float) -> bool:
    if not transit_str or transit_str in ("--", "all night"):
        return True
    m = re.match(r"(\d+):(\d+)(AM|PM)", transit_str.upper())
    if not m:
        return True
    h, mn, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm == "PM" and h != 12: h += 12
    elif ampm == "AM" and h == 12: h = 0
    t = h + mn / 60.0
    if start_h <= end_h:
        return start_h <= t <= end_h
    else:
        return t >= start_h or t <= end_h


def _passes_filters(entry: dict) -> bool:
    mag = entry["mag"]
    fov = entry.get("fov")
    if mag is not None:
        if mag < config.DSO_MAG_MIN or mag > config.DSO_MAG_MAX:
            return False
    if fov is not None:
        if fov < config.DSO_FOV_MIN or fov > config.DSO_FOV_MAX:
            return False
    if not _in_shoot_window(entry.get("transit", "--"),
                            config.DSO_SHOOT_START, config.DSO_SHOOT_END):
        return False
    return True


def _build_tonight_list() -> list:
    if not _EPHEM:
        raw = [
            {
                "name": o[0], "common": o[1], "type": o[2],
                "ra": o[3], "dec": o[4],
                "mag": o[5], "const": o[6], "fov": o[7],
                "max_alt": None, "window": "ephem not installed", "transit": "--",
            }
            for o in _CATALOG
        ]
        return [r for r in raw if _passes_filters(r)]

    import ephem as _ephem
    now = datetime.datetime.now()
    obs = _ephem.Observer()
    obs.lat  = str(config.LATITUDE)
    obs.lon  = str(config.LONGITUDE)
    obs.date = now
    obs.horizon = "0"

    results = []
    for entry in _CATALOG:
        name, common, obj_type, ra, dec, mag, const, fov = entry

        if mag is not None and (mag < config.DSO_MAG_MIN or mag > config.DSO_MAG_MAX):
            continue
        if fov is not None and (fov < config.DSO_FOV_MIN or fov > config.DSO_FOV_MAX):
            continue

        body = _ephem.FixedBody()
        body._ra    = ra
        body._dec   = dec
        body._epoch = _ephem.J2000
        try:
            obs_t = _ephem.Observer()
            obs_t.lat  = obs.lat
            obs_t.lon  = obs.lon
            obs_t.date = obs.date
            transit_t  = obs_t.next_transit(body)
            obs_t.date = transit_t
            body.compute(obs_t)
            max_alt = float(body.alt) * 180 / math.pi
        except Exception:
            continue

        if max_alt < 20:
            continue

        obs.date = now
        body.compute(obs)

        try:
            rise  = _ephem.localtime(obs.next_rising(body)).strftime("%-I:%M%p")
            set_  = _ephem.localtime(obs.next_setting(body)).strftime("%-I:%M%p")
            trans = _ephem.localtime(obs.next_transit(body)).strftime("%-I:%M%p")
            window = f"{rise} – {set_}"
        except _ephem.NeverUpError:
            continue
        except _ephem.AlwaysUpError:
            window, trans = "all night", "--"
        except Exception:
            window, trans = "--", "--"

        rec = {
            "name": name, "common": common, "type": obj_type,
            "ra": ra, "dec": dec,
            "mag": mag, "const": const, "fov": fov,
            "max_alt": max_alt, "window": window, "transit": trans,
        }

        if not _in_shoot_window(trans, config.DSO_SHOOT_START, config.DSO_SHOOT_END):
            continue

        results.append(rec)

    results.sort(key=lambda x: -(x["max_alt"] or 0))
    return results[:10]
