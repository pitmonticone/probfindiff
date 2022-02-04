"""Top-level API."""

import functools
from collections import namedtuple
from functools import partial
from typing import Any, Optional, Tuple

import jax
import jax.numpy as jnp

from probfindiff import collocation, stencil
from probfindiff.typing import ArrayLike, KernelFunctionLike
from probfindiff.utils import autodiff
from probfindiff.utils import kernel as kernel_module
from probfindiff.utils import kernel_zoo

FiniteDifferenceScheme = namedtuple(
    "FiniteDifferenceScheme",
    (
        "weights",
        "covs_marginal",
        "order_derivative",
    ),
)
"""Finite difference schemes.

A finite difference scheme consists of a weight-vector, marginal covariances, and offset indices.
"""


@jax.jit
def differentiate(fx: ArrayLike, *, scheme: FiniteDifferenceScheme) -> ArrayLike:
    """Apply a finite difference scheme to a vector of function evaluations.

    Parameters
    ----------
    fx
        Array of function evaluated to be differentiated numerically. Shape ``(n,)``.
    scheme
        PN finite difference schemes.


    Returns
    -------
    :
        Finite difference approximation and the corresponding base-uncertainty. Shapes `` (n,), (n,)``.
    """
    weights, unc_base, *_ = scheme
    dfx = jnp.einsum("...k,...k->...", weights, fx)
    return dfx, unc_base


def differentiate_along_axis(
    fx: ArrayLike, *, axis: int, scheme: FiniteDifferenceScheme
) -> ArrayLike:
    """Apply a finite difference scheme along a specified axis.

    Parameters
    ----------
    fx
        Array of function evaluated to be differentiated numerically. Shape ``(..., n, ...)``.
    axis
        Axis along which the scheme should be applied.
    scheme
        PN finite difference schemes.


    Returns
    -------
    :
        Finite difference approximation and the corresponding base-uncertainty. Shapes `` (..., n, ...), (n,)``.
    """

    fd = partial(differentiate, scheme=scheme)
    return jnp.apply_along_axis(fd, axis=axis, arr=fx)


_DEFAULT_NOISE_VARIANCE = 1e-14
"""We might change the defaults again soon, so we encapsulate it into a variable..."""


@functools.partial(
    jax.jit, static_argnames=("order_derivative", "order_method", "kernel")
)
def backward(
    *,
    dx: float,
    order_derivative: int = 1,
    order_method: int = 2,
    kernel: Optional[KernelFunctionLike] = None,
    noise_variance: float = _DEFAULT_NOISE_VARIANCE,
) -> Any:
    """Backward coefficients in 1d.

    Parameters
    ----------
    dx
        Step-size.
    order_derivative
        Order of the derivative.
    order_method
        Desired accuracy.
    kernel
        Kernel function. Defines the function-model.
    noise_variance
        Variance of the observation noise.

    Returns
    -------
    :
        Finite difference coefficients and base uncertainty.
    """
    offset = -jnp.arange(order_derivative + order_method, step=1)
    grid = offset * dx
    scheme = from_grid(
        xs=grid,
        order_derivative=order_derivative,
        kernel=kernel,
        noise_variance=noise_variance,
    )
    return scheme, grid


@functools.partial(
    jax.jit, static_argnames=("order_derivative", "order_method", "kernel")
)
def forward(
    *,
    dx: float,
    order_derivative: int = 1,
    order_method: int = 2,
    kernel: Optional[KernelFunctionLike] = None,
    noise_variance: float = _DEFAULT_NOISE_VARIANCE,
) -> Any:
    """Forward coefficients in 1d.

    Parameters
    ----------
    dx
        Step-size.
    order_derivative
        Order of the derivative.
    order_method
        Desired accuracy.
    kernel
        Kernel function. Defines the function-model.
    noise_variance
        Variance of the observation noise.

    Returns
    -------
    :
        Finite difference coefficients and base uncertainty.
    """
    offset = jnp.arange(order_derivative + order_method, step=1)
    grid = offset * dx
    scheme = from_grid(
        xs=grid,
        order_derivative=order_derivative,
        kernel=kernel,
        noise_variance=noise_variance,
    )
    return scheme, grid


