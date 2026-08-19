LLM_FILES := compiler/compiler.llm examples/shortener/shortener.llm examples/notes/notes.llm

.PHONY: lint

lint:
	@status=0; \
	for f in $(LLM_FILES); do \
		echo "checking $$f"; \
		python compiler/build.py $$f --check || status=1; \
	done; \
	exit $$status
