"""M20 bootable runtime package.

The runtime layer composes the existing provider-neutral market-data stack.
M20 is deliberately shadow-only: it may consume real market data, but it
contains no live broker-order submission path.
"""
