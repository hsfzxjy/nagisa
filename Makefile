.PHONY: test ci
ci:
	python3 -m pip install torch==${TORCH_VERSION} pytorch-ignite
	python3 -m unittest discover -v -s tests -t .

test:
	LOCAL=1 python3 -m unittest discover -v -s tests -t .