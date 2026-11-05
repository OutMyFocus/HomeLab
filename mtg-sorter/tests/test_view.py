"""Turning and cropping the camera picture (Rotate and Crop on the scanner page)."""

import numpy as np
import pytest

from mtgscanner import view


def test_turn_then_crop():
    frame = np.zeros((100, 200, 3), np.uint8)   # 200 wide, 100 tall
    frame[0:10, 0:20] = 255                      # a white patch top-left
    turned = view.apply(frame, 90, None)
    assert turned.shape[:2] == (200, 100)        # now tall
    assert turned[0:20, 90:100].min() == 255     # top-left went to top-right
    cropped = view.apply(frame, 0, [0, 0, 0.5, 0.5])
    assert cropped.shape[:2] == (50, 100)


def test_boxes_follow_the_turn():
    box = [0.1, 0.2, 0.3, 0.4]
    assert view.turn_box(box, 1) == [0.6, 0.1, 0.8, 0.3]
    assert view.turn_box(box, 4) == box
    assert view.turn_box(view.turn_box(box, 1), 3) == box


def test_crop_inside_a_crop_and_back():
    outer = [0.2, 0.2, 0.6, 0.6]
    full = view.inside([0.5, 0.5, 1, 1], outer)
    assert full == pytest.approx([0.4, 0.4, 0.6, 0.6])
    assert view.relative(full, outer) == pytest.approx([0.5, 0.5, 1, 1])


def test_bad_values():
    assert view.clean_rotation(450) == 90 and view.clean_rotation(45) is None and view.clean_rotation("x") is None
    assert view.clean_box([0, 0, 0.01, 1]) is None      # too thin
    assert view.clean_box("nope") is None
    assert view.clean_box([1, 1, 0, 0]) == [0, 0, 1, 1]  # corners put in order
