# SubSim helper targets

.PHONY: venv run test eval lint guard clean assets headless renderer-preview

venv:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e .

test:
	.venv/bin/python -m pytest -q

eval:
	.venv/bin/python evals/runner.py --check

lint:
	.venv/bin/python -m compileall -q subsim tests core evals

assets:
	.venv/bin/python -c "from subsim.assets import ensure_assets; ensure_assets()"

headless:
	SDL_AUDIODRIVER=dummy .venv/bin/python -m subsim --headless --duration 3

renderer-preview:
	python3 tools/renderer_v1_pipeline.py run-all

guard:
	python validate.py

run:
	.venv/bin/python -m subsim

clean:
	rm -rf .venv/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +
