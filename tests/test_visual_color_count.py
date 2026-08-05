from training.pipeline.visual.color_count import connected_components, distance_peaks, union_masks


def test_connected_components_filters_noise_and_preserves_geometry() -> None:
    width, height = 8, 5
    foreground = {(1, 1), (1, 2), (2, 1), (2, 2), (5, 1), (6, 1), (5, 2), (6, 2), (7, 4)}
    mask = [(x, y) in foreground for y in range(height) for x in range(width)]

    components = connected_components(mask, width, height, minimum_area=3)

    assert [component.area for component in components] == [4, 4]
    assert components[0].to_dict() == {
        "area": 4,
        "x_min": 1,
        "y_min": 1,
        "x_max": 2,
        "y_max": 2,
        "width": 2,
        "height": 2,
    }


def test_union_masks() -> None:
    assert union_masks([False, True, False], [True, False, False]) == [True, True, False]


def test_distance_peaks_separates_touching_discs() -> None:
    width = height = 48
    centers = [(16, 24), (31, 24)]
    mask = [
        any((x - cx) ** 2 + (y - cy) ** 2 <= 10**2 for cx, cy in centers)
        for y in range(height)
        for x in range(width)
    ]

    peaks = distance_peaks(mask, width, height, minimum_radius=6, minimum_separation=10)

    assert len(peaks) == 2
    assert [(peak.x, peak.y) for peak in peaks] == centers
