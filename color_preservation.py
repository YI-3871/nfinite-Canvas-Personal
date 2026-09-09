"""Deterministic color-drift correction for image-editing outputs.

The module intentionally depends only on Pillow and the Python standard library so
it also works in the portable Windows runtime shipped with Infinite Canvas.  It
analyses small copies, but applies the selected transform to the full-size image.
"""

from __future__ import annotations

import math
import os
import statistics
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, Iterable, List, Sequence, Tuple

from PIL import Image, ImageChops, ImageCms, ImageFilter, ImageOps, ImageStat


ANALYSIS_LONG_SIDE = 360
TONE_KNOTS = (0.0, 22.0, 45.0, 68.0, 86.0, 100.0)
STRENGTH_STEPS = (0.0, 0.25, 0.5, 0.75, 1.0)
VALID_TASK_MODES = {"outfit_swap", "pose_change", "scene_change"}
VALID_PRESERVATION_MODES = {"off", "auto", "strict"}


@dataclass
class Anchor:
    x: int
    y: int
    original_rgb: Tuple[int, int, int]
    generated_rgb: Tuple[int, int, int]
    original_lab: Tuple[float, float, float]
    generated_lab: Tuple[float, float, float]


def _median(values: Iterable[float], default: float = 0.0) -> float:
    values = list(values)
    return float(statistics.median(values)) if values else float(default)


def _percentile(values: Iterable[float], percentile: float, default: float = 0.0) -> float:
    values = sorted(float(value) for value in values)
    if not values:
        return float(default)
    position = max(0.0, min(1.0, percentile)) * (len(values) - 1)
    low = int(math.floor(position))
    high = min(len(values) - 1, low + 1)
    weight = position - low
    return values[low] * (1.0 - weight) + values[high] * weight


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return low if value < low else high if value > high else value


def _srgb_channel_to_linear(value: float) -> float:
    value = _clamp(value)
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _linear_channel_to_srgb(value: float) -> float:
    value = _clamp(value)
    return value * 12.92 if value <= 0.0031308 else 1.055 * (value ** (1.0 / 2.4)) - 0.055


def rgb_to_lab(rgb: Sequence[float]) -> Tuple[float, float, float]:
    r, g, b = (_srgb_channel_to_linear(float(channel) / 255.0) for channel in rgb[:3])
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(value: float) -> float:
        return value ** (1.0 / 3.0) if value > 0.008856 else 7.787 * value + 16.0 / 116.0

    fx, fy, fz = f(x), f(y), f(z)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def lab_to_rgb(lab: Sequence[float]) -> Tuple[float, float, float]:
    l_value, a_value, b_value = (float(value) for value in lab[:3])
    fy = (l_value + 16.0) / 116.0
    fx = fy + a_value / 500.0
    fz = fy - b_value / 200.0

    def inv(value: float) -> float:
        cube = value ** 3
        return cube if cube > 0.008856 else (value - 16.0 / 116.0) / 7.787

    x, y, z = 0.95047 * inv(fx), inv(fy), 1.08883 * inv(fz)
    r = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    b = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    return tuple(255.0 * _linear_channel_to_srgb(channel) for channel in (r, g, b))


def delta_e76(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(3)))


def _profile_bytes(profile) -> bytes:
    try:
        return ImageCms.ImageCmsProfile(profile).tobytes()
    except Exception:
        return b""


def _open_srgb(path: str) -> Tuple[Image.Image, Dict[str, bytes]]:
    with Image.open(path) as source:
        source.load()
        source = ImageOps.exif_transpose(source)
        info = {key: source.info.get(key) for key in ("exif", "icc_profile") if source.info.get(key)}
        alpha = source.getchannel("A") if "A" in source.getbands() else None
        rgb = source.convert("RGB")
        icc_data = source.info.get("icc_profile")
        if icc_data:
            try:
                src_profile = ImageCms.ImageCmsProfile(BytesIO(icc_data))
                dst_profile = ImageCms.createProfile("sRGB")
                rgb = ImageCms.profileToProfile(rgb, src_profile, dst_profile, outputMode="RGB")
            except Exception:
                pass
        if alpha is not None:
            rgb.putalpha(alpha)
        return rgb, info