@functools.partial(
    jax.jit, static_argnames=("order_derivative", "order_method", "kernel")
)
def central(
    *,
    dx: float,
    order_derivative: int = 1,
    order_method: int = 2,
    kernel: Optional[KernelFunctionLike] = None,
    noise_variance: float = _DEFAULT_NOISE_VARIANCE,
) -> Any:
    """Central coefficients in 1d.

    Parameters
    ----------
    dx
        Step-size.
    order_derivative
        Order of the derivative.
    order_method
        Desired accuracy.
    kernel
        Kernel function. Defines the function-model.
    noise_variance
        Variance of the observation noise.

    Returns
    -------
    :
        Finite difference coefficients and base uncertainty.
    """
    num_central = (2 * ((order_derivative + 1.0) / 2.0) // 2) - 1 + order_method
    num_side = num_central // 2
    offset = jnp.arange(-num_side, num_side + 1, step=1)
    grid = offset * dx
    scheme = from_grid(
        xs=grid,
        order_derivative=order_derivative,
        kernel=kernel,
        noise_variance=noise_variance,
    )
    return scheme, grid


@functools.partial(jax.jit, static_argnames=("order_derivative", "kernel"))
def from_grid(
    *,
    xs: ArrayLike,
    order_derivative: int = 1,
    kernel: Optional[KernelFunctionLike] = None,
    noise_variance: float = _DEFAULT_NOISE_VARIANCE,
) -> Any:
    """Finite difference coefficients based on an array of offset indices.

    Parameters
    ----------
    order_derivative
        Order of the derivative.
    xs
        Grid. Shape ``(n,)``.
    kernel
        Kernel function. Defines the function-model.
    noise_variance
        Variance of the observation noise.

    Returns
    -------
    :
        Finite difference coefficients and base uncertainty.
    """
    if kernel is None:
        kernel = _default_kernel(min_order=xs.shape[0])
    L = functools.reduce(autodiff.compose, [autodiff.derivative] * order_derivative)
    ks = kernel_module.differentiate(k=kernel, L=L)

    x = jnp.zeros_like(xs[0])
    weights, cov_marginal = collocation.non_uniform_nd(
        x=x[..., None],
        xs=xs[..., None],
        ks=ks,
        noise_variance=noise_variance,
    )
    scheme = FiniteDifferenceScheme(
        weights,
        cov_marginal,
        order_derivative=order_derivative,
    )
    return scheme


def _default_kernel(*, min_order: int) -> KernelFunctionLike:
    return functools.partial(kernel_zoo.polynomial, p=jnp.ones((min_order,)))


@functools.partial(jax.jit, static_argnames=("shape_input",))
def multivariate(
    scheme_1d: FiniteDifferenceScheme, xs_1d: ArrayLike, shape_input: Tuple[int]
) -> Tuple[FiniteDifferenceScheme, ArrayLike]:
    r"""Turn a univariate finite-difference scheme into a multivariate scheme.

    Parameters
    ----------
    scheme_1d
        Input finite-difference scheme in 1d.
    xs_1d
        Input finite-difference grid/stencil in 1d.
    shape_input
        Input dimension of the to-be-differentiated function as a shape-tuple.
        If the goal is the gradient of an `n`-dimensional function, ``shape_input=(n,)``.

    Returns
    -------
    :
        Tuple of a new scheme and a new grid.
        The new scheme consists of a 1d set of weights.
        The new grid has shape ``(n, n, c)``.

    Examples
    --------
    >>> from probfindiff import central
    >>> scheme_1d, xs_1d = central(dx=1.)
    >>> print(xs_1d)
    [-1.  0.  1.]

    >>> scheme, xs = multivariate(scheme_1d=scheme_1d, xs_1d=xs_1d, shape_input=(2,))
    >>> print(xs.shape)
    (2, 2, 3)
    >>> print(xs)
    [[[-1.  0.  1.]
      [ 0.  0.  0.]]
     [[ 0.  0.  0.]
      [-1.  0.  1.]]]
    >>> print(scheme.weights)
    [-0.5  0.   0.5]
    """
    xs_full = stencil.multivariate(xs_1d=xs_1d, shape_input=shape_input)
    return scheme_1d, xs_full
