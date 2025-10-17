# SubSim helper targets

.PHONY: venv run test guard clean assets headless

venv:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e .

test:
	.venv/bin/python -m pytest -q

assets:
	.venv/bin/python -c "from subsim.assets import ensure_assets; ensure_assets()"

headless:
	SDL_AUDIODRIVER=dummy .venv/bin/python -m subsim --headless --duration 3

guard:
	python validate.py

run:
	.venv/bin/python -m subsim

clean:
	rm -rf .venv/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +
