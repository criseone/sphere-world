# Sphere World

A small Three.js app that wraps an equirectangular panorama on an inverted sphere, lets you place N "virtual cameras" inside it, renders each camera to its own monitor canvas, and projects every camera's frustum back onto the panorama as a curved rectangle. It also has an optional 3-layer depth-parallax mode (concentric transparent spheres) and an Overview mode that flies you outside the whole scene with `OrbitControls` + `TransformControls` handles.

No build step. Just static files and an ESM import-map.

## Live demo

Clone, serve statically, open `index.html`.

## Run it locally

```bash
git clone https://github.com/criseone/sphere-world.git
cd sphere-world
python3 -m http.server 8765   # any static server works
open http://localhost:8765
```

A static server is required — ES module imports refuse to run from `file://`.

## Controls

| Action | Inside mode | Overview mode |
|---|---|---|
| Look around / orbit | drag | drag |
| Pan | — | right-drag |
| Move | `W` `A` `S` `D`, `Q`/`E` for up/down | wheel zoom |
| Zoom | wheel = FOV | wheel = dolly |
| Recenter | `R` | `R` |
| Select a camera | click its body | click its body |
| Translate selected camera | `T`, then drag arrows | `T`, then drag arrows |
| Rotate selected camera | `R`, then drag rings | `R`, then drag rings |
| Deselect | `Esc` | `Esc` |

Right panel:
- `+ Camera` adds a new monitor (capped at ~10 by browser GL-context limits)
- `depth` toggles the 3-layer depth-parallax mode
- `overview` flies outside the sphere with orbit controls
- `Save` / `Load` round-trip the full setup as JSON
- Per-camera: yaw / pitch / fov / X-Y-Z offset sliders, `16:9`/`9:16` orientation toggle, `×` removes

## Files

```
index.html              layout, styles, importmap, mounts main.js
main.js                 entire app (~600 lines)
test.jpg                720×360 equirectangular source image (2:1)
depth_far.png           sky / horizon layer with alpha mask
depth_mid.png           midground band with alpha mask
depth_near.png          floor / foreground spheres with alpha mask
build_depth_layers.py   regenerates the 3 depth PNGs from test.jpg
.claude/launch.json     dev-server config for the Claude Code preview panel
```

## How it works

### Sphere wrapping

The panorama lives on a `THREE.SphereGeometry` (radius 500, BackSide material) so the texture is visible from inside. Texture is loaded with `colorSpace = SRGBColorSpace` and `LinearFilter` to avoid mipmap seams on the 720-pixel-wide non-power-of-two source.

### Multi-camera output

Each `Monitor` instance owns:
- a `PerspectiveCamera` (added to the scene graph so `TransformControls` can grab it)
- its own `WebGLRenderer` attached to a small `<canvas>` in the right panel
- a tiny clickable `IcosahedronGeometry` body marker
- a wireframe frustum-projection gizmo (see below)

The shared `Scene` is rendered once per camera per frame. Multiple WebGL contexts means the texture/geometry is uploaded once per renderer, but for a small number of cameras this is the simplest possible architecture. If you want N > 10, swap to a single renderer with `WebGLRenderTarget` per camera and blit out via `drawImage`.

### Frustum projection gizmo

For each monitor camera, every frame:
1. Compute the four NDC corner directions from `(±1, ±1)` in camera space, transformed by the camera's quaternion.
2. Ray-cast each direction against a sphere of radius 500 (closed-form quadratic) to find where the corner lands on the panorama.
3. Sample 24 points per edge, ray-cast each one, and stitch them into `LineSegments`. The result is a curved rectangle traced across the sphere surface — exactly what the camera "sees" projected onto the panorama. Plus four straight rays from the camera apex to those four corners.

Geometry is built in **world space** every frame, so the gizmo's own transform is identity — it tracks position / rotation / FOV / offset / orientation changes for free.

### Layers for gizmo isolation

Three.js `Object3D.layers` is used to keep the gizmos / handles / body markers / axes widget out of the monitor camera renders:

- `LAYER_WORLD = 0` — spheres, panorama
- `LAYER_GIZMO = 1` — frustum lines, body markers, TransformControls helper

`mainCam.layers.enableAll()` so the main view sees both. Each `monitor.cam.layers.set(LAYER_WORLD)` so monitors only see the panorama.

