PROM_IMAGE := prom/prometheus:v2.54.1
AM_IMAGE   := prom/alertmanager:v0.27.0

.PHONY: up down clean ps logs validate test-rules dashboards reload \
        demo-errors demo-latency demo-reset demo-cpu demo-cpu-stop demo-outage demo-recover alerts

up:            ## Build and start the whole stack
	docker compose up -d --build
	@echo "\nGrafana       http://localhost:3000  (admin / admin)"
	@echo "Prometheus    http://localhost:9090"
	@echo "Alertmanager  http://localhost:9093"
	@echo "Demo app      http://localhost:8000\n"

down:          ## Stop containers (keep data)
	docker compose down

clean:         ## Stop containers and delete all data volumes
	docker compose down -v

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=50

validate:      ## Lint Prometheus config/rules and Alertmanager config
	docker run --rm --entrypoint promtool -v $(CURDIR)/prometheus:/etc/prometheus $(PROM_IMAGE) check config /etc/prometheus/prometheus.yml
	docker run --rm --entrypoint amtool -v $(CURDIR)/alertmanager:/etc/alertmanager $(AM_IMAGE) check-config /etc/alertmanager/alertmanager.yml

test-rules:    ## Unit-test the alerting rules
	docker run --rm --entrypoint promtool -v $(CURDIR)/prometheus:/etc/prometheus $(PROM_IMAGE) test rules /etc/prometheus/tests/alerts_test.yml

dashboards:    ## Regenerate Grafana dashboard JSON from scripts/generate_dashboards.py
	python3 scripts/generate_dashboards.py

reload:        ## Hot-reload Prometheus config and rules
	curl -sf -X POST http://localhost:9090/-/reload && echo "reloaded"

# ---- Failure injection: watch alerts go pending -> firing -> resolved -------
demo-errors:   ## 40% of requests fail  -> ServiceHighErrorRate, ErrorBudgetFastBurn
	curl -s "http://localhost:8000/chaos?error_rate=0.4"; echo

demo-latency:  ## +1.2s latency        -> ServiceHighLatencyP95, CriticalLatencyP99
	curl -s "http://localhost:8000/chaos?latency=1.2"; echo

demo-reset:    ## Back to healthy
	curl -s "http://localhost:8000/chaos/reset"; echo

demo-cpu:      ## Burn all CPU cores   -> HostHighCpu, HostCriticalCpu (after 5m)
	docker run -d --rm --name cpu-stress alpine sh -c 'for i in 1 2 3 4 5 6 7 8; do (while :; do :; done) & done; wait'

demo-cpu-stop:
	-docker stop cpu-stress

demo-outage:   ## Kill the app             -> InstanceDown (critical)
	docker compose stop demo-app

demo-recover:
	docker compose start demo-app

alerts:        ## Show notifications received by the webhook sink
	docker compose logs -f --tail=30 webhook-logger
