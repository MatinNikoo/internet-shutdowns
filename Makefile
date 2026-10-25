# make all       every result, figure, report card, the released data and the papers (a few minutes)
# make sims      planted shutdown simulations (about 25 minutes, results/simulations.json)
# make data      download everything again (needs network, about 25 minutes)
# make test      fast tests

PY ?= python3
RUN = nice -n 10 $(PY)

.PHONY: all results figures cards release site paper test sims data clean

all: results figures site cards release paper test

results:
	$(RUN) analysis/run_events.py
	$(RUN) analysis/identification.py
	$(RUN) analysis/outcomes.py
	$(RUN) analysis/exposure.py
	$(RUN) analysis/heterogeneity.py
	$(RUN) analysis/stacked.py
	$(RUN) analysis/discover.py

figures:
	$(RUN) analysis/figures.py

site:
	$(RUN) analysis/export_site.py

cards:
	$(RUN) -m shutdowns cards --html

release:
	$(RUN) analysis/release.py

paper:
	$(RUN) analysis/paper_numbers.py
	cd paper && latexmk -pdf -interaction=nonstopmode -quiet paper.tex analysis_plan.tex
	cd memo && latexmk -pdf -interaction=nonstopmode -quiet memo.tex

test:
	$(PY) -m pytest -q

sims:
	$(RUN) analysis/simulations.py

data:
	$(RUN) analysis/fetch_data.py all

clean:
	cd paper && latexmk -c paper.tex analysis_plan.tex
	cd memo && latexmk -c memo.tex
