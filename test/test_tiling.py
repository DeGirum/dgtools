from degirum_tools.tile_strategy import SimpleTiling
from degirum_tools.math_support import edge_box_fusion
import numpy as np

def test_wbf():
    res_list = [
                {"bbox": [10, 40, 20, 50], "score": 0.8, "category_id": "1"},
                {"bbox": [10, 90, 20, 100], "score": 0.7, "category_id": "1"},
                {"bbox": [50, 90, 60, 100], "score": 0.6, "category_id": "1"},
                {"bbox": [55, 95, 65, 105], "score": 0.5, "category_id": "1"},
                {"bbox": [11, 45, 21, 55], "score": 0.9, "category_id": "1"}
    ]

    res_list_2 = [
                  {"bbox": [0, 0, 10, 10], "score": 0.8, "category_id": "1"},
                  {"bbox": [9, 0, 19, 10], "score": 0.8, "category_id": "1"},
                  {"bbox": [0, 9, 10, 19], "score": 0.8, "category_id": "1"},
                  {"bbox": [9, 9, 19, 19], "score": 0.8, "category_id": "1"}
    ]
    # Normalize for WBF
    for res in res_list:
        res['wbf_info'] = [res['bbox'][0] / 500, res['bbox'][1] / 500, res['bbox'][2] / 500, res['bbox'][3] / 500]
    for res in res_list_2:
        res['wbf_info'] = [res['bbox'][0] / 500, res['bbox'][1] / 500, res['bbox'][2] / 500, res['bbox'][3] / 500]

    # overlap > 0.8 y dimension, no overlap x dimension
    res = edge_box_fusion([res_list[1], res_list[2]], 0.8, 0.3)
    assert len(res) == 2

    # overlap both dimensions, 1D-IOU < 0.8
    res = edge_box_fusion([res_list[2], res_list[3]], 0.8, 0.3)
    assert len(res) == 2

    # overlap both dimensions, X 1D-IOU > 0.8
    res = edge_box_fusion([res_list[0], res_list[4]], 0.8, 0.3)
    assert len(res) == 1

    # overlap both dimensions, X 1D-IOU > 0.8, not same class
    res_list[4]['category_id'] = 2
    res = edge_box_fusion([res_list[0], res_list[4]], 0.8, 0.3)
    assert len(res) == 2
    res_list[4]['category_id'] = 1

    # overlap both dimensions, X 1D-IOU > 0.8, one box score is less than the score threshold
    res_list[4]['score'] = 0.2
    res = edge_box_fusion([res_list[0], res_list[4]], 0.8, 0.3, destructive=False)
    assert len(res) == 2
    res_list[4]['score'] = 0.8

    # All boxes (order matters to check if masking feature works in the IoU matching)
    res_list.append(res_list[1])
    res_list[1] = res_list[4]
    res_list.pop(4)
    res = edge_box_fusion(res_list, 0.8, 0.3)
    assert len(res) == 4

    # Corner case, fusion of four boxes at corners
    res = edge_box_fusion(res_list_2, 0.8, 0.3)
    assert len(res) == 1


def test_generate_tiles():
    # Tolerance accounts for rounding errors due to discrete nature of pixels.
    tolerance = 0.01

    class DummyModelParams:
        InputW = [640]
        InputH = [640]
    
    m_params = DummyModelParams()

    # 1 x 1 no overlap square, matching aspect ratio
    tile_strat = SimpleTiling(1, 1, 0)
    tile_strat._set_model_parameters(m_params)
    tiles = list(tile_strat._generate_tiles(np.zeros((100, 100, 3))))

    assert len(tiles) == 1
    assert tiles[0][1][1] == [0, 0, 100, 100]

    # 2 x 2 no overlap square, matching aspect ratio
    tile_strat = SimpleTiling(2, 2, 0)
    tile_strat._set_model_parameters(m_params)
    tiles = list(tile_strat._generate_tiles(np.zeros((100, 100, 3))))

    assert len(tiles) == 4
    assert tiles[0][1][1] == [0, 0, 50, 50]

    # 2 x 2 10% overlap, matching aspect ratio
    tile_strat = SimpleTiling(2, 2, 0.1)
    tile_strat._set_model_parameters(m_params)
    tiles = list(tile_strat._generate_tiles(np.zeros((640, 640, 3))))

    width = tiles[0][1][1][2]
    height = tiles[0][1][1][3]

    tile2_x = tiles[1][1][1][0]
    tile3_y = tiles[2][1][1][1]

    assert abs(((width - tile2_x) / width ) - 0.1) <= tolerance, 'Overlap width not close to 10%'
    assert abs(((height - tile3_y) / height) - 0.1 ) <= tolerance, 'Overlap height not close to 10%'

    # 2 x 2 rectangle, 10% overlap, matching aspect ratio
    m_params.InputH = [384]
    tile_strat = SimpleTiling(2, 2, 0.1)
    tile_strat._set_model_parameters(m_params)
    tiles = list(tile_strat._generate_tiles(np.zeros((384, 640, 3))))
    
    assert len(tiles) == 4

    width = tiles[0][1][1][2]
    height = tiles[0][1][1][3]

    tile2_x = tiles[1][1][1][0]
    tile3_y = tiles[2][1][1][1] 

    assert abs(((width - tile2_x) / width ) - 0.1) <= tolerance, 'Overlap width not close to 10%'
    assert abs(((height - tile3_y) / height) - 0.1 ) <= tolerance, 'Overlap height not close to 10%'

    # 2 x 2 rectangle, model aspect ratio > image aspect ratio, w >= h
    # model aspect ratio = 1, image aspect ratio = 1.666666
    # expect forced overlap in the y dimension
    m_params.InputH = [640]
    tile_strat = SimpleTiling(2, 2, 0)
    tile_strat._set_model_parameters(m_params)
    tiles = list(tile_strat._generate_tiles(np.zeros((384, 640, 3))))

    width = tiles[0][1][1][2]
    height = tiles[0][1][1][3]

    tile2_x = tiles[1][1][1][0]
    tile3_y = tiles[2][1][1][1] 

    assert width - tile2_x == 0
    assert (height - tile3_y) / height > tolerance

    for tile in tiles:
        assert tile[1][1][0] >= 0 and tile[1][1][0] <= 640
        assert tile[1][1][1] >= 0 and tile[1][1][1] <= 384
        assert tile[1][1][2] >= 0 and tile[1][1][2] <= 640
        assert tile[1][1][3] >= 0 and tile[1][1][3] <= 384

    # 2 x 2 rectangle, model aspect ratio < image aspect ratio, w >= h
    # model aspect ratio = 1.6666, image aspect ratio = 1
    # expect forced overlap in the x dimension
    m_params.InputH = [384]
    tile_strat = SimpleTiling(2, 2, 0)
    tile_strat._set_model_parameters(m_params)
    tiles = list(tile_strat._generate_tiles(np.zeros((640, 640, 3))))

    width = tiles[0][1][1][2]
    height = tiles[0][1][1][3]

    tile2_x = tiles[1][1][1][0]
    tile3_y = tiles[2][1][1][1] 

    assert (width - tile2_x) / width > tolerance
    assert height - tile3_y == 0

    for tile in tiles:
        assert tile[1][1][0] >= 0 and tile[1][1][0] <= 640
        assert tile[1][1][1] >= 0 and tile[1][1][1] <= 640
        assert tile[1][1][2] >= 0 and tile[1][1][2] <= 640
        assert tile[1][1][3] >= 0 and tile[1][1][3] <= 640

test_wbf()