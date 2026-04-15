# AstroBot — Installation & Deployment

Step-by-step guide to running AstroBot on a Raspberry Pi with a 7-inch display.

---

## 1. Flash Raspberry Pi OS

Use **[Raspberry Pi Imager](https://www.raspberrypi.com/software/)** to flash
**Raspberry Pi OS Lite (64-bit)** onto a microSD card.
In the imager's advanced settings (⚙), pre-configure:

- Wi-Fi SSID and password
- SSH enabled
- Username and password (default: `pi`)
- Locale / timezone

> Raspberry Pi OS Lite (no desktop) is recommended for a dedicated dashboard —
> lighter, faster boot. If you prefer the full desktop, that works too.

---

## 2. First Boot & SSH

Insert the SD card, power on, then connect:

```bash
ssh pi@raspberrypi.local
```

Update the system:

```bash
sudo apt update && sudo apt upgrade -y
```

---

## 3. Install System Dependencies

pygame requires several SDL2 libraries; ephem requires a C compiler.

```bash
sudo apt install -y \
    python3-pip python3-venv python3-dev \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libfreetype6-dev libportmidi-dev \
    git gcc
```

---

## 4. Clone the Repository

```bash
cd ~
git clone https://github.com/hkfroggy/astrobot.git
cd astrobot
```

---

## 5. Create Virtual Environment & Install Python Packages

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Verify the install (with a monitor attached):

```bash
.venv/bin/python main.py --windowed
```

---

## 6. Configure Your Display

Edit the boot config for your 7-inch screen:

```bash
# Pi 3 / Pi 4
sudo nano /boot/config.txt

# Pi 5
sudo nano /boot/firmware/config.txt
```

Add or adjust the following block:

```ini
# Force HDMI output even when no monitor is detected at boot
hdmi_force_hotplug=1

# Custom resolution — 1024×640 @ 60 Hz
hdmi_group=2
hdmi_mode=87
hdmi_cvt=1024 640 60 6 0 0 0

# Remove black border around the image
disable_overscan=1
```

> Check your display's manual for the exact `hdmi_cvt` values.
> Some 7-inch HDMI screens use 1024×600 or 800×480 instead.

Reboot to apply:

```bash
sudo reboot
```

---

## 7. Disable Screen Blanking

The dashboard should never sleep or go black.

**Option A — raspi-config (easiest):**

```bash
sudo raspi-config
# → Display Options → Screen Blanking → Disabled
```

**Option B — rc.local:**

```bash
sudo nano /etc/rc.local
```

Add before `exit 0`:

```bash
setterm --blank 0 --powerdown 0 --powersave off
```

---

## 8. Edit config.py

Set your location, units, and NOAA tide station before running:

```bash
nano ~/astrobot/config.py
```

```python
LATITUDE      = 34.05          # decimal degrees N (negative = S)
LONGITUDE     = -118.24        # decimal degrees E (negative = W)
TIMEZONE      = "America/Los_Angeles"
LOCATION_NAME = "Los Angeles, CA"
TEMP_UNIT     = "F"            # "F" = Fahrenheit  |  "C" = Celsius
NOAA_STATION_ID = "9410660"    # leave "" to disable tides
```

Find your NOAA station ID at:
https://tidesandcurrents.noaa.gov/tide_predictions.html

These settings can also be changed at runtime via the ⚙ gear button.

---

## 9. Run on Boot with systemd

Create the service file:

```bash
sudo nano /etc/systemd/system/astrobot.service
```

**For desktop-based Pi OS (LXDE / Wayfire):**

```ini
[Unit]
Description=AstroBot Dashboard
After=network-online.target graphical.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/astrobot
Environment=DISPLAY=:0
Environment=SDL_VIDEODRIVER=x11
ExecStart=/home/pi/astrobot/.venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
```

**For Lite OS (framebuffer, no desktop):**

```ini
[Unit]
Description=AstroBot Dashboard
After=network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/astrobot
Environment=SDL_VIDEODRIVER=fbcon
Environment=SDL_FBDEV=/dev/fb0
ExecStart=/home/pi/astrobot/.venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable astrobot.service
sudo systemctl start astrobot.service
```

---

## 10. Verify

```bash
# Check service status
sudo systemctl status astrobot.service

# Stream live logs
journalctl -u astrobot.service -f
```

---

## Updating

Pull the latest code and restart:

```bash
cd ~/astrobot
git pull
sudo systemctl restart astrobot.service
```

---

## Quick Reference

| Task | Command |
|---|---|
| Start | `sudo systemctl start astrobot` |
| Stop | `sudo systemctl stop astrobot` |
| Restart | `sudo systemctl restart astrobot` |
| Enable on boot | `sudo systemctl enable astrobot` |
| Disable on boot | `sudo systemctl disable astrobot` |
| View live logs | `journalctl -u astrobot -f` |
| Update code | `cd ~/astrobot && git pull && sudo systemctl restart astrobot` |
| Edit config | `nano ~/astrobot/config.py` |

---

## Troubleshooting

**App doesn't start / blank screen**
- Check logs: `journalctl -u astrobot -f`
- Confirm the display resolution in `/boot/config.txt`
- Try running manually first: `cd ~/astrobot && .venv/bin/python main.py`

**pygame can't find a display**
- Ensure `DISPLAY=:0` is set in the service (desktop) or `SDL_VIDEODRIVER=fbcon` (Lite)
- On desktop OS, the service must start *after* the graphical session

**No weather / tide data**
- Confirm the Pi has internet access: `ping open-meteo.com`
- Check `config.py` for correct timezone string (must match IANA format, e.g. `America/Los_Angeles`)

**Ephem not found**
- Re-run: `cd ~/astrobot && .venv/bin/pip install ephem`
- The app runs without it but moon/sky calculations fall back to approximations

**Wrong tide data**
- Verify `NOAA_STATION_ID` in `config.py` matches your nearest US coastal station
- Non-US users: set `NOAA_STATION_ID = ""` — swell data from Open-Meteo still works globally
