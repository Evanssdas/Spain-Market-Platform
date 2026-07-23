.PHONY: install test collect train forecast grade

install:
	python -m pip install -r requirements.txt
	python -m pip install -e .

test:
	pytest

collect:
	python -m spain_power collect-history --start 2023-01-01

train:
	python -m spain_power train

forecast:
	python -m spain_power forecast

grade:
	python -m spain_power grade
