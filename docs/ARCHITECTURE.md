# BoAYo desktop shell

BoAYo owns one complete BOSIO scene. BOSIO rotates and scans that finished
scene; it does not draw BoAYo's window captions.

```text
PYNQ buttons + sensor pose
          |
          v
BoAYoShell (gaze, hit testing, internal move/resize/close)
          |
          v
640x360 black canvas (white content + caption controls)
          |
          v
BoayoScene -> existing BOSIO scene packer -> BosioV2 output core
```

The caption order is left resize, close, move, right resize. A gaze-focused
caption grows by 12 percent and brightens. The white rectangular area remains
application content; all surrounding pixels belong to the black BoAYo desktop.

Generate a host-side preview. The default preview reconstructs the 1280x720
view after 20-face/211-tile/MxM triangular-cell sampling and RGB332 palette
quantization. `--preview-source` is only for inspecting the clean source canvas:

```sh
python3 boayo_desktop.py --preview boayo.png
python3 boayo_desktop.py --preview boayo-move.png --preview-focus move
python3 boayo_desktop.py --preview boayo-source.png --preview-source
```

Run on PYNQ-Z2 with the existing BOSIO v2 bitstream and libraries:

```sh
sudo python3 boayo_desktop.py --bitstream /path/to/bosio_v2.bit --m 32
```

BTN0 activates the gaze-focused element and keeps move/resize active while
held. BTN1 reopens the sample internal window after closing it. If sensor axes
are reversed on a particular mounting, use `--gaze-yaw-sign -1` and/or
`--gaze-pitch-sign -1`.

`libbosio_compositor.so` is not rebuilt or used for BoAYo caption composition.
The existing scene-packing path remains usable unchanged.
