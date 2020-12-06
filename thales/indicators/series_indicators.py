"""Indicators that can be calculated directly from a single Pandas.Series of
price data with a DateTime index."""

__all__ = ["DEMA", "EMA", "KAMA", "KER", "MACD", "RSI", "SMA", "TEMA", "TRIMA", "WMA"]

import numpy as np
import pandas as pd
from scipy.signal import convolve


# Typical parameters for number of time periods in moving average indicators:
MA_TYPICAL_N = list(range(2, 11, 1)) + list(range(20, 81, 20)) + list(range(100, 1001, 100))


def validate_series(s: pd.Series):
    """Perform basic data validation checks on an input series of price data."""
    assert isinstance(s.index, pd.DatetimeIndex), "Series index must be pd.DatetimeIndex"
    s = s.sort_index(ascending=True)
    assert len(s.dropna()) == len(s), "Series cannot contain NaNs"
    return s


def convert_to_percent_diff(input_s: pd.Series, output_s: pd.Series):
    """If an output is usually directly proportional to input (e.g. a moving
    average) then it can be helpful for machine learning tasks to convert it to
    a percent difference from the input value, so that the learner does not
    learn directly from the input price."""
    return (output_s - input_s) / input_s


def convert_to_ratio(input_s: pd.Series, output_s: pd.Series):
    """Similar to `convert_to_percent_diff` but converts output to a ratio of
    the input price."""
    return output_s / input_s


class _SeriesInSeriesOut(pd.Series):
    """Subclass of Pandas.Series which takes a single input feature (i.e. a
    Pandas.Series of price data) and returns a technical indicator as a
    Pandas.Series."""

    # For each indicator `parameters` stores a range of typical parameter values
    # for the indicator-specific keyword argument in the init call:
    parameters = dict()

    def __init__(self, s: pd.Series, validate: bool = True,
                 as_percent_diff: bool = False, as_ratio: bool = False,
                 indicator_name: str = "", **kwargs):
        """Takes a 1-dimensional input data series and converts it to an output
        pandas.Series using the logic in the `apply_indicator` method.

        Args:
            s: input price data.
            validate: if True, validate input to ensure correct data format.
            as_percent_diff: if True apply `convert_to_percent_diff` to output.
            as_ratio: if True apply `convert_to_ratio` to output.
            indicator_name: technical indicator name.
        """
        if validate:
            s = validate_series(s)
        output = self.apply_indicator(s, **kwargs)
        if as_percent_diff:
            output = convert_to_percent_diff(s, output)
        elif as_ratio:
            output = convert_to_ratio(s, output)
        super().__init__(data=output)
        self.name = " - ".join([s for s in [s.name, indicator_name] if s])

    @staticmethod
    def apply_indicator(s: pd.Series, **kwargs):
        """Method applies indicator logic in subclasses."""
        return s


class _SeriesInDfOut(pd.DataFrame):
    """Subclass of Pandas.DataFrame which takes a single input feature (i.e. a
    Pandas.Series of price data) and returns a technical indicator as a
    Pandas.DataFrame."""

    # For each indicator `parameters` stores a range of typical parameter values
    # for the indicator-specific keyword argument in the init call:
    parameters = dict()

    def __init__(self, s: pd.Series, validate: bool = True,
                 as_percent_diff: bool = False, as_ratio: bool = False,
                 **kwargs):
        """Takes a 1-dimensional input data series and converts it to an output
        pandas.Series using the logic in the `apply_indicator` method.

        Args:
            s: input price data.
            validate: if True, validate input to ensure correct data format.
            as_percent_diff: if True apply `convert_to_percent_diff` to output.
            as_ratio: if True apply `convert_to_ratio` to output.
        """
        if validate:
            s = validate_series(s)
        output = self.apply_indicator(s, **kwargs)
        if as_percent_diff:
            for col in output.columns:
                output[col] = convert_to_percent_diff(s, output[col])
        elif as_ratio:
            for col in output.columns:
                output[col] = convert_to_ratio(s, output[col])
        super().__init__(data=output)

    @staticmethod
    def apply_indicator(s: pd.Series, **kwargs):
        """Method applies indicator logic in subclasses."""
        return pd.DataFrame(s)


class SMA(_SeriesInSeriesOut):
    """Simple Moving Average."""

    parameters = {"n": MA_TYPICAL_N}

    def __init__(self, s: pd.Series, n: int = 5, **kwargs):
        super().__init__(s, n=n, indicator_name=f"SMA (n={n:.0f})", **kwargs)
        self.n = n

    def apply_indicator(self, s: pd.Series, n: int = 5):
        """Simple moving average of `n` time periods."""
        return s.rolling(window=n).mean()


