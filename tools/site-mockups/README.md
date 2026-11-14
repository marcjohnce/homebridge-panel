# Mockups for the project page

`wall-hyperpixel-square.html` draws a Raspberry Pi with a HyperPixel 4.0 Square (720 × 720) on an
acoustic slat wall, to scale (44 px per cm). The screen shows `site/assets/screens/dark-720x720-home-light.webp`,
so re-render after `python tools/site_screenshots.py`:

```bash
google-chrome --headless=new --hide-scrollbars --allow-file-access-from-files \
  --window-size=1600,1000 --force-device-scale-factor=2 \
  --screenshot=wall.png "file://$PWD/tools/site-mockups/wall-hyperpixel-square.html"
```

Then save it as `site/assets/wall-hyperpixel-square.webp` (2400 × 1500) and
`site/assets/wall-hyperpixel-square-1200.webp` (1200 × 750).
