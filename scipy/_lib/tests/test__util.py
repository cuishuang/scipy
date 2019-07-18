from __future__ import division, print_function, absolute_import

from multiprocessing import Pool
from multiprocessing.pool import Pool as PWL
import os

import numpy as np
from numpy.testing import assert_equal, assert_
import pytest
from pytest import raises as assert_raises, deprecated_call

import scipy
from scipy._lib._util import _aligned_zeros, check_random_state, MapWrapper


def test__aligned_zeros():
    niter = 10

    def check(shape, dtype, order, align):
        err_msg = repr((shape, dtype, order, align))
        x = _aligned_zeros(shape, dtype, order, align=align)
        if align is None:
            align = np.dtype(dtype).alignment
        assert_equal(x.__array_interface__['data'][0] % align, 0)
        if hasattr(shape, '__len__'):
            assert_equal(x.shape, shape, err_msg)
        else:
            assert_equal(x.shape, (shape,), err_msg)
        assert_equal(x.dtype, dtype)
        if order == "C":
            assert_(x.flags.c_contiguous, err_msg)
        elif order == "F":
            if x.size > 0:
                # Size-0 arrays get invalid flags on Numpy 1.5
                assert_(x.flags.f_contiguous, err_msg)
        elif order is None:
            assert_(x.flags.c_contiguous, err_msg)
        else:
            raise ValueError()

    # try various alignments
    for align in [1, 2, 3, 4, 8, 16, 32, 64, None]:
        for n in [0, 1, 3, 11]:
            for order in ["C", "F", None]:
                for dtype in [np.uint8, np.float64]:
                    for shape in [n, (1, 2, 3, n)]:
                        for j in range(niter):
                            check(shape, dtype, order, align)


def test_check_random_state():
    # If seed is None, return the RandomState singleton used by np.random.
    # If seed is an int, return a new RandomState instance seeded with seed.
    # If seed is already a RandomState instance, return it.
    # Otherwise raise ValueError.
    rsi = check_random_state(1)
    assert_equal(type(rsi), np.random.RandomState)
    rsi = check_random_state(rsi)
    assert_equal(type(rsi), np.random.RandomState)
    rsi = check_random_state(None)
    assert_equal(type(rsi), np.random.RandomState)
    assert_raises(ValueError, check_random_state, 'a')
    if hasattr(np.random, 'Generator'):
        # np.random.Generator is only available in numpy >= 1.17
        rg = np.random.Generator(np.random.PCG64())
        rsi = check_random_state(rg)
        assert_equal(type(rsi), np.random.Generator)


class TestMapWrapper(object):

    def setup_method(self):
        self.input = np.arange(10.)
        self.output = np.sin(self.input)

    def test_serial(self):
        p = MapWrapper(1)
        assert_(p._mapfunc is map)
        assert_(p.pool is None)
        assert_(p._own_pool is False)
        out = list(p(np.sin, self.input))
        assert_equal(out, self.output)

        with assert_raises(RuntimeError):
            p = MapWrapper(0)

    def test_parallel(self):
        with MapWrapper(2) as p:
            out = p(np.sin, self.input)
            assert_equal(list(out), self.output)

            assert_(p._own_pool is True)
            assert_(isinstance(p.pool, PWL))
            assert_(p._mapfunc is not None)

        # the context manager should've closed the internal pool
        # check that it has by asking it to calculate again.
        with assert_raises(Exception) as excinfo:
            p(np.sin, self.input)

        # on py27 an AssertionError is raised, on >py27 it's a ValueError
        err_type = excinfo.type
        assert_((err_type is ValueError) or (err_type is AssertionError))

        # can also set a PoolWrapper up with a map-like callable instance
        try:
            p = Pool(2)
            q = MapWrapper(p.map)

            assert_(q._own_pool is False)
            q.close()

            # closing the PoolWrapper shouldn't close the internal pool
            # because it didn't create it
            out = p.map(np.sin, self.input)
            assert_equal(list(out), self.output)
        finally:
            p.close()


# get our custom ones and a few from the "import *" cases
@pytest.mark.parametrize(
    'key', ('fft', 'ifft', 'diag', 'arccos',
            'randn', 'rand', 'array', 'finfo'))
def test_numpy_deprecation(key):
    """Test that 'from numpy import *' functions are deprecated."""
    if key in ('fft', 'ifft', 'diag', 'arccos'):
        arg = [1.0, 0.]
    elif key == 'finfo':
        arg = float
    else:
        arg = 2
    func = getattr(scipy, key)
    if key == 'fft':
        match = r'scipy\.fft.*deprecated.*1.5.0.*'
    else:
        match = r'scipy\.%s is deprecated.*2\.0\.0' % key
    with deprecated_call(match=match) as dep:
        func(arg)  # deprecated
    fname = os.path.splitext(os.path.basename(dep.list[0].filename))[0]
    assert fname == 'test__util'
    if key in ('rand', 'randn'):
        root = np.random
    elif key in ('fft', 'ifft'):
        root = np.fft
    else:
        root = np
    func_np = getattr(root, key)
    func_np(arg)  # not deprecated
    assert func_np is not func
