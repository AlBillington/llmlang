import random
import string

CODE_LENGTH = 6
CODE_ALPHABET = string.ascii_letters + string.digits


class CodeGenerator:
    # generates a random 6-character alphanumeric code [llm:generate]
    def generate(self) -> str:
        return "".join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))
