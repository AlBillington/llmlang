from Backend.CodeGenerator import CodeGenerator


class UrlShortener:
    # code_generator/_code_to_url already documented at their point of use; _url_to_code is a private lookup optimization [llm-exempt]
    def __init__(self, code_generator: CodeGenerator):
        self._code_generator = code_generator

        # stores a mapping of short code to original URL [llm:Backend.UrlShortener._code_to_url]
        self._code_to_url = {}

        self._url_to_code = {}

    # creates a unique short code for a given long URL, using CodeGenerator to generate the code [llm:Backend.UrlShortener.create_short_code]
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

    # looks up the original URL for a given short code [llm:Backend.UrlShortener.get_url]
    def get_url(self, code: str):
        return self._code_to_url.get(code)
