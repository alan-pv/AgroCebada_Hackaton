import pytest

pytest.importorskip("flask")

from app import create_app
from app.modules import formatting

NAN = float("nan")


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


@pytest.mark.parametrize("value, expected", [
    (1234.5678, "1,234.57"),
    (-1234.5, "-1,234.50"),
    (0.5, "0.50"),
    (987654.321, "987,654.32"),
])
def test_number(value, expected):
    assert formatting.number(value) == expected


def test_number_digits_and_rounding():
    assert formatting.number(1234.5678, 0) == "1,235"
    assert formatting.number(2.671) == "2.67"
    assert formatting.number(2.678) == "2.68"
    # Un negativo que se redondea a cero no lleva signo
    assert formatting.number(-0.001) == "0.00"


def test_money():
    assert formatting.money(24772.6) == "$24,773"
    assert formatting.money(24772.6, 2) == "$24,772.60"
    assert formatting.money(-1500) == "-$1,500"
    assert formatting.money(-0.4) == "$0"


def test_percent():
    assert formatting.percent(0.27) == "27 %"
    assert formatting.percent(0.5) == "50 %"
    assert formatting.percent(0.2734, 1) == "27.3 %"
    assert formatting.percent(0.2749) == "27 %"
    assert formatting.percent(0.2751) == "28 %"


@pytest.mark.parametrize("filter_fn", [formatting.number, formatting.money, formatting.percent])
@pytest.mark.parametrize("value", [None, NAN])
def test_missing_values_show_dash(filter_fn, value):
    assert filter_fn(value) == "—"


def test_filters_are_registered_in_app(client):
    template = client.application.jinja_env.from_string(
        "{{ 24772.6 | money }} | {{ 0.27 | percent }} | {{ 1234.5 | number }}"
    )
    assert template.render() == "$24,773 | 27 % | 1,234.50"
