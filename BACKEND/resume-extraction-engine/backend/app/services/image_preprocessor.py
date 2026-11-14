"""OpenCV preprocessing for OCR: grayscale -> upscale -> denoise -> background normalisation ->
Otsu threshold -> small-angle deskew."""
from __future__ import annotations

import cv2
import numpy as np


def to_gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def rotate_90s(img: np.ndarray, osd_rotate: int) -> np.ndarray:
    return {
        90: lambda i: cv2.rotate(i, cv2.ROTATE_90_CLOCKWISE),
        180: lambda i: cv2.rotate(i, cv2.ROTATE_180),
        270: lambda i: cv2.rotate(i, cv2.ROTATE_90_COUNTERCLOCKWISE),
    }.get(osd_rotate % 360, lambda i: i)(img)


def _skew_angle(binary_inv: np.ndarray) -> float:
    h, w = binary_inv.shape
    scale = 800 / max(w, 1)
    small = cv2.resize(binary_inv, (800, max(int(h * scale), 1)), interpolation=cv2.INTER_AREA)
    best, best_score = 0.0, -1.0
    center = (small.shape[1] / 2, small.shape[0] / 2)
    for a in np.arange(-5.0, 5.01, 0.5):
        m = cv2.getRotationMatrix2D(center, float(a), 1.0)
        r = cv2.warpAffine(small, m, (small.shape[1], small.shape[0]), flags=cv2.INTER_NEAREST)
        score = float(np.var(r.sum(axis=1)))
        if score > best_score:
            best, best_score = float(a), score
    return best


def preprocess(img: np.ndarray) -> np.ndarray:
    gray = to_gray(img)
    if min(gray.shape) < 1200:
        f = 1200 / min(gray.shape)
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    gray = cv2.medianBlur(gray, 3)                                   # noise removal
    bg = cv2.medianBlur(cv2.dilate(gray, np.ones((7, 7), np.uint8)), 21)
    norm = cv2.divide(gray, bg, scale=255)                           # remove uneven lighting
    _, binary = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    angle = _skew_angle(255 - binary)
    if abs(angle) >= 0.5:
        h, w = binary.shape
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        binary = cv2.warpAffine(binary, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)
    return binary
