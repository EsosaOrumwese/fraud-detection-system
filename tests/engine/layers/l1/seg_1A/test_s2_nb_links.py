import math

import pytest

from engine.layers.l1.seg_1A.s0_foundations.l1.design import (
    DesignDictionaries,
    DesignVectors,
    DispersionCoefficients,
    HurdleCoefficients,
)
from engine.layers.l1.seg_1A.s2_nb_outlets import NBLinks, compute_links_from_design, compute_nb_links


def test_compute_nb_links():
    beta_mu = (0.2, 0.1)
    beta_phi = (0.4, -0.1, 0.5)
    design_mu = (1.0, 0.5)
    design_phi = (1.0, 0.5, 0.25)

    links = compute_nb_links(
        beta_mu=beta_mu,
        beta_phi=beta_phi,
        design_mean=design_mu,
        design_dispersion=design_phi,
    )
    assert isinstance(links, NBLinks)
    expected_eta_mu = sum(b * x for b, x in zip(beta_mu, design_mu))
    expected_eta_phi = sum(b * x for b, x in zip(beta_phi, design_phi))
    assert math.isclose(links.eta_mu, expected_eta_mu)
    assert math.isclose(links.eta_phi, expected_eta_phi)
    assert links.mu > 0.0
    assert links.phi > 0.0


def test_compute_links_from_design():
    dicts = DesignDictionaries(mcc=(1234,), channel=("CP", "CNP"), gdp_bucket=(1, 2, 3, 4, 5))
    hurdle_coeffs = HurdleCoefficients(
        dictionaries=dicts,
        beta=(0.0,) * (1 + len(dicts.mcc) + len(dicts.channel) + len(dicts.gdp_bucket)),
        beta_mu=(0.2, 0.3, -0.1, 0.5),
    )
    dispersion_coeffs = DispersionCoefficients(dictionaries=dicts, beta_phi=(0.1, 0.5, -0.2, 0.4, 0.05))
    x_nb_mean = (1.0, 1.0, 1.0, 0.0)
    x_nb_dispersion = (1.0, 1.0, 1.0, 0.0, math.log(1000.0))
    design = DesignVectors(
        merchant_id=1,
        bucket=1,
        gdp=1000.0,
        log_gdp=math.log(1000.0),
        x_hurdle=(1.0,),
        x_nb_mean=x_nb_mean,
        x_nb_dispersion=x_nb_dispersion,
    )

    links = compute_links_from_design(
        design,
        hurdle=hurdle_coeffs,
        dispersion=dispersion_coeffs,
    )
    expected_eta_mu = sum(b * x for b, x in zip(hurdle_coeffs.beta_mu, x_nb_mean))
    expected_eta_phi = sum(b * x for b, x in zip(dispersion_coeffs.beta_phi, x_nb_dispersion))
    assert math.isclose(links.eta_mu, expected_eta_mu)
    assert math.isclose(links.eta_phi, expected_eta_phi)
    assert links.mu > 0.0
    assert links.phi > 0.0


def test_shape_mismatch_raises():
    with pytest.raises(Exception):
        compute_nb_links(
            beta_mu=(0.0,),
            beta_phi=(0.0,),
            design_mean=(1.0, 0.2),
            design_dispersion=(1.0,),
        )
