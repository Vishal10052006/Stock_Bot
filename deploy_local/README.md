# STOCK_BOT local deployment A-J

Local-first runtime for heavy CPU/GPU work. GitHub remains source control and CI. Live broker execution remains locked.

A reproducible environment
B host preflight
C CPU/GPU detection
D local secrets
E supervision
F real-market virtual paper
G local read-only dashboard
H persistence/health
I maintenance
J fail-closed safety

Setup:

    bash deploy_local/install.sh
    cp deploy_local/.env.example .env
    chmod 600 .env
    bash deploy_local/preflight.sh
    python deploy_local/doctor.py --require-market

Run paper mode:

    bash deploy_local/start.sh paper

Run shadow mode:

    bash deploy_local/start.sh shadow

Run dashboard:

    bash deploy_local/start_dashboard.sh
