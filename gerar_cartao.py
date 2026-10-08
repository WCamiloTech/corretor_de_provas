
import json
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

BASE = Path(__file__).resolve().parent
ARQUIVO_JSON = BASE / "avaliacao.json"
PASTA_SAIDA = BASE / "cartoes"
PASTA_SAIDA.mkdir(exist_ok=True)

with ARQUIVO_JSON.open("r", encoding="utf-8") as f:
    prova = json.load(f)

questoes = prova["questoes"]
objetivas = [q for q in questoes if q["tipo"] == "objetiva"]
discursivas = [q for q in questoes if q["tipo"] == "discursiva"]

# Validações básicas
numeros = [q["numero"] for q in questoes]
if len(numeros) != len(set(numeros)):
    raise ValueError("Existem números de questões repetidos.")

for q in questoes:
    if q["pontos"] <= 0:
        raise ValueError("A pontuação deve ser positiva.")

    if q["tipo"] == "objetiva":
        alternativas = q["alternativas"]
        if q["gabarito"] not in alternativas:
            raise ValueError(
                f'Gabarito inválido na questão {q["numero"]}'
            )
    elif q["tipo"] != "discursiva":
        raise ValueError("Tipo de questão desconhecido.")

# Identificador estável para este aluno e esta avaliação
chave = f'{prova["id"]}:{prova["aluno"]["id"]}'
cartao_id = str(uuid5(NAMESPACE_URL, chave))

nome_arquivo = (
    f'{prova["id"]}_{prova["aluno"]["id"]}.pdf'
)
saida = PASTA_SAIDA / nome_arquivo

largura, altura = A4
pdf = canvas.Canvas(str(saida), pagesize=A4)

# Marcadores de referência
for x, y in [
    (25, 25),
    (largura - 45, 25),
    (25, altura - 45),
    (largura - 45, altura - 45)
]:
    pdf.rect(x, y, 20, 20, stroke=0, fill=1)

# Cabeçalho
pdf.setFont("Helvetica-Bold", 14)
pdf.drawString(50, altura - 75, prova["titulo"])

pdf.setFont("Helvetica", 10)
pdf.drawString(
    50, altura - 95, prova["disciplina"]
)
pdf.drawString(
    50, altura - 115,
    f'Aluno: {prova["aluno"]["nome"]}'
)
pdf.drawString(
    50, altura - 135,
    f'Turma: {prova["turma"]}'
)
pdf.drawString(
    50, altura - 155,
    f'Data: {prova["data"]}'
)

# QR Code - somente identificador
qr = qrcode.make(cartao_id)
pdf.drawImage(
    ImageReader(qr.get_image().convert("RGB")),
    largura - 145,
    altura - 165,
    width=90,
    height=90
)

# Área de respostas
pdf.setFont("Helvetica-Bold", 11)
pdf.drawString(50, altura - 205, "QUESTÕES OBJETIVAS")

y = altura - 240

for q in objetivas:
    if y < 135:
        raise ValueError(
            "Quantidade de questões excede o layout atual."
        )

    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y - 3, f'{q["numero"]:02d}')

    for indice, alternativa in enumerate(q["alternativas"]):
        if indice >= 5:
            raise ValueError(
                "Este layout suporta até 5 alternativas."
            )

        x = 100 + indice * 75
        pdf.circle(x, y, 8, stroke=1, fill=0)
        pdf.drawString(x + 13, y - 3, alternativa)

    y -= 32

# Área discursiva
y -= 20
if discursivas:
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "QUESTÕES DISCURSIVAS")
    y -= 20

    pdf.setFont("Helvetica", 10)
    for q in discursivas:
        if y < 95:
            raise ValueError(
                "Sem espaço para listar as discursivas."
            )
        pdf.drawString(
            50, y,
            f'Questão {q["numero"]:02d} - '
            f'{q["pontos"]:g} pontos - Correção manual'
        )
        y -= 18

pdf.setFont("Helvetica", 9)
total = sum(q["pontos"] for q in questoes)
pdf.drawString(
    50, 75,
    f'Pontuação total: {total:g} pontos'
)

pdf.save()

print("Cartão gerado com sucesso!")
print(f"Arquivo: {saida}")
print(f"ID do cartão: {cartao_id}")
print(f"Objetivas: {len(objetivas)}")
print(f"Discursivas: {len(discursivas)}")
print(f"Pontuação total: {total:g}")
