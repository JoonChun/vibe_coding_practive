from server.services import timeseries as ts


def test_downsample_no_duplicate_last():
    curve = list(range(160))
    out = ts.downsample(curve)
    assert out[-1] == 159
    assert out[-1] != out[-2]  # 마지막 점 중복 없음
    assert len(out) < len(curve)


def test_downsample_short_passthrough():
    assert ts.downsample([1, 2, 3]) == [1, 2, 3]


def test_detect_split_anomaly():
    assert ts.detect_split_anomaly([100, 101, 99, 102]) is None  # 정상 급등락 없음
    assert ts.detect_split_anomaly([100, 100, 50, 51]) == 2       # 2:1 분할(반토막)
    assert ts.detect_split_anomaly([100, 210]) == 1               # 1:2 역분할


def test_epoch_to_date():
    assert ts.epoch_to_date(1700000000).count("-") == 2   # YYYY-MM-DD
    assert ts.epoch_to_date(1700000000, "%Y-%m").count("-") == 1
    assert ts.epoch_to_date(None) is None
    assert ts.epoch_to_date("bad") is None
