from Backend.CodeGenerator import CodeGenerator


class UrlShortener:
    def __init__(self, code_generator: CodeGenerator):
        self._code_generator = code_generator

        # stores a mapping of short code to original URL [llm:_code_to_url]
        self._code_to_url = {}

        self._url_to_code = {}

    # creates a unique short code for a given long URL, using CodeGenerator to generate the code [llm:create_short_code]
    def create_short_code(self, url: str) -> str:
        existing = self._url_to_code.get(url)
        if existing is not None:
            return existing

        code = self._code_generator.generate()
        while code in self._code_to_url:
            code = self._code_generator.generate()

        self._code_to_url[code] = url
        self._url_to_code[url] = code
        return code

    # looks up the original URL for a given short code [llm:get_url]
    def get_url(self, code: str):
        return self._code_to_url.get(code)
