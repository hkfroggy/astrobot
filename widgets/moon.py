"""
Moon phase widget — improved rendering:
  • Larger moon disk (radius ~82 px for the 220×320 slot)
  • Lunar maria as soft dark blobs on the lit face
  • Atmospheric glow corona near full / gibbous moon
  • Limb-darkening gradient at the lunar limb
  • Cleaner text layout centred below the disk
"""
import pygame
import math
import datetime
import config
from .base import BaseWidget

try:
    import ephem
    _EPHEM = True
except ImportError:
    _EPHEM = False


# ── Lunar maria — normalised to moon radius ───────────────────────────────────
# (x, y, semi-axis-x, semi-axis-y)
# x: –1 = west limb (left as seen from N hemisphere), +1 = east limb (right)
# y: –1 = north (top), +1 = south (bottom)
_MARIA = [
    (-0.28, -0.22, 0.27, 0.22),   # Mare Imbrium
    ( 0.18, -0.28, 0.20, 0.17),   # Mare Serenitatis
    ( 0.32,  0.15, 0.19, 0.15),   # Mare Tranquillitatis
    ( 0.55,  0.03, 0.13, 0.10),   # Mare Crisium
    ( 0.42,  0.38, 0.16, 0.12),   # Mare Fecunditatis
    (-0.18,  0.38, 0.19, 0.15),   # Mare Nubium
    (-0.46,  0.06, 0.25, 0.36),   # Oceanus Procellarum
    (-0.28,  0.57, 0.12, 0.09),   # Mare Humorum
    ( 0.10,  0.03, 0.12, 0.09),   # Mare Vaporum
    ( 0.05, -0.52, 0.20, 0.07),   # Mare Frigoris
    ( 0.54,  0.38, 0.09, 0.07),   # Mare Nectaris
]

_GLOW_PAD = 14   # pixels of glow corona around the disk


def _is_lit(nx, ny, frac):
    """Return True if the normalised disk point (nx, ny) is on the lit face."""
    if frac < 0.02 or frac > 0.98:
        return False
    waxing  = frac <= 0.5
    p       = frac if waxing else 1.0 - frac
    cos_val = math.cos(p * 2 * math.pi)
    ew      = abs(cos_val)
    in_ell  = (nx * nx / max(ew * ew, 1e-8) + ny * ny) <= 1.0 if ew > 1e-4 else False
    if waxing:
        return (nx > 0 and not in_ell) if cos_val >= 0 else (nx > 0 or in_ell)
    else:
        return (nx < 0 and not in_ell) if cos_val >= 0 else (nx < 0 or in_ell)


