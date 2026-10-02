"""Window and TradingView chart-region detection.

S02/S03 use explicit window metadata first. S05 adds conservative visual
evidence so the target window interior is not automatically treated as a
chart. Detection is observation-only and never creates trading authority.
"""

from __future__ import annotations

from typing import Any, Iterable

from .contracts import ChartObservation, WindowObservation


class WindowDetector:
    def __init__(self, applications: Iterable[str] = ("tradingview",)) -> None:
        self.applications = tuple(item.lower() for item in applications)

    def select(self, windows: Iterable[WindowObservation]) -> WindowObservation | None:
        candidates = tuple(windows)
        for window in candidates:
            haystack = f"{window.application} {window.title}".lower()
            if any(token in haystack for token in self.applications):
                return window
        return None


class TradingViewRegionDetector:
    """Conservative S05 chart-region detector.

    With no frame, the detector retains the S03 metadata-only fallback for
    backwards compatibility. With a frame, it validates the candidate using
    the existing visual chart recognizer and estimates a tighter interior
    region from image activity. OCR may provide supporting spatial evidence,
    but it can never manufacture a chart region by itself.
    """

    def detect(
        self,
        window: WindowObservation | None,
        image: Any | None = None,
        ocr_result: Any | None = None,
    ) -> ChartObservation:
        if window is None:
            return ChartObservation(detected=False)

        # Metadata-only compatibility path used by older callers/tests.
        header = min(120, max(24, window.height // 8))
        fallback = ChartObservation(
            detected=True,
            left=window.left,
            top=window.top + header,
            width=window.width,
            height=window.height - header,
            confidence=0.60,
        )
        if image is None:
            return fallback

        try:
            import cv2
            import numpy as np

            from .vision import _as_rgb_array, recognize_chart

            rgb = _as_rgb_array(image)
            height, width = rgb.shape[:2]
            if width < 200 or height < 120:
                return ChartObservation(detected=False)

            detected, visual_score = recognize_chart(rgb)
            if not detected:
                return ChartObservation(
                    detected=False,
                    confidence=round(min(0.30, visual_score), 4),
                )

            # Analyze only the post-header area. This avoids browser chrome and
            # TradingView's top control band without assuming fixed screen
            # coordinates.
            y0 = min(header, max(0, height - 1))
            roi = rgb[y0:, :]
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150)

            row_activity = np.mean(edges > 0, axis=1)
            col_activity = np.mean(edges > 0, axis=0)

            # Chart/canvas regions tend to occupy a large contiguous area.
            # Use a low percentile threshold so sparse grid/candle structure
            # survives, then require a substantial span before trimming.
            row_threshold = max(0.003, float(np.percentile(row_activity, 35)))
            col_threshold = max(0.003, float(np.percentile(col_activity, 35)))

            active_rows = np.flatnonzero(row_activity >= row_threshold)
            active_cols = np.flatnonzero(col_activity >= col_threshold)

            if len(active_rows) and len(active_cols):
                left_i = int(active_cols.min())
                right_i = int(active_cols.max()) + 1
                top_i = int(active_rows.min()) + y0
                bottom_i = int(active_rows.max()) + y0 + 1

                # Never shrink a chart candidate below a meaningful fraction
                # of the target window; text-heavy noise must not create a tiny
                # false chart box.
                min_width = max(200, int(width * 0.55))
                min_height = max(120, int(height * 0.45))
                if right_i - left_i >= min_width and bottom_i - top_i >= min_height:
                    left, top = left_i, top_i
                    box_width, box_height = right_i - left_i, bottom_i - top_i
                else:
                    left, top = 0, y0
                    box_width, box_height = width, height - y0
            else:
                left, top = 0, y0
                box_width, box_height = width, height - y0

            # OCR is supporting evidence only. Count tokens whose centers fall
            # inside the candidate; do not lower the score merely because OCR
            # is unavailable.
            ocr_support = 0.0
            tokens = getattr(ocr_result, "tokens", ()) if ocr_result else ()
            if tokens:
                inside = 0
                for token in tokens:
                    cx = token.left + token.width / 2
                    cy = token.top + token.height / 2
                    if left <= cx < left + box_width and top <= cy < top + box_height:
                        inside += 1
                ocr_support = min(0.12, inside / 25.0 * 0.12)

            confidence = min(1.0, round(0.88 * visual_score + ocr_support, 4))
            return ChartObservation(
                detected=True,
                left=window.left + left,
                top=window.top + top,
                width=box_width,
                height=box_height,
                confidence=confidence,
            )
        except (ImportError, ValueError, TypeError, AttributeError):
            # A visual detector must fail closed rather than invent a region.
            return ChartObservation(detected=False, confidence=0.0)
