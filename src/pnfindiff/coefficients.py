"""Finite difference coefficients. (In 1d.)"""

import functools

import jax.numpy as jnp

from pnfindiff import collocation
from pnfindiff.aux import diffop, kernel


def backward(x, *, dx, deriv=1, acc=2):
    """Backward coefficients in 1d."""
    offset = -jnp.arange(deriv + acc, step=1)
    return from_offset(x=x, dx=dx, offset=offset, deriv=deriv)


def forward(x, *, dx, deriv=1, acc=2):
    """Forward coefficients in 1d."""
    offset = jnp.arange(deriv + acc, step=1)
    return from_offset(x=x, dx=dx, offset=offset, deriv=deriv)


def center(x, *, dx, deriv=1, acc=2):
    """Forward coefficients in 1d."""
    num = (deriv + acc) // 2
    offset = jnp.arange(-num, num + 1, step=1)
    return from_offset(x=x, dx=dx, offset=offset, deriv=deriv)


def from_offset(x, *, dx, offset, deriv=1):
    """Forward coefficients in 1d."""
    xs = x + offset * dx
    _, k = kernel.exp_quad()
    L = functools.reduce(diffop.compose, [diffop.deriv_scalar] * deriv)

    ks = kernel.differentiate(k=k, L=L)
    return scattered_1d(x=x, xs=xs, ks=ks)


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
