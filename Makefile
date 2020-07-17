ci:
	python3 -m unittest discover -v -s tests

test:
	LOCAL=1 python3 -m unittest discover -v -s tests