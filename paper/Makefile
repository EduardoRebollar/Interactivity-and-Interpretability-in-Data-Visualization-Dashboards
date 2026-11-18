# The comps paper. Adapted from the Oxy CS comps paper template's Makefile
# (https://github.com/justinnhli/oxy-cs-comps-paper-template).
#
# numbers.tex, tables/ and figures/ are generated from the study data, which is not in the
# repository, so they are committed and this Makefile does not rebuild them. To regenerate them,
# from the repository root:
#   uv run python scripts/paper_numbers.py
#   uv run python scripts/paper_figures.py

LATEX = latexmk -pdf --shell-escape

default: main.pdf

main.pdf: Makefile main.tex numbers.tex references.bib oxycomps.sty $(wildcard tables/*.tex) \
		$(wildcard figures/*.tex) figures/versions.pdf
	$(LATEX) main

clean:
	latexmk -C main
	rm -f *-blx.bib *.bbl *.run.xml
