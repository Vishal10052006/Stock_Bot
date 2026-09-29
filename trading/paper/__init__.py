"""Paper trading package.

Submodules are intentionally imported directly to keep package initialization
free of eager cross-package imports. This prevents import cycles between
backtesting, paper lifecycle, and experiment modules.
"""
