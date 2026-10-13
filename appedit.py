#!/usr/bin/env python3
"""Appedit: monta videosets de DJ con el estilo descrito en ESTILO.md.

Sincroniza las cámaras con la grabación de la mesa comparando el audio,
elige momentos del set, corta en el beat alternando cámara principal,
segunda cámara y un clip de recurso, y exporta un FCPXML por pieza para
importarlo en DaVinci Resolve (File > Import > Timeline).

Requisitos: Python 3.9+, numpy y ffmpeg/ffprobe en el PATH.
"""
import argparse
import html
import json
import random
import subprocess
import sys
import urllib.parse
from fractions import Fraction
from pathlib import Path

import numpy as np

SR = 4000                 # Hz a los que se analiza el audio
HOP = 40                  # muestras por punto de envolvente -> 10 ms
ENV_RATE = SR / HOP       # puntos de envolvente por segundo

VIDEO_EXT = {".mp4", ".mov", ".mxf", ".m4v", ".mts", ".avi"}

# Duración de plano en segundos medida en "b2b duro": mínimo, deciles 10..90, máximo.
DURACIONES = [0.71, 1.30, 1.67, 1.97, 2.21, 2.50, 2.84, 3.00, 3.25, 3.92, 5.5]
# Zooms usados sobre los planos de cámara (peso aproximado según el proyecto).
ZOOMS = [1.25] * 6 + [1.32] * 3 + [1.30]

NOMBRE = {"cam1": "Cámara principal", "cam2": "Segunda cámara", "rec": "Recurso"}


# ---------------------------------------------------------------- medios

def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True)
    d = json.loads(out.stdout)
    video = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    fmt_tags = d["format"].get("tags", {})
    info = {
        "path": str(Path(path).resolve()),
        "name": Path(path).name,
        "duration": float(d["format"]["duration"]),
        "fps": Fraction(video["r_frame_rate"]) if video else None,
        "width": int(video["width"]) if video else None,
        "height": int(video["height"]) if video else None,
        "audio_rate": int(audio["sample_rate"]) if audio else None,
        "audio_channels": int(audio["channels"]) if audio else None,
        "start": Fraction(0),
    }
    # Timecode de inicio: DaVinci lo usa para casar el clip, así que hay que respetarlo.
    tc = None
    for s in d["streams"]:
        tc = tc or s.get("tags", {}).get("timecode")
    tc = tc or fmt_tags.get("timecode")
    if tc and info["fps"]:
        info["start"] = timecode_a_segundos(tc, info["fps"])
    elif "time_reference" in fmt_tags and info["audio_rate"]:
        # WAV con cabecera BWF: muestras desde medianoche.
        info["start"] = Fraction(int(fmt_tags["time_reference"]), info["audio_rate"])
    return info


def timecode_a_segundos(tc, fps):
    h, m, s, f = (int(x) for x in tc.replace(";", ":").split(":"))
    base = round(fps) if fps <= 30 else round(fps / 2)   # 50p lleva timecode a 25
    return Fraction(h * 3600 + m * 60 + s) + Fraction(f, base)


def envolvente(path):
    """RMS cada 10 ms del audio del archivo, leído en bloques para no llenar la memoria."""
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
         "-ar", str(SR), "-f", "f32le", "-"],
        stdout=subprocess.PIPE)
    trozos, resto = [], np.zeros(0, np.float32)
    while True:
        buf = proc.stdout.read(HOP * 4 * 25000)
        if not buf:
            break
        x = np.concatenate([resto, np.frombuffer(buf, np.float32)])
        n = len(x) // HOP
        trozos.append(np.sqrt((x[:n * HOP].reshape(n, HOP).astype(np.float64) ** 2).mean(1)))
        resto = x[n * HOP:]
    proc.wait()
    if proc.returncode:
        sys.exit(f"ffmpeg no pudo leer el audio de {path}")
    return np.concatenate(trozos) if trozos else np.zeros(0)


def ataques(rms):
    """Curva de ataques (golpes): subidas de volumen en escala logarítmica, normalizada."""
    lg = np.log(rms + 1e-5)
    d = np.diff(lg, prepend=lg[:1])
    d[d < 0] = 0
    return (d - d.mean()) / (d.std() + 1e-9)


