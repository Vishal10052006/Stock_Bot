# STOCK_BOT Local Security

Make the repository private before storing proprietary source/assets. Keep broker credentials in the local `.env` only. Keep datasets, model binaries, caches, runtime state and logs out of Git. Protect `main` with required pull-request reviews and passing CI. A private repository prevents new anonymous clones but cannot recall copies already downloaded; remove unwanted collaborators and rotate exposed credentials.
