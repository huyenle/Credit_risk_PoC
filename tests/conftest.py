"""Shared fixtures: regenerate the portfolio and ground truth once per session so
tests always run against artifacts produced by the current code."""

from __future__ import annotations

import importlib
import warnings

import pytest


@pytest.fixture(scope="session", autouse=True)
def artifacts():
    """Regenerate data/portfolio.csv and data/ground_truth.yaml before tests."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gen = importlib.import_module("generate_portfolio")
        gt = importlib.import_module("compute_ground_truth")
        gen.main()
        gt.main()
