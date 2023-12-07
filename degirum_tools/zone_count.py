#
# zone_count.py: polygon zone object counting support
#
# Copyright DeGirum Corporation 2023
# All rights reserved
#
# Implements classes for polygon zone object counting
#

import numpy as np, cv2
from typing import Tuple, Optional, Any
from .ui_support import Display


class _PolygonZone:
    """
    A class for defining a polygon-shaped zone within a frame for detecting objects.

    Attributes:
        polygon (np.ndarray): A polygon represented by a numpy array of shape
            `(N, 2)`, containing the `x`, `y` coordinates of the points.
        frame_resolution_wh (Tuple[int, int]): The frame resolution (width, height)
        triggering_position: The position within the bounding box that triggers the zone
        current_count (int): The current count of detected objects within the zone
        mask (np.ndarray): The 2D bool mask for the polygon zone
    """

    def __init__(
        self,
        polygon: np.ndarray,
        frame_resolution_wh: Tuple[int, int],
        triggering_position: str,
    ):
        self.polygon = polygon.astype(int)
        self.frame_resolution_wh = frame_resolution_wh
        self.triggering_position = triggering_position

        self.width, self.height = frame_resolution_wh
        self.mask = np.zeros((self.height + 1, self.width + 1))
        cv2.fillPoly(self.mask, [polygon], color=1)

    def trigger(self, bboxes: np.ndarray) -> np.ndarray:
        """
        Determines if the detections are within the polygon zone.

        Parameters:
            bboxes (np.ndarray): the numpy array of shape `(N, 4)` of bounding boxes to be checked against the polygon zone

        Returns:
            np.ndarray: A boolean numpy array indicating
                if each detection is within the polygon zone
        """

        # clip to frame
        bboxes[:, [0, 2]] = bboxes[:, [0, 2]].clip(0, self.width)
        bboxes[:, [1, 3]] = bboxes[:, [1, 3]].clip(0, self.height)

        clipped_anchors = np.ceil(
            _PolygonZone.get_anchor_coordinates(
                xyxy=bboxes, anchor=self.triggering_position
            )
        ).astype(int)

        is_in_zone = self.mask[clipped_anchors[:, 1], clipped_anchors[:, 0]]
        return is_in_zone.astype(bool)

    @staticmethod
    def get_anchor_coordinates(xyxy: np.ndarray, anchor: str) -> np.ndarray:
        """
        Calculates and returns the coordinates of a specific anchor point
        within the bounding boxes defined by the `xyxy` attribute. The anchor
        point can be any of the predefined positions,
        such as `CENTER`, `CENTER_LEFT`, `BOTTOM_RIGHT`, etc.

        Args:
            xyxy (nd.array): An array of shape `(n, 4)` of bounding box coordinates,
                where `n` is the number of bounding boxes.
            anchor (str): An string specifying the position of the anchor point
                within the bounding box.

        Returns:
            np.ndarray: An array of shape `(n, 2)`, where `n` is the number of bounding
                boxes. Each row contains the `[x, y]` coordinates of the specified
                anchor point for the corresponding bounding box.

        Raises:
            ValueError: If the provided `anchor` is not supported.
        """
        if anchor == "CENTER":
            return np.array(
                [
                    (xyxy[:, 0] + xyxy[:, 2]) / 2,
                    (xyxy[:, 1] + xyxy[:, 3]) / 2,
                ]
            ).transpose()
        elif anchor == "CENTER_LEFT":
            return np.array(
                [
                    xyxy[:, 0],
                    (xyxy[:, 1] + xyxy[:, 3]) / 2,
                ]
            ).transpose()
        elif anchor == "CENTER_RIGHT":
            return np.array(
                [
                    xyxy[:, 2],
                    (xyxy[:, 1] + xyxy[:, 3]) / 2,
                ]
            ).transpose()
        elif anchor == "BOTTOM_CENTER":
            return np.array([(xyxy[:, 0] + xyxy[:, 2]) / 2, xyxy[:, 3]]).transpose()
        elif anchor == "BOTTOM_LEFT":
            return np.array([xyxy[:, 0], xyxy[:, 3]]).transpose()
        elif anchor == "BOTTOM_RIGHT":
            return np.array([xyxy[:, 2], xyxy[:, 3]]).transpose()
        elif anchor == "TOP_CENTER":
            return np.array([(xyxy[:, 0] + xyxy[:, 2]) / 2, xyxy[:, 1]]).transpose()
        elif anchor == "TOP_LEFT":
            return np.array([xyxy[:, 0], xyxy[:, 1]]).transpose()
        elif anchor == "TOP_RIGHT":
            return np.array([xyxy[:, 2], xyxy[:, 1]]).transpose()

        raise ValueError(f"{anchor} is not supported.")


