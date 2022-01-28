"""Finite difference coefficients. (In 1d.)"""

import functools

import jax.numpy as jnp

from pnfindiff import collocation
from pnfindiff.aux import diffops, kernel


def backward(x, *, dx, deriv=1, acc=2, k=None):
    """Backward coefficients in 1d."""
    xs = x - jnp.arange(deriv + acc) * dx
    ks = _differentiate_kernel(deriv=deriv, k=k)
    return scattered_1d(x=x, xs=xs, ks=ks)


def forward(x, *, dx, deriv=1, acc=2, k=None):
    """Forward coefficients in 1d."""
    xs = x + jnp.arange(deriv + acc) * dx
    ks = _differentiate_kernel(deriv=deriv, k=k)
    return scattered_1d(x=x, xs=xs, ks=ks)


def _differentiate_kernel(*, deriv, k):
    L = functools.reduce(diffops.compose, [diffops.deriv_scalar()] * deriv)
    if k is None:
        _, k = kernel.exp_quad()
    k_batch, _ = kernel.batch_gram(k)
    lk_batch, lk = kernel.batch_gram(L(k, argnums=0))
    llk_batch, _ = kernel.batch_gram(L(lk, argnums=1))
    return k_batch, lk_batch, llk_batch


def scattered_1d(*, x, xs, ks):
    """Finite difference coefficients for scattered data."""
    return scattered_nd(x=jnp.array([x]), xs=xs[:, None], ks=ks)


def scattered_nd(*, x, xs, ks):
    """Finite difference coefficients for scattered data in multiple dimensions."""

    k, lk, llk = ks
    n = xs.shape[0]

    K = k(xs, xs.T).reshape((n, n))
    LK = lk(x[None, :], xs.T).reshape((n,))
    LLK = llk(x[None, :], x[None, :].T).reshape(())
    return collocation.unsymmetric(K=K, LK0=LK, LLK=LLK)
