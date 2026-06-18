"""Media center core: source providers, local library, metadata enrichment.

This package generalises QPlayer beyond Xtream IPTV into a multi-source media
centre. A *source* exposes categories/items and resolves a playable URL; the
library DB tracks cross-source state (resume positions, favourites) and caches
scanned local media + fetched metadata.
"""
