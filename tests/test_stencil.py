"""Tests for stencil functionality."""

import jax.numpy as jnp

from probfindiff import stencil


def test_multivariate():
    xs_1d = jnp.arange(1, 4, dtype=float)
    xs = stencil.multivariate(xs_1d=xs_1d, shape_input=(7,))
    assert xs.shape == (7, 7, 3)
