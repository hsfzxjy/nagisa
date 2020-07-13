test:
	python3 -m unittest discover -v -s tests

local_test:
	LOCAL=1 python3 -m unittest discover -v -s tests