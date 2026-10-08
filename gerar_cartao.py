
import json
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from layout_cartao import (
    ALTURA,
    LARGURA,
    MAX_OBJETIVAS,
    desenhar_marcadores,
    desenhar_questoes,
)

BASE = Path(__file__).resolve().parent
ARQUIVO_JSON = BASE / "avaliacao.json"
PASTA_SAIDA = BASE / "cartoes"

VERSAO_LAYOUT = "0.3"


def carregar_avaliacao():
    if not ARQUIVO_JSON.is_file():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {ARQUIVO_JSON}"
        )

    with ARQUIVO_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def validar_avaliacao(prova):
    campos = [
        "id", "titulo", "disciplina",
        "turma", "data", "aluno", "questoes"
    ]

    for campo in campos:
        if campo not in prova:
            raise ValueError(
                f"Campo obrigatório ausente: {campo}"
            )

    for campo in ("id", "nome"):
        if not str(prova["aluno"].get(campo, "")).strip():
            raise ValueError(
                f"Campo do aluno ausente: {campo}"
            )

    for campo in ("id", "titulo", "disciplina", "turma"):
        if not str(prova[campo]).strip():
            raise ValueError(
                f"Campo inválido: {campo}"
            )

    questoes = prova["questoes"]

    if not isinstance(questoes, list) or not questoes:
        raise ValueError("A avaliação não possui questões.")

    numeros = []
    objetivas = []
    discursivas = []

    for q in questoes:
        numero = q.get("numero")
        tipo = q.get("tipo")
        pontos = q.get("pontos")

        if type(numero) is not int or numero <= 0:
            raise ValueError("Número de questão inválido.")

        if (
            type(pontos) not in (int, float)
            or not 0 < pontos < float("inf")
        ):
            raise ValueError(
                f"Pontuação inválida na questão {numero}."
            )

        numeros.append(numero)

        if tipo == "objetiva":
            alternativas = q.get("alternativas")
            gabarito = q.get("gabarito")

            if (
                not isinstance(alternativas, list)
                or not 2 <= len(alternativas) <= 5
            ):
                raise ValueError(
                    f"Alternativas inválidas na questão {numero}."
                )

            if (
                any(a not in "ABCDE" for a in alternativas)
                or len(set(alternativas)) != len(alternativas)
                or any(type(a) is not str or len(a) != 1
                       for a in alternativas)
            ):
                raise ValueError(
                    f"Alternativas inválidas na questão {numero}."
                )

            if gabarito not in alternativas:
                raise ValueError(
                    f"Gabarito inválido na questão {numero}."
                )

            objetivas.append(q)

        elif tipo == "discursiva":
            discursivas.append(q)

        else:
            raise ValueError(
                f"Tipo inválido na questão {numero}: {tipo}"
            )

    if len(numeros) != len(set(numeros)):
        raise ValueError("Existem questões repetidas.")

    if len(objetivas) > MAX_OBJETIVAS:
        raise ValueError(
            f"Limite de {MAX_OBJETIVAS} objetivas excedido."
        )

    # Mantém a numeração original em ordem crescente.
    objetivas.sort(key=lambda q: q["numero"])
    discursivas.sort(key=lambda q: q["numero"])

    return objetivas, discursivas


def nome_seguro(valor):
    return re.sub(
        r"[^A-Za-z0-9_-]",
        "_",
        str(valor)
    )


def desenhar_texto_limitado(pdf, texto, x, y, max_largura):
    """Reduz a fonte para caber na largura disponível."""
    texto = str(texto)

    for tamanho in (10, 9, 8, 7):
        pdf.setFont("Helvetica", tamanho)

        if pdf.stringWidth(texto, "Helvetica", tamanho) <= max_largura:
            pdf.drawString(x, y, texto)
            return

    raise ValueError(
        f"Texto muito longo para o cartão: {texto}"
    )


