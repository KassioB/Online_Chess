''' Lê o log do build na entrada e imprime o final como uma anotação de erro do GitHub Actions
(anotações são públicas e curtas; o log completo exige login). '''
import sys

lines = sys.stdin.read().replace("\r", "").split("\n")[-60:]
text = "\n".join(lines).replace("%", "%25").replace("\n", "%0A")
print("::error title=Fim do log do Buildozer::" + text)