class EMA(_SeriesInSeriesOut):
    """Exponential moving average. When alpha is specified EMA is equivalent to:

    >>> s = pd.Series()
    >>> ema = [s[0]]
    >>> alpha = 0.5
    >>> for y_i in s[1:]:
    >>>     prev_s = ema[-1]
    >>>     ema.append(alpha*y_i + (1-alpha) * prev_s)
    """

    parameters = {"alpha": np.arange(0.05, 1, 0.05)}

    def __init__(self, s: pd.Series, alpha: float = None,
                 span: float = None, **kwargs):
        if not alpha and not span:
            span = len(s)
        label, value = ("alpha", alpha) if alpha else ("span", span)
        super().__init__(s, alpha=alpha, span=span, indicator_name=f"EMA ({label}={value})", **kwargs)
        self.alpha = alpha
        self.span = span

    def apply_indicator(self, s: pd.Series, alpha: float = None,
                        span: float = None):
        return s.ewm(alpha=alpha, span=span, adjust=False).mean()


class WMA(_SeriesInSeriesOut):
    """Weighted Moving Average."""

    parameters = {"n": MA_TYPICAL_N}

    def __init__(self, s: pd.Series, n: int = 5, **kwargs):
        super().__init__(s, n=n, indicator_name=f"WMA (n={n})", **kwargs)
        self.n = n

    @staticmethod
    def apply_indicator(s: pd.Series, n: int = 5):
        weights = np.arange(n, 0, -1)
        weights = weights / weights.sum()
        data = convolve(s, weights, mode="valid", method="auto")
        index = s.index[n-1:]
        return pd.Series(data, index=index)


class DEMA(_SeriesInSeriesOut):
    """Double exponential moving average. Implemention is equivalent to:

    >>> s = pd.Series()
    >>> ema_s: pd.Series = EMA(s)
    >>> double_ema = (2 * ema_s) - EMA(ema_s)
    """

    parameters = {"alpha": np.arange(0.05, 1, 0.05)}

    def __init__(self, s: pd.Series, alpha: float = None,
                 span: float = None, **kwargs):
        if not alpha and not span:
            span = len(s)
        label, value = ("alpha", alpha) if alpha else ("span", span)
        super().__init__(s, alpha=alpha, span=span, indicator_name=f"DEMA ({label}={value})", **kwargs)
        self.alpha = alpha
        self.span = span

    def apply_indicator(self, s: pd.Series, alpha: float = None,
                        span: float = None):
        ema = EMA(s, alpha=alpha, span=span, validate=False)
        return (2 * ema) - EMA(ema, alpha=alpha, span=span, validate=False)


class TEMA(_SeriesInSeriesOut):
    """Triple exponential moving average. Implemention is equivalent to:

    >>> s = pd.Series
    >>> ema = EMA(s)
    >>> triple_ema = (3 * ema) - (3 * EMA(ema)) + (EMA(EMA(ema)))
    """

    parameters = {"alpha": np.arange(0.05, 1, 0.05)}

    def __init__(self, s: pd.Series, alpha: float = None,
                 span: float = None, **kwargs):
        if not alpha and not span:
            span = len(s)
        label, value = ("alpha", alpha) if alpha else ("span", span)
        super().__init__(s, alpha=alpha, span=span, indicator_name=f"TEMA ({label}={value})", **kwargs)
        self.alpha = alpha
        self.span = span

    def apply_indicator(self, s: pd.Series, alpha: float = None,
                        span: float = None):
        ema = EMA(s, alpha=alpha, span=span, validate=False)
        return (3 * ema) - (3 * EMA(ema, alpha, span, validate=False)) + \
               EMA(EMA(ema, alpha, span, validate=False), alpha, span, validate=False)


class TRIMA(_SeriesInSeriesOut):
    """Triangular moving average."""

    parameters = {"n": MA_TYPICAL_N}

    def __init__(self, s: pd.Series, n: int = 5, **kwargs):
        super().__init__(s, n=n, indicator_name=f"TRIMA (n={n})", **kwargs)
        self.n = n

    def apply_indicator(self, s: pd.Series, n: int = 5):
        sma = SMA(s, n=n, validate=False).dropna()
        return SMA(sma, n=n)


