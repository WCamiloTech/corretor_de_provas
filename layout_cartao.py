
from reportlab.lib.pagesizes import A4

LARGURA, ALTURA = A4

# Coordenadas em pontos PDF (origem no canto inferior esquerdo).
COLUNAS_X = (55, 310)
INICIO_Y = ALTURA - 245
ESPACAMENTO_Y = 25
QUESTOES_POR_COLUNA = 16
MAX_OBJETIVAS = 32

RAIO_BOLHA = 7
ESPACAMENTO_X = 35
DESLOCAMENTO_X = 43

# Quatro quadrados de referência para alinhamento.
TAMANHO_MARCADOR = 18
MARGEM_MARCADOR = 25

MARCADORES = {
    "inferior_esquerdo": (
        MARGEM_MARCADOR,
        MARGEM_MARCADOR
    ),
    "inferior_direito": (
        LARGURA - MARGEM_MARCADOR - TAMANHO_MARCADOR,
        MARGEM_MARCADOR
    ),
    "superior_esquerdo": (
        MARGEM_MARCADOR,
        ALTURA - MARGEM_MARCADOR - TAMANHO_MARCADOR
    ),
    "superior_direito": (
        LARGURA - MARGEM_MARCADOR - TAMANHO_MARCADOR,
        ALTURA - MARGEM_MARCADOR - TAMANHO_MARCADOR
    )
}


def desenhar_marcadores(pdf):
    """Desenha os quatro marcadores de alinhamento."""
    pdf.setFillColorRGB(0, 0, 0)

    mapa = {}

    for nome, (x, y) in MARCADORES.items():
        pdf.rect(
            x, y,
            TAMANHO_MARCADOR,
            TAMANHO_MARCADOR,
            stroke=0,
            fill=1
        )

        mapa[nome] = {
            "x": round(x, 2),
            "y": round(y, 2),
            "largura": TAMANHO_MARCADOR,
            "altura": TAMANHO_MARCADOR
        }

    return mapa


def desenhar_questoes(pdf, questoes):
    """
    Desenha até 32 questões objetivas em duas colunas.

    Retorna as coordenadas das bolhas em pontos PDF.
    """
    if len(questoes) > MAX_OBJETIVAS:
        raise ValueError(
            f"O layout suporta até {MAX_OBJETIVAS} "
            "questões objetivas."
        )

    mapa = {}

    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setLineWidth(1)

    for indice, questao in enumerate(questoes):
        coluna = indice // QUESTOES_POR_COLUNA
        linha = indice % QUESTOES_POR_COLUNA

        x_base = COLUNAS_X[coluna]
        y = INICIO_Y - linha * ESPACAMENTO_Y

        numero = questao["numero"]
        alternativas = questao["alternativas"]

        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(
            x_base,
            y - 3,
            f"{numero:02d}"
        )

        mapa[str(numero)] = {}

        for indice_alt, letra in enumerate(alternativas):
            x = (
                x_base
                + DESLOCAMENTO_X
                + indice_alt * ESPACAMENTO_X
            )

            pdf.circle(
                x, y,
                RAIO_BOLHA,
                stroke=1,
                fill=0
            )

            pdf.setFont("Helvetica", 7)
            pdf.drawCentredString(
                x,
                y + 11,
                letra
            )

            mapa[str(numero)][letra] = {
                "x": round(x, 2),
                "y": round(y, 2),
                "raio": RAIO_BOLHA
            }

    return mapa
