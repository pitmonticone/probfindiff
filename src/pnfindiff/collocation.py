"""Global collocation with Gaussian processes."""

import jax.numpy as jnp


def unsymmetric(*, K, LK, LLK):

    weights = jnp.linalg.solve(K, LK.T).T
    unc_base = LLK - weights @ LK.T
    return weights, unc_base