def desenhar_cabecalho(pdf, prova, cartao_id):
    pdf.setFont("Helvetica-Bold", 14)

    titulo = str(prova["titulo"])

    if pdf.stringWidth(titulo, "Helvetica-Bold", 14) > 380:
        raise ValueError(
            "Título muito longo. Use um título mais curto."
        )

    pdf.drawString(55, ALTURA - 78, titulo)

    desenhar_texto_limitado(
        pdf,
        prova["disciplina"],
        55, ALTURA - 102, 380
    )

    desenhar_texto_limitado(
        pdf,
        f'Aluno: {prova["aluno"]["nome"]}',
        55, ALTURA - 125, 380
    )

    desenhar_texto_limitado(
        pdf,
        f'Turma: {prova["turma"]}',
        55, ALTURA - 145, 380
    )

    desenhar_texto_limitado(
        pdf,
        f'Data: {prova["data"]}',
        55, ALTURA - 165, 380
    )

    # QR Code contém somente o ID do cartão.
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )
    qr.add_data(cartao_id)
    qr.make(fit=True)

    imagem = qr.make_image(
        fill_color="black",
        back_color="white"
    ).convert("RGB")

    pdf.drawImage(
        ImageReader(imagem),
        LARGURA - 145,
        ALTURA - 170,
        width=90,
        height=90
    )

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(
        55,
        ALTURA - 210,
        "QUESTÕES OBJETIVAS"
    )

    pdf.setLineWidth(0.5)
    pdf.line(
        55,
        ALTURA - 220,
        LARGURA - 55,
        ALTURA - 220
    )


def desenhar_rodape(pdf, objetivas, discursivas):
    total_obj = sum(q["pontos"] for q in objetivas)
    total_disc = sum(q["pontos"] for q in discursivas)
    total = total_obj + total_disc

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(
        55, 140,
        "QUESTÕES DISCURSIVAS"
    )

    pdf.setFont("Helvetica", 9)

    if discursivas:
        numeros = ", ".join(
            str(q["numero"]) for q in discursivas
        )
        texto = (
            f"Questões: {numeros} "
            "- correção manual"
        )
    else:
        texto = "Não há questões discursivas."

    desenhar_texto_limitado(
        pdf, texto, 55, 121, LARGURA - 110
    )

    pdf.line(55, 108, LARGURA - 55, 108)

    pdf.setFont("Helvetica", 9)
    pdf.drawString(
        55, 90,
        f"Objetivas: {total_obj:g} pontos"
    )
    pdf.drawString(
        225, 90,
        f"Discursivas: {total_disc:g} pontos"
    )
    pdf.drawString(
        410, 90,
        f"Total: {total:g}"
    )

    pdf.drawString(
        55, 68,
        "Nota final: __________"
    )


def gerar_cartao():
    prova = carregar_avaliacao()
    objetivas, discursivas = validar_avaliacao(prova)

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    chave = f'{prova["id"]}:{prova["aluno"]["id"]}'
    cartao_id = str(uuid5(NAMESPACE_URL, chave))

    nome = (
        f'{nome_seguro(prova["id"])}_'
        f'{nome_seguro(prova["aluno"]["id"])}'
    )

    caminho_pdf = PASTA_SAIDA / f"{nome}.pdf"
    caminho_mapa = PASTA_SAIDA / f"{nome}.json"

    pdf = canvas.Canvas(
        str(caminho_pdf),
        pagesize=A4
    )

    pdf.setTitle("Cartão-resposta")
    pdf.setAuthor("Sistema de Avaliações")

    mapa_marcadores = desenhar_marcadores(pdf)

    desenhar_cabecalho(
        pdf, prova, cartao_id
    )

    mapa_bolhas = desenhar_questoes(
        pdf, objetivas
    )

    desenhar_rodape(
        pdf, objetivas, discursivas
    )

    pdf.save()

    # Dados para o futuro leitor óptico.
    # Não inclui o gabarito.
    registro = {
        "versao_layout": VERSAO_LAYOUT,
        "cartao_id": cartao_id,
        "avaliacao_id": prova["id"],
        "aluno_id": prova["aluno"]["id"],
        "aluno_nome": prova["aluno"]["nome"],
        "turma": prova["turma"],
        "pagina": {
            "largura": round(LARGURA, 2),
            "altura": round(ALTURA, 2),
            "unidade": "pontos_pdf",
            "origem": "inferior_esquerda"
        },
        "marcadores": mapa_marcadores,
        "bolhas": mapa_bolhas,
        "questoes_discursivas": [
            {
                "numero": q["numero"],
                "pontos": q["pontos"]
            }
            for q in discursivas
        ]
    }

    with caminho_mapa.open(
        "w", encoding="utf-8"
    ) as arquivo:
        json.dump(
            registro,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    total = sum(
        q["pontos"] for q in prova["questoes"]
    )

    print("\nCartão gerado com sucesso!")
    print(f"PDF: {caminho_pdf}")
    print(f"Mapa: {caminho_mapa}")
    print(f"ID: {cartao_id}")
    print(f"Objetivas: {len(objetivas)}")
    print(f"Discursivas: {len(discursivas)}")
    print(f"Pontuação total: {total:g}")


if __name__ == "__main__":
    gerar_cartao()