# ---------------------------------------------------------- sincronización

def desfase(ref, sig):
    """Segundos de `ref` en los que empieza `sig`, y una puntuación de confianza."""
    n = len(ref) + len(sig)
    N = 1 << (n - 1).bit_length()
    c = np.fft.irfft(np.fft.rfft(ref, N) * np.conj(np.fft.rfft(sig, N)), N)
    k = int(np.argmax(c))
    conf = float((c[k] - np.median(c)) / (c.std() + 1e-9))
    lag = k if k < N - len(sig) else k - N
    if 0 < k < N - 1:   # interpolación parabólica para afinar por debajo de 10 ms
        a, b, cc = c[k - 1], c[k], c[k + 1]
        den = a - 2 * b + cc
        if den:
            lag += 0.5 * (a - cc) / den
    return lag / ENV_RATE, conf


def sincronizar(mesa, archivos, cache_path):
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    clave = lambda p: f"{p}|{Path(p).stat().st_size}|{Path(p).stat().st_mtime}"
    pendientes = [a for a in archivos if clave(a["path"]) not in cache]
    if pendientes:
        print("Analizando el audio de la mesa...")
        ref = ataques(envolvente(mesa["path"]))
        for a in pendientes:
            print(f"  sincronizando {a['name']}...", end=" ", flush=True)
            off, conf = desfase(ref, ataques(envolvente(a["path"])))
            cache[clave(a["path"])] = {"offset": off, "conf": conf}
            print(f"empieza en {fmt_t(off)} de la mesa (confianza {conf:.0f})")
        cache_path.write_text(json.dumps(cache, indent=1))
    for a in archivos:
        a.update(cache[clave(a["path"])])
        if a["conf"] < 8:
            print(f"  AVISO: la sincronización de {a['name']} es dudosa (confianza {a['conf']:.0f}). Revísala en DaVinci.")


# ------------------------------------------------------------------- beats

