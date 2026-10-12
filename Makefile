# Run every project's tests from its own folder. Each project has its own requirements.txt.
PROJECTS := google-fiber-fcr nfl-closing-line markets-vs-polls olist-ecommerce steam-pulse
.PHONY: test $(PROJECTS) operational-risk-briefing
test: $(PROJECTS) operational-risk-briefing
$(PROJECTS):
	cd projects/$@ && python -m pytest -q
operational-risk-briefing:
	cd projects/$@ && Rscript tests/test_leakage.R
