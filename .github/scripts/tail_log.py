''' Lê o log do build na entrada e imprime o trecho que explica a falha como anotação de erro do
GitHub Actions (anotações são públicas e curtas; o log completo exige login).
Ignora o despejo de variáveis de ambiente ("# ...") que o Buildozer imprime no fim. '''
import re
import sys

ANSI = re.compile(r"\x1b\[[0-9;]*m")
lines = [ANSI.sub("", l)[:300] for l in sys.stdin.read().replace("\r", "").split("\n")]
useful = [l for l in lines if not l.startswith("#")]
text = "\n".join(useful[-70:]).replace("%", "%25").replace("\n", "%0A")
print("::error title=Log do Buildozer antes do erro::" + text)