def rejilla_beats(on, t0, t1, bpm_min, bpm_max):
    """Busca tempo y fase que mejor encajan con los golpes entre t0 y t1 (segundos de mesa)."""
    seg = on[int(t0 * ENV_RATE):int(t1 * ENV_RATE)]
    seg = np.convolve(seg, np.array([0.25, 0.5, 1, 0.5, 0.25]), "same")
    idx = np.arange(len(seg))
    mejor = (-np.inf, None, None)
    for bpm in np.arange(bpm_min, bpm_max + 1e-9, 0.05):
        periodo = 60 * ENV_RATE / bpm
        nb = int((len(seg) - periodo) // periodo)
        if nb < 4:
            continue
        fases = np.arange(0, periodo, 1.0)
        pos = fases[:, None] + periodo * np.arange(nb)[None, :]
        punt = np.interp(pos, idx, seg).mean(1)
        j = int(np.argmax(punt))
        if punt[j] > mejor[0]:
            mejor = (punt[j], bpm, fases[j])
    _, bpm, fase = mejor
    if bpm is None:
        return None, None
    return float(bpm), t0 + fase / ENV_RATE


def momentos_con_energia(rms, on, duracion, n, cubierto, separacion=60):
    """Ventanas de `duracion` s con más volumen y pegada, sin solaparse."""
    paso = int(5 * ENV_RATE)
    L = int(duracion * ENV_RATE)
    db = 20 * np.log10(rms + 1e-5)
    cs_db = np.concatenate([[0], np.cumsum(db)])
    cs_on = np.concatenate([[0], np.cumsum(np.clip(on, 0, None))])
    cand = []
    for i in range(0, len(rms) - L, paso):
        t0 = i / ENV_RATE
        if not cubierto(t0, t0 + duracion):
            continue
        cand.append(((cs_db[i + L] - cs_db[i]) / L + 3 * (cs_on[i + L] - cs_on[i]) / L, t0))
    cand.sort(reverse=True)
    elegidos = []
    for _, t0 in cand:
        if all(abs(t0 - e) >= duracion + separacion for e in elegidos):
            elegidos.append(t0)
        if len(elegidos) == n:
            break
    return sorted(elegidos)


# ------------------------------------------------------------------ montaje

def duracion_plano(rng):
    return float(np.interp(rng.random(), np.linspace(0, 1, len(DURACIONES)), DURACIONES))


def planificar(t0, longitud, periodo, fuentes_en, rng, en_beat=True):
    """Lista de planos (inicio, fin, fuente) en segundos de mesa, siguiendo las reglas del estilo."""
    paso = periodo if en_beat else 1 / 25
    total = max(1, round(longitud / paso))
    final = max(1, round(rng.uniform(4, 8) / paso))
    planos, pos, usados = [], 0, []
    while pos < total:
        a = t0 + pos * paso
        previa = planos[-1][2] if planos else None
        restantes = total - pos
        objetivo = duracion_plano(rng)
        n = restantes if restantes <= final else max(2 if en_beat else 12, round(objetivo / paso))
        b = t0 + (pos + n) * paso
        opciones = [f for f in fuentes_en(a, b) if f != previa]
        if not opciones:
            opciones = fuentes_en(a, b) or [previa]
        if not planos:
            ini = [f for f in opciones if f in ("rec", "cam2")]
            src = rng.choice(ini or opciones)
        elif len(opciones) > 1 and rng.random() < 0.6:
            # Prefiere la fuente que lleva más tiempo sin salir, como en sus montajes.
            src = min(opciones, key=lambda f: max([i for i, u in enumerate(usados) if u == f], default=-1))
        else:
            src = rng.choice(opciones)
        if restantes > final:
            if src == "rec":               # los planos de recurso duran algo más
                n = max(n, round(objetivo * 1.15 / paso))
            if restantes - n < final:      # que el último plano no quede corto
                n = restantes
        b = t0 + (pos + n) * paso
        if planos and planos[-1][2] == src:
            planos[-1] = (planos[-1][0], b, src)
        else:
            planos.append((a, b, src))
        usados.append(src)
        pos += n
    return planos


# ------------------------------------------------------------------ FCPXML

def t(x):
    x = Fraction(x).limit_denominator(240000)
    return f"{x.numerator}s" if x.denominator == 1 else f"{x.numerator}/{x.denominator}s"


def a_frames(segundos, fps):
    return Fraction(round(Fraction(segundos) * fps)) / fps


def escribir_fcpxml(ruta, nombre, planos, t0_mesa, mesa, tl_fps, ancho, alto, zoom_animado, rng):
    """planos: [(desde_tl, hasta_tl, asset, inicio_en_archivo_s, es_camara)] con tiempos en segundos."""
    assets, formatos = {}, {}

    def formato(a):
        if a["fps"] is None:
            return None
        k = (a["fps"], a["width"], a["height"])
        if k not in formatos:
            formatos[k] = f"f{len(formatos) + 1}"
        return formatos[k]

    def asset_id(a):
        if a["path"] not in assets:
            assets[a["path"]] = (f"a{len(assets) + 1}", a)
        return assets[a["path"]][0]

    frame = 1 / Fraction(tl_fps)
    spine, zooms = [], []
    total = Fraction(0)
    for i, (desde, hasta, a, inicio, es_cam) in enumerate(planos):
        off = Fraction(round(Fraction(desde) / frame)) * frame
        fin = Fraction(round(Fraction(hasta) / frame)) * frame
        dur = fin - off
        zooms.append(None)
        if dur <= 0:
            continue
        start = a["start"] + a_frames(inicio, a["fps"])
        hijos = ""
        if es_cam:
            z = rng.choice(ZOOMS)
            if zoom_animado and rng.random() < 0.35:
                zooms[-1] = "anim"
                hijos += ('<adjust-transform><param name="scale"><keyframeAnimation>'
                          f'<keyframe time="{t(start)}" value="1 1"/>'
                          f'<keyframe time="{t(start + dur)}" value="1.25 1.25"/>'
                          '</keyframeAnimation></param></adjust-transform>')
            else:
                zooms[-1] = z
                hijos += f'<adjust-transform scale="{z} {z}"/>'
        if i == 0:
            # La música de la mesa va enganchada al primer plano, en una pista de audio debajo.
            hijos += "{MESA}"
            mesa_start = start
        spine.append(
            f'<asset-clip ref="{asset_id(a)}" name="{html.escape(a["name"])}" offset="{t(off)}" '
            f'start="{t(start)}" duration="{t(dur)}" srcEnable="video" tcFormat="NDF">{hijos}</asset-clip>')
        total = fin
    m_inicio = mesa["start"] + Fraction(round(t0_mesa * 48000), 48000)
    mesa_clip = (f'<asset-clip ref="{asset_id(mesa)}" lane="-1" name="{html.escape(mesa["name"])}" '
                 f'offset="{t(mesa_start)}" start="{t(m_inicio)}" duration="{t(total)}" srcEnable="audio"/>')
    spine[0] = spine[0].replace("{MESA}", mesa_clip)

    lista_assets = []
    for aid, a in assets.values():
        url = "file://" + urllib.parse.quote(a["path"])
        attrs = (f'id="{aid}" name="{html.escape(a["name"])}" start="{t(a["start"])}" '
                 f'duration="{t(Fraction(a["duration"]).limit_denominator(48000))}"')
        if a["fps"]:
            attrs += f' hasVideo="1" format="{formato(a)}"'
        if a["audio_rate"]:
            attrs += f' hasAudio="1" audioSources="1" audioChannels="{a["audio_channels"]}" audioRate="{a["audio_rate"]}"'
        lista_assets.append(f'<asset {attrs}><media-rep kind="original-media" src="{html.escape(url)}"/></asset>')
    res = [f'<format id="r0" name="Appedit" frameDuration="{t(frame)}" width="{ancho}" height="{alto}"/>']
    res += [f'<format id="{fid}" frameDuration="{t(1 / fps)}" width="{w}" height="{h}"/>'
            for (fps, w, h), fid in formatos.items()]
    res += lista_assets

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.10">\n'
           '<resources>\n' + "\n".join(res) + '\n</resources>\n'
           f'<library><event name="Appedit"><project name="{html.escape(nombre)}">'
           f'<sequence format="r0" duration="{t(total)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">'
           '<spine>\n' + "\n".join(spine) + '\n</spine></sequence></project></event></library>\n</fcpxml>\n')
    Path(ruta).write_text(xml, encoding="utf-8")
    return zooms


