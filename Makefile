default: run

run:
	@python main.py

test:
	@pylint --reports=n --msg-template="{path}:{line}: {msg_id} {symbol}, {obj} {msg}" /Users/jmei/Projects/diff-privacy/main.py
