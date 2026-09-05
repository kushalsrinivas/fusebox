.PHONY: api web worker test seed index-demo eval-code eval-investigations eval-actions load-test
api:
	cd apps/api && uvicorn app.main:app --reload --port 8000
web:
	cd apps/web && npm run dev
test:
	cd apps/api && pytest -q; cd ../../workers/ingest && pytest -q; cd ../agent && pytest -q; cd ../indexer && pytest -q; cd ../correlation && pytest -q; cd ../graph && pytest -q; cd ../action && pytest -q; cd ../verify && pytest -q; cd ../insights && pytest -q
agent:
	cd workers/agent && python -c "from agent.service import run_investigation; import json; print(json.dumps(run_investigation('00000000-0000-0000-0000-000000000001','demo','checkout crash when tapping pay',42), indent=2, default=str))"
seed:
	cd workers/ingest && python scripts/seed_feedback.py --count 200
index-demo:
	cd workers/indexer && python -c "from pil_indexer.sync import sync_repo; print(sync_repo('.pil-index','00000000-0000-0000-0000-000000000001','tests/fixtures/demo-repo','demo'))"
eval-code:
	cd workers/indexer && python evals/run_evals.py --min-pass 16
eval-investigations:
	cd workers/agent && python evals/run_investigation_evals.py
eval-actions:
	cd workers/action && python evals/run_action_evals.py
load-test:
	python scripts/load_test.py --tenants 5 --events 40