def render_previa(ruta, planos, zooms, t0_mesa, mesa, ancho=960, alto=540):
    """Vídeo de baja calidad con los mismos cortes, para verlo sin abrir DaVinci."""
    cmd, filtros = ["ffmpeg", "-v", "error", "-y"], []
    for i, ((desde, hasta, a, inicio, _), z) in enumerate(zip(planos, zooms)):
        dur = hasta - desde
        cmd += ["-ss", f"{inicio:.3f}", "-t", f"{dur:.3f}", "-i", a["path"]]
        f = f"[{i}:v]fps=25,scale={ancho}:{alto}:force_original_aspect_ratio=increase,crop={ancho}:{alto}"
        if z == "anim":
            f += (f",scale=w='trunc({ancho}*(1+0.25*t/{dur:.3f})/2)*2':h='trunc({alto}*(1+0.25*t/{dur:.3f})/2)*2'"
                  f":eval=frame,crop={ancho}:{alto}")
        elif z:
            f += f",scale={round(ancho * z / 2) * 2}:{round(alto * z / 2) * 2},crop={ancho}:{alto}"
        filtros.append(f + f",setsar=1,trim=duration={dur:.3f},setpts=PTS-STARTPTS[v{i}]")
    n = len(planos)
    total = planos[-1][1] - planos[0][0]
    cmd += ["-ss", f"{t0_mesa:.3f}", "-t", f"{total:.3f}", "-i", mesa["path"]]
    filtros.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]")
    cmd += ["-filter_complex", ";".join(filtros), "-map", "[v]", "-map", f"{n}:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-shortest", str(ruta)]
    subprocess.run(cmd, check=True)


# --------------------------------------------------------------- utilidades

