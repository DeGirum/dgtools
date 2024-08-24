#
# notifier.py: notification analyzer
#
# Copyright DeGirum Corporation 2024
# All rights reserved
#
# Implements analyzer class to generate notifications based on triggered events.
# It works with conjunction with EventDetector analyzer.
#

import numpy as np
from .result_analyzer_base import ResultAnalyzerBase
from .ui_support import put_text, color_complement, deduce_text_color, CornerPosition
from typing import Tuple, Union, Optional
import time


class EventNotifier(ResultAnalyzerBase):
    """
    Class to generate notifications based on triggered events.
    It works with conjunction with EventDetector analyzer.

    Adds `notifications` dictionary to the `result` object, where keys are names of generated
    notifications and values are notification messages.
    """

    def __init__(
        self,
        name: str,
        condition: str,
        *,
        holdoff: Union[Tuple[float, str], int, float],
        message: str,
        token: Optional[str] = None,
        show_overlay: bool = True,
        annotation_color: Optional[tuple] = None,
        annotation_corner: CornerPosition = CornerPosition.BOTTOM_LEFT,
        annotation_cool_down: float = 3.0,
    ):
        """
        Constructor

        Args:
            name: name of the notification event
            condition: condition to trigger notification; may be any valid Python expression, referencing
                event names, as generated by preceding EventDetector analyzers.
            holdoff: holdoff time to suppress repeated notifications; it is either integer holdoff value in frames,
                floating-point holdoff value in seconds, or a tuple in a form (holdoff, unit), where unit is either
                "seconds" or "frames".
            message: message to display in the notification; may be valid Python f-string, in which you can use
                `{result}` placeholder with any valid derivatives to access current inference result.
                For example: "Total {len(result.results)} objects detected"
            token: optional cloud API access token to use for cloud notifications;
                if not specified, the notification is not sent to cloud
            show_overlay: if True, annotate image; if False, send through original image
            annotation_color: Color to use for annotations, None to use complement to result overlay color
            annotation_corner: corner to place annotation text
            annotation_cool_down: time in seconds to keep notification on the screen
        """

        self._name = name
        self._token = token
        self._show_overlay = show_overlay
        self._annotation_color = annotation_color
        self._annotation_corner = annotation_corner
        self._annotation_cool_down = annotation_cool_down

        # compile condition to evaluate it later
        self._condition = compile(condition, "<string>", "eval")

        # parse holdoff duration
        self._holdoff_frames = 0
        self._holdoff_sec = 0.0
        if isinstance(holdoff, int):
            self._holdoff_frames = holdoff
        elif isinstance(holdoff, float):
            self._holdoff_sec = holdoff
        elif isinstance(holdoff, tuple):
            if holdoff[1] == "seconds":
                self._holdoff_sec = holdoff[0]
            elif holdoff[1] == "frames":
                self._holdoff_frames = int(holdoff[0])
            else:
                raise ValueError(
                    f"Invalid unit in holdoff time {holdoff[1]}, must be 'seconds' or 'frames'"
                )
        else:
            raise TypeError(f"Invalid holdoff time type: {holdoff}")

        self._message = message
        self._frame = 0
        self._prev_cond = False
        self._prev_frame = -1_000_000_000  # arbitrary big negative number
        self._prev_time = -1_000_000_000.0
        self._last_notifications: dict = {}
        self._last_display_time = -1_000_000_000.0

    def analyze(self, result):
        """
        Generate notification by analyzing given result according to the condition expression.

        If condition is met the first time, the notification is generated.

        If condition is met repeatedly on every consecutive frame, the notification is generated only once, when
        condition is met the first time.

        If condition is not met for a period less than holdoff time and then met again, the notification
        is not generated to reduce the number of notifications.

        When notification is generated, the notification message is stored in the `result.notifications` dictionary
        under the key equal to the notification name.

        Args:
            result: PySDK model result object
        """

        if not hasattr(result, "events_detected"):
            raise AttributeError(
                "Detected events info is not available in the result: insert EventDetector analyzer in a chain"
            )

        # evaluate condition using detected event names as variables in the condition expression
        var_dict = {v: (v in result.events_detected) for v in self._condition.co_names}
        cond = eval(self._condition, var_dict)

        if cond and not self._prev_cond:  # condition is met for the first time
            # check for holdoff time
            if (
                self._holdoff_frames > 0
                and (self._frame - self._prev_frame > self._holdoff_frames)
            ) or (
                self._holdoff_sec > 0
                and (time.time() - self._prev_time > self._holdoff_sec)
            ):
                if not hasattr(result, "notifications"):
                    result.notifications = {}
                result.notifications[self._name] = self._message.format(result=result)

                if self._token is not None:
                    # TODO: send notification to cloud
                    pass

                self._prev_frame = self._frame
                self._prev_time = time.time()

        self._prev_cond = cond
        self._frame += 1

    def annotate(self, result, image: np.ndarray) -> np.ndarray:
        """
        Display active notifications on a given image

        Args:
            result: PySDK result object to display (should be the same as used in analyze() method)
            image (np.ndarray): image to display on

        Returns:
            np.ndarray: annotated image
        """

        if not self._show_overlay:
            return image

        if hasattr(result, "notifications") and result.notifications:
            self._last_notifications = result.notifications
            self._last_display_time = time.time()
        else:
            if (
                not self._last_notifications
                or time.time() - self._last_display_time > self._annotation_cool_down
            ):
                return image

        bg_color = (
            color_complement(result.overlay_color)
            if self._annotation_color is None
            else self._annotation_color
        )
        text_color = deduce_text_color(bg_color)

        if self._annotation_corner == CornerPosition.TOP_LEFT:
            pos = (0, 0)
        elif self._annotation_corner == CornerPosition.TOP_RIGHT:
            pos = (image.shape[1], 0)
        elif self._annotation_corner == CornerPosition.BOTTOM_RIGHT:
            pos = (image.shape[1], image.shape[0])
        else:
            pos = (0, image.shape[0])

        return put_text(
            image,
            "\n".join(result.notifications.values()),
            pos,
            font_color=text_color,
            bg_color=bg_color,
            font_scale=result.overlay_font_scale,
            corner_position=self._annotation_corner,
        )
