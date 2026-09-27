import pytest

from analytics_worker.hedonic import sales_sample
from analytics_worker.synthetic import generate_market


@pytest.fixture(scope="session")
def market():
    df, truth = generate_market(3000, seed=11)
    return df, truth


@pytest.fixture(scope="session")
def sales(market):
    return sales_sample(market[0])