def fmt_t(s):
    s = float(s)
    signo = "-" if s < 0 else ""
    s = abs(s)
    return f"{signo}{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def parse_t(txt):
    seg = 0.0
    for parte in txt.split(":"):
        seg = seg * 60 + float(parte)
    return seg


def archivo_en(archivos, a, b):
    """Archivo de la cámara que cubre entero el tramo [a, b] de la mesa."""
    for f in archivos:
        if f["offset"] <= a and b <= f["offset"] + f["duration"] - 0.1:
            return f
    return None


COLORES = {"cam1": "#4f7cff", "cam2": "#ff8a3d", "rec": "#2bb673"}


def escribir_resumen(ruta, piezas):
    filas = []
    for p in piezas:
        total = p["planos"][-1][1] - p["planos"][0][0]
        bloques = "".join(
            f'<div title="{NOMBRE[s]} · {b - a:.2f}s" style="flex:{b - a};background:{COLORES[s]}"></div>'
            for a, b, s in p["planos"])
        filas.append(
            f'<section><h2>{html.escape(p["nombre"])}</h2>'
            f'<p>Mesa {fmt_t(p["t0"])} · {total:.1f}s · {p["bpm"]:.1f} BPM · {len(p["planos"])} planos · '
            f'recurso: {html.escape(p["recurso"])}</p><div class="barra">{bloques}</div></section>')
    leyenda = "".join(f'<span><i style="background:{c}"></i>{NOMBRE[k]}</span>' for k, c in COLORES.items())
    Path(ruta).write_text(f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Appedit resumen</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--muted:#666}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--fg:#eee;--muted:#aaa}}}}
body{{background:var(--bg);color:var(--fg);font:15px system-ui,sans-serif;max-width:960px;margin:24px auto;padding:0 16px}}
.barra{{display:flex;height:34px;gap:2px;border-radius:6px;overflow:hidden}}
p{{color:var(--muted);margin:4px 0 10px}} h2{{font-size:17px;margin:22px 0 0}}
.leyenda span{{margin-right:16px}} .leyenda i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}}
</style><h1>Montajes generados</h1><div class="leyenda">{leyenda}</div>{"".join(filas)}</html>""", encoding="utf-8")


# ---------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Monta videosets de DJ con el estilo de ESTILO.md y exporta FCPXML para DaVinci.")
    ap.add_argument("--mesa", required=True, help="grabación de la mesa de mezclas (wav)")
    ap.add_argument("--cam1", nargs="+", required=True, help="archivo(s) de la cámara principal")
    ap.add_argument("--cam2", nargs="+", required=True, help="archivo(s) de la segunda cámara")
    ap.add_argument("--recursos", required=True, help="carpeta con los clips de recurso")
    ap.add_argument("--salida", default="salida", help="carpeta donde se guardan los FCPXML")
    ap.add_argument("--piezas", type=int, default=6, help="cuántas piezas generar si no se dan --momentos")
    ap.add_argument("--duracion", type=float, default=60, help="duración de cada pieza en segundos")
    ap.add_argument("--momentos", nargs="*", help="inicio de cada pieza en el audio de la mesa (mm:ss o h:mm:ss)")
    ap.add_argument("--bpm", default="110-150", help="rango de tempo a buscar, p. ej. 120-135")
    ap.add_argument("--sin-beat", action="store_true", help="no ajustar los cortes al beat")
    ap.add_argument("--zoom-animado", action="store_true", help="algunos planos con zoom animado 1.0→1.25")
    ap.add_argument("--fps", default="23.976", help="fps de la timeline (23.976, 24, 25, 30...)")
    ap.add_argument("--resolucion", default="1920x1080", help="resolución de la timeline")
    ap.add_argument("--semilla", type=int, help="fija el azar para repetir el mismo montaje")
    ap.add_argument("--cache", help="archivo donde guardar la sincronización (por defecto, en la carpeta de salida)")
    ap.add_argument("--previa", action="store_true", help="renderiza además un mp4 de baja calidad de cada pieza")
    args = ap.parse_args()

    rng = random.Random(args.semilla)
    tl_fps = {"23.976": Fraction(24000, 1001), "29.97": Fraction(30000, 1001),
              "59.94": Fraction(60000, 1001)}.get(args.fps, Fraction(args.fps))
    ancho, alto = (int(x) for x in args.resolucion.lower().split("x"))
    bpm_min, bpm_max = (float(x) for x in args.bpm.split("-"))
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)

    mesa = probe(args.mesa)
    cams = {"cam1": [probe(p) for p in args.cam1], "cam2": [probe(p) for p in args.cam2]}
    recursos = [probe(p) for p in sorted(Path(args.recursos).iterdir())
                if p.suffix.lower() in VIDEO_EXT and not p.name.startswith(".")]
    if not recursos:
        sys.exit("No hay clips de vídeo en la carpeta de recursos.")
    sincronizar(mesa, cams["cam1"] + cams["cam2"], Path(args.cache) if args.cache else salida / "sincronizacion.json")

    print("Buscando momentos y beats...")
    rms = envolvente(mesa["path"])
    on = ataques(rms)

    def cubierto(a, b):
        return all(archivo_en(cams[c], a, b) for c in cams)

    if args.momentos:
        inicios = [parse_t(m) for m in args.momentos]
    else:
        inicios = momentos_con_energia(rms, on, args.duracion, args.piezas, cubierto)
        if not inicios:
            sys.exit("No encuentro tramos donde las dos cámaras estén grabando a la vez.")

    libres = recursos[:]
    rng.shuffle(libres)
    piezas = []
    for n, inicio in enumerate(inicios, 1):
        bpm, primer_beat = rejilla_beats(on, inicio, inicio + args.duracion, bpm_min, bpm_max)
        if bpm is None or args.sin_beat:
            bpm, primer_beat = bpm or 0.0, inicio
        periodo = 60 / bpm if bpm else 1
        t0 = primer_beat
        longitud = round(args.duracion / periodo) * periodo if not args.sin_beat else args.duracion

        # Un solo clip de recurso por pieza: mejor uno que dure toda la pieza y que no se haya usado.
        if not libres:
            libres = recursos[:]
            rng.shuffle(libres)
        largos = [r for r in libres if r["duration"] >= longitud]
        rec = (largos or sorted(libres, key=lambda r: -r["duration"]))[0]
        libres.remove(rec)
        rec_in = rng.uniform(0, max(0.0, rec["duration"] - longitud))

        def fuentes_en(a, b):
            return [c for c in ("cam1", "cam2") if archivo_en(cams[c], a, b)] + ["rec"]

        plan = planificar(t0, longitud, periodo, fuentes_en, rng, en_beat=not args.sin_beat)
        clips = []
        for a, b, s in plan:
            desde, hasta = a - t0, b - t0
            if s == "rec":
                inicio_arch = (rec_in + desde) % max(rec["duration"] - (b - a), 0.1)
                clips.append((desde, hasta, rec, inicio_arch, False))
            else:
                f = archivo_en(cams[s], a, b)
                clips.append((desde, hasta, f, a - f["offset"], True))

        nombre = f"pieza_{n:02d}_{fmt_t(t0).replace(':', '-')[:7]}"
        info = {"nombre": nombre, "t0": t0, "bpm": bpm, "planos": plan, "recurso": rec["name"]}
        zooms = escribir_fcpxml(salida / f"{nombre}.fcpxml", nombre, clips, t0, mesa,
                        tl_fps, ancho, alto, args.zoom_animado, rng)
        piezas.append(info)
        if args.previa:
            print(f"    renderizando vista previa de {nombre}...")
            render_previa(salida / f"{nombre}_previa.mp4", clips, zooms, t0, mesa)
        print(f"  {nombre}: mesa {fmt_t(t0)}, {bpm:.1f} BPM, {len(plan)} planos, recurso {rec['name']}")

    escribir_resumen(salida / "resumen.html", piezas)
    print(f"\nListo. Importa los .fcpxml de '{salida}' en DaVinci: File > Import > Timeline.")
    print(f"Vista rápida de los cortes: {salida / 'resumen.html'}")


if __name__ == "__main__":
    main()
