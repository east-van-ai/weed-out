"""The two kinds of failure a run itself can raise. Imports nothing."""


class ReadinessError(Exception):
    """Something the run needed was missing, found before the first write."""


class RuntimeFailure(Exception):
    """The run stopped partway, after the first write had already happened."""
