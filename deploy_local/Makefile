install:
	bash deploy_local/install.sh
preflight:
	bash deploy_local/preflight.sh
doctor:
	python deploy_local/doctor.py --require-market
env:
	python deploy_local/env_check.py
runtime:
	python deploy_local/runtime.py
gpu:
	python deploy_local/gpu_test.py
dashboard:
	bash deploy_local/start_dashboard.sh
stop:
	bash deploy_local/stop.sh