def _render_moon_phase(r, phase_frac):
    """
    Return a pygame Surface sized (r*2 + GLOW_PAD*2)².
    The moon disk centre sits at (GLOW_PAD+r, GLOW_PAD+r) within the surface.
    """
    pad  = _GLOW_PAD
    size = r * 2 + pad * 2
    cx   = cy = pad + r

    lit_c  = config.MOON_LIT     # (232, 228, 205)
    dark_c = config.MOON_SHADOW  # ( 10,  14,  28)

    # ── 1. Build the moon disk ─────────────────────────────────────────────────
    disk = pygame.Surface((size, size), pygame.SRCALPHA)
    disk.fill((0, 0, 0, 0))

    if phase_frac < 0.02 or phase_frac > 0.98:
        # New moon — faint dark silhouette only
        pygame.draw.circle(disk, (*dark_c, 60), (cx, cy), r)
    else:
        waxing  = phase_frac <= 0.5
        p       = phase_frac if waxing else 1.0 - phase_frac
        cos_val = math.cos(p * 2 * math.pi)

        # Dark base
        pygame.draw.circle(disk, dark_c, (cx, cy), r)

        # Lit semicircle
        tmp = pygame.Surface((size, size), pygame.SRCALPHA)
        tmp.fill((0, 0, 0, 0))
        pygame.draw.circle(tmp, lit_c, (cx, cy), r)
        if waxing:
            tmp.fill((0, 0, 0, 0), pygame.Rect(0, 0, cx, size))          # erase left
        else:
            tmp.fill((0, 0, 0, 0), pygame.Rect(cx, 0, size - cx, size))  # erase right
        disk.blit(tmp, (0, 0))

        # Terminator ellipse
        ew = int(abs(cos_val) * r)
        if ew > 0:
            tmp2 = pygame.Surface((size, size), pygame.SRCALPHA)
            tmp2.fill((0, 0, 0, 0))
            er = pygame.Rect(cx - ew, cy - r, ew * 2, r * 2)
            pygame.draw.ellipse(tmp2, dark_c if cos_val > 0 else lit_c, er)
            disk.blit(tmp2, (0, 0))

        # Lunar maria (only on the lit face)
        for nx, ny, rx_n, ry_n in _MARIA:
            if not _is_lit(nx, ny, phase_frac):
                continue
            mx  = cx + int(nx * r)
            my  = cy + int(ny * r)
            mw  = max(4, int(rx_n * r * 2))
            mh  = max(3, int(ry_n * r * 2))
            # Soft-edged blob: outer at alpha 75, inner (shrunk) at 50
            shrink = max(1, mw // 5)
            for sw_off, alpha in ((0, 75), (shrink, 50)):
                sw = mw - sw_off * 2
                sh = mh - sw_off * 2
                if sw > 1 and sh > 1:
                    pygame.draw.ellipse(
                        disk,
                        (dark_c[0], dark_c[1], dark_c[2], alpha),
                        pygame.Rect(mx - sw // 2, my - sh // 2, sw, sh),
                    )

    # Clip disk to the circular boundary
    clip = pygame.Surface((size, size), pygame.SRCALPHA)
    clip.fill((0, 0, 0, 0))
    pygame.draw.circle(clip, (255, 255, 255, 255), (cx, cy), r)
    disk.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

    # Limb darkening — soft dark ring pressed against the edge
    for dr in range(7, 0, -1):
        alpha = (8 - dr) * 10   # 70 → 10 from outer ring inward
        pygame.draw.circle(disk, (0, 0, 18, alpha), (cx, cy), r - dr + 1, dr)

    # ── 2. Composite: glow corona first, then disk on top ─────────────────────
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))

    fullness = 1.0 - abs(phase_frac - 0.5) * 2    # 0 = new moon, 1 = full moon
    if fullness > 0.4:
        intensity = int(100 * ((fullness - 0.4) / 0.6) ** 1.6)
        for dr in range(pad - 1, 1, -1):
            ga = max(0, intensity - dr * (intensity // (pad - 1) + 1))
            if ga > 0:
                pygame.draw.circle(
                    surf,
                    (lit_c[0], lit_c[1], min(255, lit_c[2] + 20), ga),
                    (cx, cy), r + dr, 2,
                )

    surf.blit(disk, (0, 0))
    return surf


def _phase_name(frac):
    if   frac < 0.03 or frac > 0.97: return "New Moon"
    elif frac < 0.22:                 return "Waxing Crescent"
    elif frac < 0.28:                 return "First Quarter"
    elif frac < 0.47:                 return "Waxing Gibbous"
    elif frac < 0.53:                 return "Full Moon"
    elif frac < 0.72:                 return "Waning Gibbous"
    elif frac < 0.78:                 return "Last Quarter"
    else:                             return "Waning Crescent"


class MoonWidget(BaseWidget):

    def __init__(self, surface, rect):
        super().__init__(surface, rect)
        self._refresh_interval = config.ASTRO_REFRESH
        self._f_phase = self.make_font(16)
        self._f_med   = self.make_font(14)
        self._f_small = self.make_font(13)
        self._f_tiny  = self.make_font(11)
        self._moon_surf = None
        self._moon_key  = None

    # ── Data fetch ────────────────────────────────────────────────────────────

    def fetch_data(self):
        if not _EPHEM:
            return _simple_moon()

        now = datetime.datetime.now()
        obs = ephem.Observer()
        obs.lat  = str(config.LATITUDE)
        obs.lon  = str(config.LONGITUDE)
        obs.date = now

        moon  = ephem.Moon(obs)
        illum = moon.phase
        pnm   = ephem.previous_new_moon(obs.date)
        age   = float(obs.date - pnm)
        frac  = (age % 29.53) / 29.53

        def _fmt(t):
            try:    return ephem.localtime(t).strftime("%-I:%M %p")
            except: return "--"

        rise = set_t = "--"
        try:
            obs.horizon = "0"
            rise  = _fmt(obs.next_rising(moon))
            set_t = _fmt(obs.next_setting(moon))
        except Exception:
            pass

        return {
            "illum": round(illum, 1),
            "age":   round(age % 29.53, 1),
            "frac":  frac,
            "phase": _phase_name(frac),
            "rise":  rise,
            "set":   set_t,
        }

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self):
        self.draw_bg()
        if self._fetch_failed:
            self.draw_error()
            return
        with self._lock:
            d = dict(self.data)

        if not d:
            self.loading(self._f_med)
            return

        frac  = d.get("frac",  0.0)
        illum = d.get("illum", 0.0)
        phase = d.get("phase", "")
        age   = d.get("age",   0.0)
        rise  = d.get("rise",  "--")
        set_t = d.get("set",   "--")

        rx  = self.rect.x
        ry  = self.rect.y
        cx  = self.rect.centerx
        pad = _GLOW_PAD

        # ── Moon disk ─────────────────────────────────────────────────────────
        moon_r = min(self.rect.width, self.rect.height) // 2 - 34
        moon_r = max(moon_r, 50)

        key = (round(frac, 3), moon_r)
        if key != self._moon_key:
            self._moon_surf = _render_moon_phase(moon_r, frac)
            self._moon_key  = key

        # Centre the disk with glow pad fitting inside the widget top
        mc_x = cx
        mc_y = ry + moon_r + pad + 6
        self.surface.blit(self._moon_surf,
                          (mc_x - moon_r - pad, mc_y - moon_r - pad))

        # ── Phase name & illumination stats ───────────────────────────────────
        ty = mc_y + moon_r + pad + 10

        self.text(phase, self._f_phase, config.GOLD, cx, ty, "midtop")
        ty += 22

        self.text(f"{illum:.0f}% illuminated", self._f_small,
                  config.TEXT_MID, cx, ty, "midtop")
        ty += 17

        self.text(f"Day {age:.1f} of 29.5", self._f_tiny,
                  config.TEXT_LO, cx, ty, "midtop")
        ty += 20

        # ── Divider ───────────────────────────────────────────────────────────
        pygame.draw.line(self.surface, config.DIVIDER,
                         (rx + 8, ty), (rx + self.rect.width - 8, ty), 1)
        ty += 9

        # ── Rise / Set (two columns) ──────────────────────────────────────────
        col_w = self.rect.width // 2

        self.text("▲ Rise", self._f_tiny,  config.TEXT_MID, rx + 12, ty)
        self.text("▼ Set",  self._f_tiny,  config.TEXT_MID, rx + col_w + 12, ty)
        ty += 14
        self.text(rise,  self._f_small, config.TEXT_HI, rx + 12, ty)
        self.text(set_t, self._f_small, config.TEXT_HI, rx + col_w + 12, ty)


# ── Fallback moon calculation (no ephem) ─────────────────────────────────────

def _simple_moon():
    """Approximate phase without ephem (~1 day accuracy)."""
    known_new = datetime.date(2000, 1, 6)
    today     = datetime.date.today()
    days      = (today - known_new).days
    age       = days % 29.53059
    frac      = age / 29.53059
    illum     = 50 * (1 - math.cos(frac * 2 * math.pi))
    return {
        "illum": round(illum, 1),
        "age":   round(age, 1),
        "frac":  frac,
        "phase": _phase_name(frac),
        "rise":  "--",
        "set":   "--",
    }