### Depth parallax

When the depth toggle is on, `useDepthLayers()` swaps the single sphere for three concentric inverted spheres (radii 500 / 340 / 200) with the alpha-masked depth PNGs (`MeshBasicMaterial { transparent: true, depthWrite: false }`, `renderOrder` set so far paints first). Parallax only kicks in once you move the camera off-axis — at exact center, all three layers sample the same angle and look identical.

## Customizing

### Use your own panorama

Drop in your equirectangular image (any 2:1 aspect, JPG or PNG works) at `test.jpg`. Reload.

### Regenerate the 3 depth layers from your image

```bash
uv run --with pillow --with numpy python3 build_depth_layers.py
```

The script is brightness + Y-band heuristic — top of image becomes "far", bottom becomes "near". For real depth-aware segmentation, replace the masking logic with a depth model like MiDaS and write the resulting alpha channels to `depth_far.png` / `depth_mid.png` / `depth_near.png`. The app picks them up on reload — no other changes needed.

### Change sphere sizes

`PROJECTION_RADIUS` (in `main.js`) is the radius the frustum gizmos project onto. The depth-layer radii are inline in `useDepthLayers()`. Default: 500 / 340 / 200.

### Embed in your own Three.js app

There's no published package; the recommended path is to copy the bits you want. The most reusable units are:

- **Equirect sphere setup** — see `loadEquirectTexture()` and `useSingle()` in `main.js`. ~10 lines.
- **`makeProjectionGizmo` + `updateProjectionGizmo`** — the frustum-onto-sphere visualizer. Copy the function pair and call `updateProjectionGizmo(gizmo, camera, fovDeg, aspect)` once per frame per camera. Geometry is in world space, no parent transform needed.
- **`Monitor` class** — full pattern for "extra camera with its own canvas + handles". Heavier dependency surface (TransformControls, body marker, sliders) but a complete reference.

Minimal integration sketch — drop a panorama into an existing scene and add one frustum-projection gizmo:

```js
import * as THREE from "three";
// copy makeProjectionGizmo + updateProjectionGizmo from main.js

const sphere = new THREE.Mesh(
  new THREE.SphereGeometry(500, 64, 32),
  new THREE.MeshBasicMaterial({
    map: new THREE.TextureLoader().load("my-panorama.jpg"),
    side: THREE.BackSide,
  })
);
scene.add(sphere);

const myCam = new THREE.PerspectiveCamera(60, 16/9, 0.1, 6000);
const gizmo = makeProjectionGizmo(0x6cb6ff);
scene.add(gizmo);

function frame() {
  updateProjectionGizmo(gizmo, myCam, myCam.fov, myCam.aspect);
  renderer.render(scene, mainCam);
  requestAnimationFrame(frame);
}
```

### Preset JSON shape

Versioned, simple. Save a preset and look at the file — you can also write one by hand:

```jsonc
{
  "version": 1,
  "depth": false,
  "overview": false,
  "main": {
    "yaw": 0, "pitch": 0, "fov": 75,
    "pos": [0, 0, 0]
  },
  "cameras": [
    {
      "yaw": 0, "pitch": 0, "fov": 60,
      "offX": 0, "offY": 0, "offZ": 0,
      "orientation": "landscape"
    }
  ]
}
```

## Dependencies

- [Three.js](https://threejs.org) `r169` via `unpkg.com` ESM (`three`, `three/addons/`)
- Browser with WebGL2, ES modules, and import-map support (Chrome / Edge / Firefox / Safari current versions)

The depth-layer generator additionally needs Python 3 with `pillow` and `numpy` — `uv run --with pillow --with numpy ...` handles this without polluting your env.

## Debugging

`window.__app` exposes the live state for poking around in DevTools:

```js
__app.state         // { depth, overview, spheres }
__app.mainCam       // the user's free-flying camera
__app.monitors      // array of Monitor instances
__app.scene
__app.orbit         // OrbitControls
__app.transform     // TransformControls
__app.selectMonitor(__app.monitors[0])  // attach handles
__app.setMain({ pos: [0, 0, 200], yaw: 0, pitch: 0, fov: 60 })
```

## License

MIT — see `LICENSE` if added. Use it however.
