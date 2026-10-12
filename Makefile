# Run every project's tests from its own folder. Each project has its own requirements.txt.
PROJECTS := google-fiber-fcr nfl-closing-line markets-vs-polls olist-ecommerce steam-pulse
.PHONY: test $(PROJECTS)
test: $(PROJECTS)
$(PROJECTS):
	cd projects/$@/code && python -m pytest -q