def _analysis_size(size: Tuple[int, int], long_side: int = ANALYSIS_LONG_SIDE) -> Tuple[int, int]:
    width, height = size
    scale = min(1.0, float(long_side) / max(width, height, 1))
    return max(24, int(round(width * scale))), max(24, int(round(height * scale)))


def _analysis_rgb(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    return image.convert("RGB").resize(size, Image.Resampling.LANCZOS)


def _outer_mask(size: Tuple[int, int], fraction: float) -> Image.Image:
    width, height = size
    inset_x = max(1, int(round(width * fraction)))
    inset_y = max(1, int(round(height * fraction)))
    mask = Image.new("L", size, 255)
    if width > inset_x * 2 and height > inset_y * 2:
        inner = Image.new("L", (width - inset_x * 2, height - inset_y * 2), 0)
        mask.paste(inner, (inset_x, inset_y))
    return mask


def _edge_image(image: Image.Image) -> Image.Image:
    return image.convert("L").filter(ImageFilter.GaussianBlur(0.7)).filter(ImageFilter.FIND_EDGES)


def _alignment_score(original_edge: Image.Image, generated_edge: Image.Image, dx: int, dy: int, mask: Image.Image) -> float:
    width, height = original_edge.size
    x0, y0 = max(0, -dx), max(0, -dy)
    x1, y1 = min(width, width - dx), min(height, height - dy)
    if x1 - x0 < width * 0.65 or y1 - y0 < height * 0.65:
        return 255.0
    original_crop = original_edge.crop((x0, y0, x1, y1))
    generated_crop = generated_edge.crop((x0 + dx, y0 + dy, x1 + dx, y1 + dy))
    mask_crop = mask.crop((x0, y0, x1, y1))
    difference = ImageChops.difference(original_crop, generated_crop)
    return float(ImageStat.Stat(difference, mask_crop).mean[0])


def _estimate_translation(original: Image.Image, generated: Image.Image, task_mode: str) -> Tuple[int, int, float]:
    edge_original, edge_generated = _edge_image(original), _edge_image(generated)
    mask = _outer_mask(original.size, 0.29 if task_mode == "pose_change" else 0.38)
    limit = max(2, int(round(min(original.size) * (0.045 if task_mode == "pose_change" else 0.025))))
    step = 2 if limit > 7 else 1
    best = (0, 0, _alignment_score(edge_original, edge_generated, 0, 0, mask))
    for dy in range(-limit, limit + 1, step):
        for dx in range(-limit, limit + 1, step):
            score = _alignment_score(edge_original, edge_generated, dx, dy, mask)
            if score < best[2]:
                best = (dx, dy, score)
    if step > 1:
        coarse_x, coarse_y = best[0], best[1]
        for dy in range(coarse_y - 2, coarse_y + 3):
            for dx in range(coarse_x - 2, coarse_x + 3):
                score = _alignment_score(edge_original, edge_generated, dx, dy, mask)
                if score < best[2]:
                    best = (dx, dy, score)
    return best


def _balanced_anchors(groups: Dict[Tuple[int, int], List[Anchor]], cap_per_group: int = 420) -> List[Anchor]:
    result: List[Anchor] = []
    for key in sorted(groups):
        values = groups[key]
        if len(values) <= cap_per_group:
            result.extend(values)
            continue
        stride = len(values) / float(cap_per_group)
        result.extend(values[min(len(values) - 1, int(index * stride))] for index in range(cap_per_group))
    return result


def _find_anchors(original: Image.Image, generated: Image.Image, task_mode: str) -> Tuple[List[Anchor], Dict[str, float]]:
    width, height = original.size
    dx, dy, alignment_error = _estimate_translation(original, generated, task_mode)
    original_gray, generated_gray = original.convert("L"), generated.convert("L")
    original_edge, generated_edge = _edge_image(original), _edge_image(generated)
    op, gp = original.load(), generated.load()
    og, gg = original_gray.load(), generated_gray.load()
    oe, ge = original_edge.load(), generated_edge.load()
    lum_limit = 30 if task_mode == "pose_change" else 23
    edge_limit = 42 if task_mode == "pose_change" else 32
    raw: List[Anchor] = []
    valid = 0
    for y in range(max(1, -dy), min(height - 1, height - dy)):
        gy = y + dy
        for x in range(max(1, -dx), min(width - 1, width - dx)):
            gx = x + dx
            valid += 1
            if abs(int(og[x, y]) - int(gg[gx, gy])) > lum_limit:
                continue
            if abs(int(oe[x, y]) - int(ge[gx, gy])) > edge_limit:
                continue
            original_rgb = tuple(op[x, y])[:3]
            generated_rgb = tuple(gp[gx, gy])[:3]
            if max(original_rgb) >= 253 and min(original_rgb) >= 250:
                continue
            if max(original_rgb) <= 4 and max(generated_rgb) <= 4:
                continue
            original_chroma = max(original_rgb) - min(original_rgb)
            generated_chroma = max(generated_rgb) - min(generated_rgb)
            if original_chroma > 54 or generated_chroma > 70:
                continue
            original_lab = rgb_to_lab(original_rgb)
            generated_lab = rgb_to_lab(generated_rgb)
            raw.append(Anchor(x, y, original_rgb, generated_rgb, original_lab, generated_lab))

    if not raw:
        return [], {"dx": dx, "dy": dy, "error": alignment_error, "coverage": 0.0, "tiles": 0}

    median_da = _median(anchor.original_lab[1] - anchor.generated_lab[1] for anchor in raw)
    median_db = _median(anchor.original_lab[2] - anchor.generated_lab[2] for anchor in raw)
    robust_limit = 10.5 if task_mode == "pose_change" else 8.0
    filtered = [
        anchor for anchor in raw
        if math.hypot(
            (anchor.original_lab[1] - anchor.generated_lab[1]) - median_da,
            (anchor.original_lab[2] - anchor.generated_lab[2]) - median_db,
        ) <= robust_limit
    ]
    groups: Dict[Tuple[int, int], List[Anchor]] = {}
    occupied_tiles = set()
    for anchor in filtered:
        tone_bin = min(4, max(0, int(anchor.generated_lab[0] // 20)))
        tile_x = min(3, int(anchor.x * 4 / max(width, 1)))
        tile_y = min(3, int(anchor.y * 4 / max(height, 1)))
        tile = tile_y * 4 + tile_x
        occupied_tiles.add(tile)
        groups.setdefault((tone_bin, tile), []).append(anchor)
    anchors = _balanced_anchors(groups)
    return anchors, {
        "dx": dx,
        "dy": dy,
        "error": round(alignment_error, 4),
        "coverage": round(len(filtered) / max(valid, 1), 6),
        "tiles": len(occupied_tiles),
        "raw_anchor_count": len(raw),
        "anchor_count": len(anchors),
    }


def _split_anchors(anchors: Sequence[Anchor]) -> Tuple[List[Anchor], List[Anchor]]:
    train, validation = [], []
    for anchor in anchors:
        bucket = ((anchor.x * 73856093) ^ (anchor.y * 19349663)) % 5
        (validation if bucket == 0 else train).append(anchor)
    if len(validation) < 40:
        cut = max(1, len(anchors) // 5)
        validation = list(anchors[::max(1, len(anchors) // cut)])[:cut]
        validation_ids = {id(anchor) for anchor in validation}
        train = [anchor for anchor in anchors if id(anchor) not in validation_ids]
    return train, validation


def _solve_linear(matrix: List[List[float]], vector: List[float]) -> List[float]:
    size = len(vector)
    augmented = [list(matrix[row]) + [float(vector[row])] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-9:
            raise ValueError("singular color fit")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][index] - factor * augmented[column][index]
                for index in range(size + 1)
            ]
    return [augmented[row][-1] for row in range(size)]


def _fit_matrix(anchors: Sequence[Anchor], regularization: float = 0.12) -> Tuple[List[List[float]], List[float]]:
    weights = [1.0] * len(anchors)
    rows: List[List[float]] = []
    biases: List[float] = []
    for _ in range(3):
        total_weight = max(sum(weights), 1e-9)
        fitted_rows = []
        fitted_biases = []
        for output_channel in range(3):
            normal = [[0.0] * 4 for _ in range(4)]
            target = [0.0] * 4
            for anchor, weight in zip(anchors, weights):
                features = [channel / 255.0 for channel in anchor.generated_rgb] + [1.0]
                expected = anchor.original_rgb[output_channel] / 255.0
                normalized_weight = weight / total_weight
                for row in range(4):
                    target[row] += normalized_weight * features[row] * expected
                    for column in range(4):
                        normal[row][column] += normalized_weight * features[row] * features[column]
            identity_target = [0.0, 0.0, 0.0, 0.0]
            identity_target[output_channel] = 1.0
            for index in range(3):
                normal[index][index] += regularization
                target[index] += regularization * identity_target[index]
            normal[3][3] += regularization * 0.35
            coefficients = _solve_linear(normal, target)
            fitted_rows.append(coefficients[:3])
            fitted_biases.append(coefficients[3])
        rows, biases = fitted_rows, fitted_biases
        residuals = []
        for anchor in anchors:
            generated = [channel / 255.0 for channel in anchor.generated_rgb]
            predicted = [sum(rows[row][column] * generated[column] for column in range(3)) + biases[row] for row in range(3)]
            expected = [channel / 255.0 for channel in anchor.original_rgb]
            residuals.append(math.sqrt(sum((predicted[index] - expected[index]) ** 2 for index in range(3))))
        cutoff = max(0.012, _median(residuals) * 2.5)
        weights = [1.0 if residual <= cutoff else cutoff / max(residual, 1e-9) for residual in residuals]

    for row in range(3):
        for column in range(3):
            low, high = ((0.85, 1.15) if row == column else (-0.08, 0.08))
            rows[row][column] = _clamp(rows[row][column], low, high)
        biases[row] = _clamp(biases[row], -0.05, 0.05)
    return rows, biases


def _matrix_determinant(matrix: Sequence[Sequence[float]]) -> float:
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def _matrix_safe(matrix: Sequence[Sequence[float]], bias: Sequence[float]) -> bool:
    if abs(_matrix_determinant(matrix)) < 0.45:
        return False
    for row in range(3):
        if abs(matrix[row][row] - 1.0) > 0.151 or abs(bias[row]) > 0.051:
            return False
        if sum(abs(matrix[row][column]) for column in range(3) if column != row) > 0.161:
            return False
    return True


def _apply_lab_point(anchor: Anchor, shift: Sequence[float], strength: float) -> Tuple[float, float, float]:
    lab = (
        anchor.generated_lab[0],
        anchor.generated_lab[1] + shift[0] * strength,
        anchor.generated_lab[2] + shift[1] * strength,
    )
    return lab_to_rgb(lab)


def _apply_matrix_point(anchor: Anchor, matrix: Sequence[Sequence[float]], bias: Sequence[float], strength: float) -> Tuple[float, float, float]:
    generated = [channel / 255.0 for channel in anchor.generated_rgb]
    corrected = [
        _clamp(sum(matrix[row][column] * generated[column] for column in range(3)) + bias[row]) * 255.0
        for row in range(3)
    ]
    return tuple(generated[index] * 255.0 * (1.0 - strength) + corrected[index] * strength for index in range(3))


def _tone_index(lightness: float) -> int:
    for index in range(len(TONE_KNOTS) - 1):
        if lightness <= TONE_KNOTS[index + 1]:
            return index
    return len(TONE_KNOTS) - 2


def _best_tone_strengths(anchors: Sequence[Anchor], point_corrector) -> List[float]:
    global_scores = []
    for strength in STRENGTH_STEPS:
        errors = [delta_e76(anchor.original_lab, rgb_to_lab(point_corrector(anchor, strength))) for anchor in anchors]
        global_scores.append((_median(errors), strength))
    global_strength = min(global_scores)[1]
    strengths = []
    for index in range(len(TONE_KNOTS) - 1):
        group = [anchor for anchor in anchors if _tone_index(anchor.generated_lab[0]) == index]
        if len(group) < 24:
            strengths.append(global_strength)
            continue
        scores = []
        for strength in STRENGTH_STEPS:
            errors = [delta_e76(anchor.original_lab, rgb_to_lab(point_corrector(anchor, strength))) for anchor in group]
            scores.append((_median(errors), strength))
        strengths.append(min(scores)[1])
    smoothed = strengths[:]
    for index in range(1, len(strengths) - 1):
        smoothed[index] = round((strengths[index - 1] + 2.0 * strengths[index] + strengths[index + 1]) / 4.0, 4)
    return smoothed


def _strength_for_lightness(lightness: float, strengths: Sequence[float]) -> float:
    index = _tone_index(lightness)
    low, high = TONE_KNOTS[index], TONE_KNOTS[index + 1]
    next_strength = strengths[min(index + 1, len(strengths) - 1)]
    ratio = 0.0 if high <= low else _clamp((lightness - low) / (high - low))
    return strengths[index] * (1.0 - ratio) + next_strength * ratio


def _candidate_metrics(anchors: Sequence[Anchor], point_corrector, strengths: Sequence[float]) -> Dict[str, float]:
    baseline, corrected = [], []
    for anchor in anchors:
        baseline.append(delta_e76(anchor.original_lab, anchor.generated_lab))
        strength = _strength_for_lightness(anchor.generated_lab[0], strengths)
        corrected.append(delta_e76(anchor.original_lab, rgb_to_lab(point_corrector(anchor, strength))))
    before_median = _median(baseline)
    after_median = _median(corrected)
    return {
        "before_median_delta_e": round(before_median, 4),
        "before_p95_delta_e": round(_percentile(baseline, 0.95), 4),
        "after_median_delta_e": round(after_median, 4),
        "after_p95_delta_e": round(_percentile(corrected, 0.95), 4),
        "improvement": round(max(0.0, before_median - after_median), 4),
        "improvement_pct": round(100.0 * max(0.0, before_median - after_median) / max(before_median, 1e-9), 2),
    }


def _candidate_acceptable(metrics: Dict[str, float]) -> bool:
    return (
        metrics["before_median_delta_e"] >= 0.9
        and metrics["improvement"] >= 0.35
        and metrics["improvement_pct"] >= 14.0
        and metrics["after_p95_delta_e"] <= metrics["before_p95_delta_e"] * 1.10 + 0.25
    )


def _full_lab_correction(image: Image.Image, shift: Sequence[float]) -> Image.Image:
    rgb = image.convert("RGB")
    srgb_profile = ImageCms.createProfile("sRGB")
    lab_profile = ImageCms.createProfile("LAB")
    lab = ImageCms.profileToProfile(rgb, srgb_profile, lab_profile, outputMode="LAB")
    l_channel, a_channel, b_channel = lab.split()
    da, db = int(round(shift[0])), int(round(shift[1]))
    a_channel = a_channel.point(lambda value: max(0, min(255, value + da)))
    b_channel = b_channel.point(lambda value: max(0, min(255, value + db)))
    corrected_lab = Image.merge("LAB", (l_channel, a_channel, b_channel))
    return ImageCms.profileToProfile(corrected_lab, lab_profile, srgb_profile, outputMode="RGB")


def _full_matrix_correction(image: Image.Image, matrix: Sequence[Sequence[float]], bias: Sequence[float]) -> Image.Image:
    coefficients = []
    for row in range(3):
        coefficients.extend([matrix[row][0], matrix[row][1], matrix[row][2], bias[row] * 255.0])
    return image.convert("RGB", tuple(coefficients))


def _strength_mask(image: Image.Image, strengths: Sequence[float], confidence: float, mode: str, task_mode: str) -> Image.Image:
    mode_scale = 1.0 if mode == "strict" else 0.92
    if task_mode == "pose_change":
        mode_scale *= 0.82
    confidence_scale = 0.72 + 0.28 * _clamp(confidence)
    values = []
    for encoded in range(256):
        lightness = encoded * 100.0 / 255.0
        values.append(int(round(255.0 * _clamp(_strength_for_lightness(lightness, strengths) * mode_scale * confidence_scale))))
    luminance_mask = image.convert("L").point(values)
    red, green, blue = image.convert("RGB").split()
    maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    minimum = ImageChops.darker(ImageChops.darker(red, green), blue)
    chroma = ImageChops.subtract(maximum, minimum)
    minimum_factor = 0.70 if mode == "strict" else 0.55
    chroma_lut = [int(round(255.0 * (1.0 - (1.0 - minimum_factor) * (value / 255.0)))) for value in range(256)]
    chroma_mask = chroma.point(chroma_lut)
    return ImageChops.multiply(luminance_mask, chroma_mask)


def _save_corrected(image: Image.Image, output_path: str, source_info: Dict[str, bytes]) -> None:
    extension = os.path.splitext(output_path)[1].lower()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    srgb_bytes = _profile_bytes(ImageCms.createProfile("sRGB"))
    save_kwargs = {"icc_profile": srgb_bytes} if srgb_bytes else {}
    if source_info.get("exif"):
        save_kwargs["exif"] = source_info["exif"]
    if extension in {".jpg", ".jpeg"}:
        image.convert("RGB").save(output_path, "JPEG", quality=96, subsampling=0, optimize=True, **save_kwargs)
    elif extension == ".webp":
        image.save(output_path, "WEBP", lossless=True, method=4, **save_kwargs)
    else:
        image.save(output_path, "PNG", compress_level=6, **save_kwargs)


def preserve_image_colors(
    original_path: str,
    generated_path: str,
    output_path: str,
    mode: str = "auto",
    task_mode: str = "outfit_swap",
) -> Dict[str, object]:
    """Analyse and optionally correct a generated image without changing geometry."""
    mode = mode if mode in VALID_PRESERVATION_MODES else "auto"
    task_mode = task_mode if task_mode in VALID_TASK_MODES else "outfit_swap"
    diagnostics: Dict[str, object] = {
        "version": 1,
        "strategy": "adaptive_hybrid_d",
        "requested_mode": mode,
        "task_mode": task_mode,
        "status": "passthrough",
        "method": "none",
        "confidence": 0.0,
        "raw_path": generated_path,
        "corrected_path": "",
    }
    if mode == "off":
        diagnostics["reason"] = "color preservation is off"
        return diagnostics
    if task_mode == "scene_change":
        diagnostics["reason"] = "scene or lighting changes reset the color baseline"
        return diagnostics
    if not original_path or not os.path.isfile(original_path):
        diagnostics["reason"] = "color reference is unavailable"
        return diagnostics
    if not generated_path or not os.path.isfile(generated_path):
        diagnostics["reason"] = "generated image is unavailable"
        return diagnostics

    original_full, _ = _open_srgb(original_path)
    generated_full, generated_info = _open_srgb(generated_path)
    diagnostics["dimensions"] = {"width": generated_full.width, "height": generated_full.height}
    original_ratio = original_full.width / max(original_full.height, 1)
    generated_ratio = generated_full.width / max(generated_full.height, 1)
    ratio_error = abs(math.log(max(original_ratio, 1e-9) / max(generated_ratio, 1e-9)))
    if ratio_error > 0.075:
        diagnostics["reason"] = "reference and output aspect ratios differ too much"
        diagnostics["aspect_ratio_error"] = round(ratio_error, 6)
        return diagnostics

    analysis_size = _analysis_size(original_full.size)
    original = _analysis_rgb(original_full, analysis_size)
    generated = _analysis_rgb(generated_full, analysis_size)
    anchors, alignment = _find_anchors(original, generated, task_mode)
    diagnostics["analysis_size"] = {"width": analysis_size[0], "height": analysis_size[1]}
    diagnostics["alignment"] = alignment
    if len(anchors) < 180:
        diagnostics["reason"] = "not enough stable color anchors"
        return diagnostics
    train, validation = _split_anchors(anchors)
    if len(train) < 120 or len(validation) < 30:
        diagnostics["reason"] = "stable anchors are not sufficiently distributed"
        return diagnostics

    shift_limit = 12.0 if mode == "strict" else 8.0
    lab_shift = [
        _clamp(_median(anchor.original_lab[1] - anchor.generated_lab[1] for anchor in train), -shift_limit, shift_limit),
        _clamp(_median(anchor.original_lab[2] - anchor.generated_lab[2] for anchor in train), -shift_limit, shift_limit),
    ]
    lab_corrector = lambda anchor, strength: _apply_lab_point(anchor, lab_shift, strength)
    lab_strengths = _best_tone_strengths(validation, lab_corrector)
    lab_metrics = _candidate_metrics(validation, lab_corrector, lab_strengths)
    candidates = [{
        "method": "lab_chroma",
        "parameters": {"delta_a": round(lab_shift[0], 5), "delta_b": round(lab_shift[1], 5)},
        "tone_strengths": lab_strengths,
        "metrics": lab_metrics,
        "acceptable": _candidate_acceptable(lab_metrics),
        "corrector": lab_corrector,
    }]

    try:
        matrix, bias = _fit_matrix(train)
        matrix_corrector = lambda anchor, strength: _apply_matrix_point(anchor, matrix, bias, strength)
        matrix_strengths = _best_tone_strengths(validation, matrix_corrector)
        matrix_metrics = _candidate_metrics(validation, matrix_corrector, matrix_strengths)
        safe = _matrix_safe(matrix, bias)
        candidates.append({
            "method": "constrained_rgb_matrix",
            "parameters": {
                "matrix": [[round(value, 7) for value in row] for row in matrix],
                "bias": [round(value, 7) for value in bias],
                "determinant": round(_matrix_determinant(matrix), 7),
            },
            "tone_strengths": matrix_strengths,
            "metrics": matrix_metrics,
            "acceptable": safe and _candidate_acceptable(matrix_metrics),
            "corrector": matrix_corrector,
        })
    except Exception as exc:
        diagnostics["matrix_error"] = str(exc)[:180]

    public_candidates = []
    for candidate in candidates:
        public_candidates.append({key: value for key, value in candidate.items() if key != "corrector"})
    diagnostics["candidates"] = public_candidates
    accepted = [candidate for candidate in candidates if candidate["acceptable"]]
    if not accepted:
        diagnostics["reason"] = "no correction candidate passed the safety checks"
        return diagnostics
    selected = min(
        accepted,
        key=lambda candidate: candidate["metrics"]["after_median_delta_e"] + 0.16 * candidate["metrics"]["after_p95_delta_e"],
    )
    metrics = selected["metrics"]
    coverage_score = min(1.0, float(alignment.get("coverage", 0.0)) / 0.08)
    spatial_score = min(1.0, float(alignment.get("tiles", 0)) / 10.0)
    registration_score = _clamp(1.0 - float(alignment.get("error", 255.0)) / 52.0)
    improvement_score = min(1.0, float(metrics["improvement_pct"]) / 55.0)
    confidence = 0.27 * coverage_score + 0.23 * spatial_score + 0.20 * registration_score + 0.30 * improvement_score
    if task_mode == "pose_change":
        confidence *= 0.90
    confidence = round(_clamp(confidence), 4)
    diagnostics["confidence"] = confidence
    threshold = 0.38 if mode == "strict" else 0.48
    if confidence < threshold:
        diagnostics["reason"] = "correction confidence is below the automatic threshold"
        return diagnostics

    if selected["method"] == "constrained_rgb_matrix":
        parameters = selected["parameters"]
        corrected_rgb = _full_matrix_correction(generated_full, parameters["matrix"], parameters["bias"])
    else:
        parameters = selected["parameters"]
        corrected_rgb = _full_lab_correction(generated_full, (parameters["delta_a"], parameters["delta_b"]))
    mask = _strength_mask(generated_full, selected["tone_strengths"], confidence, mode, task_mode)
    generated_rgb = generated_full.convert("RGB")
    corrected = Image.composite(corrected_rgb, generated_rgb, mask)
    if "A" in generated_full.getbands():
        corrected.putalpha(generated_full.getchannel("A"))
    _save_corrected(corrected, output_path, generated_info)
    diagnostics.update({
        "status": "corrected",
        "method": selected["method"],
        "reason": "safe candidate improved held-out stable regions",
        "parameters": selected["parameters"],
        "tone_strengths": selected["tone_strengths"],
        "metrics": metrics,
        "corrected_path": output_path,
        "magenta_drift": {
            "delta_a": round(-lab_shift[0], 5),
            "delta_b": round(-lab_shift[1], 5),
            "index": round(max(0.0, -lab_shift[0]) + max(0.0, lab_shift[1]), 5),
        },
    })
    return diagnostics
