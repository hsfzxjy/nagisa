.PHONY: test ci
ci:
	python3 -m unittest discover -v -s tests -t .

test:
	LOCAL=1 python3 -m unittest discover -v -s tests -t .