"""dtdash - Dynatrace Dashboard Builder.

Gera dashboards da plataforma Dynatrace (Grail / Dashboards app) a partir de uma
descricao em linguagem natural, apresenta uma previa para aprovacao e, apos
aprovado, cria o dashboard (e os segments associados) diretamente no tenant.

O pacote usa apenas a biblioteca padrao do Python (>= 3.9).
"""

from .version import __version__

__all__ = ["__version__"]