class KER(_SeriesInSeriesOut):
    """Kaufman Efficiency Ratio."""

    parameters = {"n": MA_TYPICAL_N}

    def __init__(self, s: pd.Series, n: int = 5, **kwargs):
        super().__init__(s, n=n, indicator_name=f"KER (n={n})", **kwargs)
        self.n = n

    def apply_indicator(self, s: pd.Series, n: int = 5):
        trend = s.diff(n).abs()
        volatility = s.diff().abs().rolling(window=n).sum()
        return trend / volatility


class KAMA(_SeriesInSeriesOut):
    """Kaufman adaptive moving average.
    See: https://school.stockcharts.com/doku.php?id=technical_indicators:kaufman_s_adaptive_moving_average
    """

    # parameters = {"n": MA_TYPICAL_N}  # TODO

    def __init__(self, s: pd.Series, er: int = 10,
                 ema_fast: int = 2, ema_slow: int = 30,
                 n: int = 20, **kwargs):
        name = f"KAMA (er={er}, ema_fast={ema_fast}, ema_slow={ema_slow}, n={n})"
        super().__init__(s, er=er, ema_fast=ema_fast, ema_slow=ema_slow, n=n, indicator_name=name, **kwargs)
        self.er = er
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.n = n

    def apply_indicator(self, s: pd.Series, er: int = 10,
                        ema_fast: int = 2, ema_slow: int = 30,
                        n: int = 20):
        """
        Args:
            s: price data.
            er: Kaufman Efficiency Ratio window.
            ema_fast: number of periods for fast EMA constant.
            ema_slow: number of periods for slow EMA constant.
            n: number of periods for SMA calculation for first KAMA value.
        """

        assert n >= er, f"`n` must be greater/equal to `er`."
        s_name = s.name
        calc_df = pd.DataFrame(s)
        calc_df["e_ratio"] = KER(s, n=er, validate=False)
        fast_c, slow_c = 2/(ema_fast+1), 2/(ema_slow+1)
        calc_df["smoothing_constant"] = (calc_df["e_ratio"] * (fast_c-slow_c) + slow_c) ** 2
        sma = SMA(s, n=n, validate=False).dropna()
        calc_df = calc_df.loc[sma.index[1:]]
        kama = list()
        kama.append(sma.iloc[0])  # First value is sma.
        for price, sc in zip(calc_df[s_name], calc_df["smoothing_constant"]):
            prior_kama = kama[-1]
            kama.append(prior_kama + sc * (price - prior_kama))
        return pd.Series(kama[1:], index=calc_df.index)


class MACD(_SeriesInDfOut):
    """Moving average convergence-divergence. See:
        https://www.investopedia.com/articles/forex/05/macddiverge.asp
    """

    # parameters = {"n": MA_TYPICAL_N} # TODO

    def __init__(self, s: pd.Series, p_fast: int = 12, p_slow: int = 26,
                 signal: int = 9, **kwargs):
        super().__init__(s, p_fast=p_fast, p_slow=p_slow, signal=signal, **kwargs)
        self.p_fast = p_fast
        self.p_slow = p_slow
        self.signal = signal

    def apply_indicator(self, s: pd.Series, p_fast: int = 12, p_slow: int = 26,
                        signal: int = 9):
        ema_fast = EMA(s, span=p_fast, validate=False)
        ema_slow = EMA(s, span=p_slow, validate=False)
        macd_name = f"{s.name} - MACD (p_fast={p_fast}, p_slow={p_slow})"
        macd = (ema_fast - ema_slow).rename(macd_name)
        signal_name = f"{s.name} - MACD_signal (p_fast={p_fast}, p_slow={p_slow}, signal={signal})"
        macd_signal = EMA(macd, span=signal, validate=False).rename(signal_name)
        return pd.concat([macd, macd_signal], axis=1)


class RSI(_SeriesInSeriesOut):
    """Relative strength index; see:
        https://www.investopedia.com/terms/r/rsi.asp
    """

    parameters = {"n": MA_TYPICAL_N}

    def __init__(self, s: pd.Series, n: int = 14, **kwargs):
        super().__init__(s, n=n, indicator_name=f"RSI (n={n})", **kwargs)
        self.n = n

    def apply_indicator(self, s: pd.Series, n: int = 14):
        up, down = s.diff(1), s.diff(1)
        up.loc[(up < 0)], down.loc[(down > 0)] = 0, 0
        up_ewm = EMA(up, span=n, validate=False)
        down_ewm = EMA(down.abs(), span=n, validate=False)
        rsi = up_ewm / (up_ewm + down_ewm)
        return rsi
