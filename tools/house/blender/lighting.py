"""Time-of-day lighting (stage 6, 2026-10-20).

    import lighting; lighting.apply(bpy.context.scene, "evening")

Presets:
  noon     the approved baseline: Poly Haven HDRI kloofendal_43d_clear_puresky (CC0) turned so its sun
           lies front-left (SUN_TO, the house faces south); the sun lamp is off because the HDRI carries
           the sun; daylight only: electric lamps off, ceiling "Daylight fill" lights stand in for bounce
  morning  low warm sun from the front left, physical sky (multiple scattering) with the same sun
  evening  lower, redder sun from the front right; interior lamps already on
  night    sun below the horizon (deep blue sky), a faint cool moon lamp, every interior lamp and
           the fire at full strength
The world is rebuilt on every call; lamps, glow materials, exposure and the haze colour of the
"Aerial perspective" compositor group are set from the preset. build_all.sh ends on "noon", so the
saved file is always the baseline.
"""
import bpy, math, os
from mathutils import Vector

# 10-20: the house faces south (open front = -y = south); the midday sun comes from the front-left
SUN_TO = Vector((-0.45, -0.62, 0.64)).normalized()

#            sun dir (x, y, elev deg), lamp W/m2, lamp colour, sky strength, interior x, exposure, haze
PRESETS = {
    # noon: daylight only, every electric lamp off (user, 10-20); the fire keeps burning
    "noon":    dict(sun=None, lamp=0.0, lamp_col=(1.0, 0.96, 0.9), sky=1.0, interior=0.0, exposure=1.1, fill=0.0,
                    haze=(0.6, 0.68, 0.78)),
    "morning": dict(sun=(-0.8, -0.6, 14.0), lamp=3.2, lamp_col=(1.0, 0.82, 0.62), sky=0.35, interior=0.0, fill=0.6,
                    exposure=0.3, haze=(0.78, 0.74, 0.74)),
    "evening": dict(sun=(0.85, -0.5, 5.0), lamp=2.6, lamp_col=(1.0, 0.58, 0.32), sky=0.35, interior=1.6, fill=0.25,
                    exposure=0.5, haze=(0.85, 0.66, 0.55)),
    "night":   dict(sun=(0.3, 0.9, -7.0), lamp=0.06, lamp_col=(0.62, 0.72, 1.0), sky=0.35, interior=3.0, fill=0.0,
                    exposure=2.2, haze=(0.10, 0.13, 0.22), moon=(-0.5, -0.4, 35.0)),
}
# Interior close-ups are exposed like an indoor photo: this many stops above the preset (the overview
# keeps the preset, exposed for the outdoors). Daylight only - no fill lights (user, 10-20).
INTERIOR_PHOTO_EV = 1.7
LAMP_BASE = {}       # interior lamp energies at "noon" (the values the interior scripts set)
GLOW_BASE = {}


def _dir(x, y, elev):
    h = Vector((x, y, 0)).normalized()
    e = math.radians(elev)
    return Vector((h.x * math.cos(e), h.y * math.cos(e), math.sin(e)))


def _world(sc, p):
    w = sc.world
    w.use_nodes = True
    N, L = w.node_tree.nodes, w.node_tree.links
    N.clear()
    bg = N.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = p["sky"]
    if p["sun"] is None:
        tex = os.path.join(os.path.dirname(bpy.data.filepath), "textures", "hdri", "kloofendal_43d_clear_puresky_2k.exr")
        env = N.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(tex, check_existing=True)
        tc, mp = N.new("ShaderNodeTexCoord"), N.new("ShaderNodeMapping")
        # Blender equirect: u = atan2(d.y, -d.x) / 2pi + 0.5; the HDRI sun at u 0.60 -> atan2(y, -x) = 0.2 pi
        hdri_az = math.atan2(math.sin(0.2 * math.pi), -math.cos(0.2 * math.pi))
        mp.inputs["Rotation"].default_value = (0, 0, hdri_az - math.atan2(SUN_TO.y, SUN_TO.x))
        L.new(tc.outputs["Generated"], mp.inputs[0])
        L.new(mp.outputs[0], env.inputs[0])
        L.new(env.outputs[0], bg.inputs[0])
    else:
        d = _dir(*p["sun"])
        sky = N.new("ShaderNodeTexSky")
        sky.sky_type = 'MULTIPLE_SCATTERING'
        sky.sun_disc = False                          # the sun lamp gives the direct light and shadows
        sky.sun_elevation = math.asin(d.z)
        # Cycles: sun direction azimuth atan2(y, x) = sun_rotation + pi/2
        sky.sun_rotation = (math.atan2(d.y, d.x) - math.pi / 2) % (2 * math.pi)
        L.new(sky.outputs[0], bg.inputs[0])
    L.new(bg.outputs[0], N.new("ShaderNodeOutputWorld").inputs["Surface"])


def _sun_lamp(sc, p):
    sun = bpy.data.objects["Sun"]
    src = p.get("moon") or p["sun"]
    if src is not None:
        d = _dir(*src)
        sun.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()    # lamp shines along -Z
    sun.data.energy = p["lamp"]
    sun.data.color = p["lamp_col"]
    sun.data.angle = math.radians(0.53)


def apply(sc, name):
    p = PRESETS[name]
    _world(sc, p)
    _sun_lamp(sc, p)
    for o in bpy.data.objects:
        if o.type == 'LIGHT' and o.name.startswith("Daylight fill"):     # sky bounce stand-in, scales with daylight
            base = LAMP_BASE.setdefault(o.name, o.get("base_energy", o.data.energy))
            o["base_energy"] = base
            o.data.energy = base * p.get("fill", 0.0)
        elif o.type == 'LIGHT' and o.data.type in ('POINT', 'SPOT'):
            base = LAMP_BASE.setdefault(o.name, o.get("base_energy", o.data.energy))
            o["base_energy"] = base
            fire = o.name.startswith("Fireplace")                       # the fire is not switched off by day
            o.data.energy = base * (max(1.0, p["interior"]) if fire else p["interior"])
    for mn in ("Lamp glow", "Flame", "Flame core"):
        m = bpy.data.materials.get(mn)
        if not m:
            continue
        for n in m.node_tree.nodes:
            s = n.inputs.get("Emission Strength") or (n.inputs.get("Strength") if n.type == 'EMISSION' else None)
            if s is not None:
                key = f"{mn}/{n.name}"
                base = GLOW_BASE.setdefault(key, m.get("base_" + n.name, s.default_value))
                m["base_" + n.name] = base
                if mn == "Lamp glow":                                    # bulbs follow the lamps (off by day)
                    s.default_value = base * p["interior"]
                else:
                    s.default_value = base * max(1.0, p["interior"] * 0.8)
    # exposure in stops, applied as Cycles film exposure (the view-transform exposure had no visible effect)
    sc.view_settings.exposure = 0.0
    sc.cycles.film_exposure = 2.0 ** p["exposure"]
    cg = bpy.data.node_groups.get("Aerial perspective")
    if cg and "Haze" in cg.nodes:
        cg.nodes["Haze"].inputs[7].default_value = (*p["haze"], 1)
    sc["time_of_day"] = name
