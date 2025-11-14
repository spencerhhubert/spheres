import sys
import json
import math
from typing import Optional
import matplotlib.pyplot as plt
import numpy as np

# Weights histogram by overall_rank: weight = 1/overall_rank
# Lower ranks (more common parts) contribute more to the distribution

DO_WEIGHTING = False
OUTPUT_FILE = "distribution-parts.jpg"


def loadData(file_path: str) -> list[dict]:
    with open(file_path, 'r') as f:
        data = json.load(f)
        return data.get('pieces', [])


def getMinSphereDiameter(dim_x_cm: float, dim_y_cm: float, dim_z_cm: float) -> float:
    x_mm = dim_x_cm * 10
    y_mm = dim_y_cm * 10
    z_mm = dim_z_cm * 10

    diagonal = math.sqrt(x_mm**2 + y_mm**2 + z_mm**2)

    return diagonal


def extractSphereDiameters(parts: list[dict]) -> tuple[list[float], list[float]]:
    diameters = []
    weights = []

    for part in parts:
        pack_dim_x = part.get('pack_dim_x')
        pack_dim_y = part.get('pack_dim_y')
        pack_dim_z = part.get('pack_dim_z')

        if pack_dim_x is None or pack_dim_y is None or pack_dim_z is None:
            continue

        if pack_dim_x == 0 or pack_dim_y == 0 or pack_dim_z == 0:
            continue

        diameter = getMinSphereDiameter(pack_dim_x, pack_dim_y, pack_dim_z)

        if DO_WEIGHTING:
            overall_rank = part.get('overall_rank', 0)
            if overall_rank > 0:
                weight = 1.0 / overall_rank
            else:
                weight = 0.0
        else:
            weight = 1.0

        diameters.append(diameter)
        weights.append(weight)

    return diameters, weights


def generateDistribution(diameters: list[float], weights: list[float]):
    if not diameters:
        print("No valid sphere diameters found")
        return

    diameters_array = np.array(diameters)
    weights_array = np.array(weights)

    mean = np.average(diameters_array, weights=weights_array)
    variance = np.average((diameters_array - mean)**2, weights=weights_array)
    std = np.sqrt(variance)

    sorted_indices = np.argsort(diameters_array)
    sorted_diameters = diameters_array[sorted_indices]
    sorted_weights = weights_array[sorted_indices]
    cumsum = np.cumsum(sorted_weights)
    median_idx = np.searchsorted(cumsum, cumsum[-1] / 2.0)
    median = sorted_diameters[median_idx]

    fig, ax = plt.subplots(figsize=(12, 8))

    n, bins, patches = ax.hist(diameters_array, bins=50, weights=weights_array, alpha=0.7, color='blue', edgecolor='black')

    ax.axvline(mean, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean:.2f}')
    ax.axvline(median, color='green', linestyle='--', linewidth=2, label=f'Median: {median:.2f}')
    ax.axvline(mean + std, color='orange', linestyle=':', linewidth=2, label=f'+1 SD: {mean + std:.2f}')
    ax.axvline(mean - std, color='orange', linestyle=':', linewidth=2, label=f'-1 SD: {mean - std:.2f}')
    ax.axvline(mean + 2*std, color='purple', linestyle=':', linewidth=2, label=f'+2 SD: {mean + 2*std:.2f}')
    ax.axvline(mean - 2*std, color='purple', linestyle=':', linewidth=2, label=f'-2 SD: {mean - 2*std:.2f}')

    def weighted_percentile(data, weights, percentile):
        sorted_indices = np.argsort(data)
        sorted_data = data[sorted_indices]
        sorted_weights = weights[sorted_indices]
        cumsum = np.cumsum(sorted_weights)
        percentile_idx = np.searchsorted(cumsum, cumsum[-1] * percentile / 100.0)
        return sorted_data[percentile_idx]

    percentiles = [25, 50, 75, 90, 95]
    percentile_values = [weighted_percentile(diameters_array, weights_array, p) for p in percentiles]

    stats_text = f'n = {len(diameters)}\n'
    stats_text += f'Mean = {mean:.2f}\n'
    stats_text += f'SD = {std:.2f}\n'
    stats_text += f'Median = {median:.2f}\n'
    stats_text += f'Min = {min(diameters):.2f}\n'
    stats_text += f'Max = {max(diameters):.2f}\n\n'
    stats_text += 'Percentiles (weighted):\n'
    for p, v in zip(percentiles, percentile_values):
        stats_text += f'{p}th: {v:.2f}\n'

    ax.text(0.98, 0.97, stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    ax.set_xlabel('Minimum Sphere Diameter (mm)', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title('Distribution of Minimum Bounding Sphere Diameters for LEGO Parts (mm)', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, format='jpg', dpi=150)
    print(f"Distribution saved to {OUTPUT_FILE}")
    print(f"Analyzed {len(diameters)} parts")
    print(f"Mean diameter: {mean:.2f}mm, SD: {std:.2f}mm")


def main():
    if len(sys.argv) < 2:
        print("Usage: python build-sphere-distribution.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]

    parts = loadData(file_path)
    diameters, weights = extractSphereDiameters(parts)
    generateDistribution(diameters, weights)


if __name__ == '__main__':
    main()