class ZoneCounter:
    """
    Class to count detected object bounding boxes in polygon zones
    """

    # Triggering position within the bounding box
    CENTER = "CENTER"
    CENTER_LEFT = "CENTER_LEFT"
    CENTER_RIGHT = "CENTER_RIGHT"
    TOP_CENTER = "TOP_CENTER"
    TOP_LEFT = "TOP_LEFT"
    TOP_RIGHT = "TOP_RIGHT"
    BOTTOM_LEFT = "BOTTOM_LEFT"
    BOTTOM_CENTER = "BOTTOM_CENTER"
    BOTTOM_RIGHT = "BOTTOM_RIGHT"

    def __init__(
        self,
        count_polygons: np.ndarray,
        *,
        class_list: Optional[list] = None,
        per_class_display: bool = False,
        triggering_position: str = BOTTOM_CENTER,
        window_name: Optional[str] = None,
    ):
        """Constructor

        Args:
            count_polygons (nd.array): list of polygons to count objects in; each polygon is a list of points (x,y)
            class_list (list): list of classes to count; if None, all classes are counted
            per_class_display (bool): when True, display zone counts per class, otherwise display total zone counts
            triggering_position (str): the position within the bounding box that triggers the zone
            window_name (str): optional OpenCV window name to configure for interactive zone adjustment
        """

        self._wh: Optional[Tuple] = None
        self._zones: Optional[list] = None
        self._win_name = window_name
        self._mouse_callback_installed = False
        self._class_list = class_list
        self._per_class_display = per_class_display
        if class_list is None and per_class_display:
            raise ValueError(
                "class_list must be specified when per_class_display is True"
            )

        self._triggering_position = triggering_position
        self._polygons = [
            np.array(polygon, dtype=np.int32) for polygon in count_polygons
        ]

    def _lazy_init(self, result):
        """
        Complete deferred initialization steps
            - initialize polygon zones from model result object
            - install mouse callback

        Args:
            result: PySDK model result object
        """
        if self._zones is None:
            self._wh = (result.image.shape[1], result.image.shape[0])
            self._zones = [
                _PolygonZone(polygon, self._wh, self._triggering_position)
                for polygon in self._polygons
            ]
        if not self._mouse_callback_installed and self._win_name is not None:
            self._install_mouse_callback()

    def window_attach(self, win_name: str):
        """Attach OpenCV window for interactive zone adjustment by installing mouse callback

        Args:
            win_name (str): OpenCV window name to attach to
        """

        self._win_name = win_name
        self._mouse_callback_installed = False

    def count(self, result):
        """
        Detect object bounding boxes in polygon zones.
        Update each result object `result.results[i]` by adding "in_zone" key to it,
        when this object is in a zone and its class belongs to a class list specified
        in a constructor. "in_zone" key value is the index of the zone where this object
        is detected.

        Args:
            result: PySDK model result object
        """

        self._lazy_init(result)

        if self._zones is None:
            return

        def in_class_list(obj):
            return (
                True
                if self._class_list is None
                else obj["label"] in self._class_list
                if "label" in obj
                else False
            )

        filtered_results = [
            obj for obj in result.results if "bbox" in obj and in_class_list(obj)
        ]

        if len(filtered_results) == 0:
            return

        bboxes = np.array([obj["bbox"] for obj in filtered_results])

        for zi, zone in enumerate(self._zones):
            triggers = zone.trigger(bboxes)
            [
                obj.update({"in_zone": zi})
                for obj, flag in zip(filtered_results, triggers)
                if flag
            ]

    def display(self, result, image: np.ndarray) -> np.ndarray:
        """
        Display polygon zones and zone counts on a given image

        Args:
            result: PySDK result object to display (should be the same as used in count() method)
            image (np.ndarray): image to display on

        Returns:
            np.ndarray: annotated image
        """

        def color_complement(color):
            adj_color = (color[0] if isinstance(color, list) else color)[::-1]
            return tuple([255 - c for c in adj_color])

        zone_color = color_complement(result.overlay_color)
        background_color = color_complement(result.overlay_fill_color)

        npolygons = len(self._polygons)

        # count objects in zones
        if self._per_class_display and self._class_list is not None:
            zone_counts = [[0] * len(self._class_list) for i in range(npolygons)]
            for obj in result.results:
                if (zi := obj.get("in_zone", -1)) != -1:
                    try:
                        zone_counts[zi][self._class_list.index(obj["label"])] += 1
                    except Exception:
                        pass  # ignore missing classes/keys

        else:
            zone_counts = [[0] for i in range(npolygons)]
            for obj in result.results:
                if (zi := obj.get("in_zone", -1)) != -1:
                    zone_counts[zi][0] += 1

        # draw annotations
        for zi in range(npolygons):
            cv2.polylines(
                image, [self._polygons[zi]], True, zone_color, result.overlay_line_width
            )

            if self._per_class_display and self._class_list is not None:
                text = f"Zone {zi}:"
                for ci, class_name in enumerate(self._class_list):
                    text += f"\n {class_name}: {zone_counts[zi][ci]}"
            else:
                text = f"Zone {zi}: {zone_counts[zi][0]}"

            Display.put_text(
                image,
                text,
                tuple(x + result.overlay_line_width for x in self._polygons[zi][0]),
                zone_color,
                background_color,
                cv2.FONT_HERSHEY_PLAIN,
                result.overlay_font_scale,
            )
        return image

    def count_and_display(self, result, image: np.ndarray) -> np.ndarray:
        """
        Count detected object bounding boxes in polygon zones and display them on model result image

        Args:
            result: PySDK model result object
            image (np.ndarray): image to display on

        Returns:
            np.ndarray: annotated image
        """
        self.count(result)
        return self.display(result, image)

    @staticmethod
    def _mouse_callback(event: int, x: int, y: int, flags: int, self: Any):
        """Mouse callback for OpenCV window for interactive zone operations"""

        click_point = np.array((x, y))

        def zone_update():
            idx = self._gui_state["update"]
            if idx >= 0 and self._wh is not None:
                self._zones[idx] = _PolygonZone(
                    self._polygons[idx], self._wh, self._triggering_position
                )

        if event == cv2.EVENT_LBUTTONDOWN:
            for idx, polygon in enumerate(self._polygons):
                if cv2.pointPolygonTest(polygon, (x, y), False) > 0:
                    zone_update()
                    self._gui_state["dragging"] = polygon
                    self._gui_state["offset"] = click_point
                    self._gui_state["update"] = idx
                    break

        if event == cv2.EVENT_RBUTTONDOWN:
            for idx, polygon in enumerate(self._polygons):
                for pt in polygon:
                    if np.linalg.norm(pt - click_point) < 10:
                        zone_update()
                        self._gui_state["dragging"] = pt
                        self._gui_state["offset"] = click_point
                        self._gui_state["update"] = idx
                        break

        elif event == cv2.EVENT_MOUSEMOVE:
            if self._gui_state["dragging"] is not None:
                delta = click_point - self._gui_state["offset"]
                self._gui_state["dragging"] += delta
                self._gui_state["offset"] = click_point

        elif event == cv2.EVENT_LBUTTONUP or event == cv2.EVENT_RBUTTONUP:
            self._gui_state["dragging"] = None
            zone_update()
            self._gui_state["update"] = -1

    def _install_mouse_callback(self):
        try:
            cv2.setMouseCallback(self._win_name, ZoneCounter._mouse_callback, self)  # type: ignore[attr-defined]
            self._gui_state = {"dragging": None, "update": -1}
            self._mouse_callback_installed = True
        except Exception:
            pass  # ignore errors
