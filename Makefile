# Run every project's tests from its own folder. Each project has its own requirements.txt.
PROJECTS := aircraft-readiness electricity-price-tracker google-fiber-fcr markets-vs-polls nfl-closing-line olist-ecommerce rural-hospital-warning-signs steam-pulse
.PHONY: test test-r $(PROJECTS)
test: $(PROJECTS) test-r
$(PROJECTS):
	cd projects/$@/code && python -m pytest -q
test-r:
	cd projects/diabetes-care-gaps/code && Rscript -e 'testthat::test_dir("tests", stop_on_failure = TRUE)'
