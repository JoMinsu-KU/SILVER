from statistics import NormalDist
import math

def wilson_ci(success: int, n: int, alpha: float = 0.05):
    if n <= 0:
        return (math.nan, math.nan)
    z = NormalDist().inv_cdf(1 - alpha / 2)
    p = success / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return center - half, center + half
