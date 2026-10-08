
from pathlib import Path
from uuid import uuid4

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ARQUIVO = Path("cartao_resposta.pdf")

prova = {
    "titulo": "Avaliação - MMC",
    "disciplina": "Montagem e Manutenção",
    "aluno": "João da Silva",
    "turma": "MMC2",
    "questoes": [
        {"numero": 1, "tipo": "objetiva"},
        {"numero": 2, "tipo": "objetiva"},
        {"numero": 3, "tipo": "discursiva"},
        {"numero": 4, "tipo": "objetiva"},
        {"numero": 5, "tipo": "objetiva"},
        {"numero": 6, "tipo": "discursiva"},
    ],
}

identificador = str(uuid4())
largura, altura = A4

pdf = canvas.Canvas(str(ARQUIVO), pagesize=A4)

# Identificação
pdf.setFont("Helvetica-Bold", 15)
pdf.drawString(45, altura - 65, prova["titulo"])

pdf.setFont("Helvetica", 10)
pdf.drawString(45, altura - 90, prova["disciplina"])
pdf.drawString(45, altura - 115, f'Aluno: {prova["aluno"]}')
pdf.drawString(45, altura - 135, f'Turma: {prova["turma"]}')

# QR Code
imagem_qr = qrcode.make(identificador)
caminho_qr = Path("qrcode_temp.png")
imagem_qr.save(caminho_qr)

pdf.drawImage(
    str(caminho_qr),
    largura - 135,
    altura - 155,
    width=85,
    height=85
)

# Questões objetivas
pdf.setFont("Helvetica-Bold", 11)
pdf.drawString(45, altura - 195, "QUESTÕES OBJETIVAS")

y = altura - 225

for questao in prova["questoes"]:
    if questao["tipo"] != "objetiva":
        continue

    numero = questao["numero"]
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y - 3, f"{numero:02d}")

    for indice, alternativa in enumerate("ABCDE"):
        x = 100 + indice * 75
        pdf.circle(x, y, 8, stroke=1, fill=0)
        pdf.drawString(x + 13, y - 3, alternativa)

    y -= 32

# Questões discursivas
y -= 25
pdf.setFont("Helvetica-Bold", 11)
pdf.drawString(45, y, "QUESTÕES DISCURSIVAS")

y -= 22
pdf.setFont("Helvetica", 10)

for questao in prova["questoes"]:
    if questao["tipo"] == "discursiva":
        pdf.drawString(
            50, y,
            f'Questão {questao["numero"]:02d} - Correção manual'
        )
        y -= 20

# Marcadores de referência
pdf.setFillColorRGB(0, 0, 0)
for x, marcador_y in [
    (25, 25),
    (largura - 45, 25),
    (25, altura - 45),
    (largura - 45, altura - 45),
]:
    pdf.rect(x, marcador_y, 20, 20, fill=1, stroke=0)

pdf.save()
caminho_qr.unlink(missing_ok=True)

print(f"Cartão gerado: {ARQUIVO.resolve()}")
print(f"Identificador: {identificador}")
