
import json
from pathlib import Path

import cv2
import numpy as np

BASE = Path(__file__).resolve().parent
FOTO = BASE / "fotos" / "teste_04.jpg"
MAPA = BASE / "cartoes" / "MMC2-2026-AV01_ALUNO-001.json"
SAIDA = BASE / "resultados"

ESCALA = 3
LIMIAR_MARCACAO = 0.35
LIMIAR_BRANCO = 0.15

SAIDA.mkdir(parents=True, exist_ok=True)


def carregar_dados():
    with MAPA.open("r", encoding="utf-8") as f:
        return json.load(f)


def localizar_marcadores(imagem):
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

    # Suavização e binarização adaptativa
    cinza = cv2.GaussianBlur(cinza, (5, 5), 0)

    binaria = cv2.adaptiveThreshold(
        cinza,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        10
    )

    contornos, _ = cv2.findContours(
        binaria,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    altura, largura = imagem.shape[:2]
    candidatos = []

    for contorno in contornos:
        area = cv2.contourArea(contorno)

        if area < 100 or area > largura * altura * 0.01:
            continue

        perimetro = cv2.arcLength(contorno, True)
        poligono = cv2.approxPolyDP(
            contorno, 0.04 * perimetro, True
        )

        if len(poligono) != 4:
            continue

        x, y, w, h = cv2.boundingRect(poligono)
        proporcao = w / float(h)

        if not 0.65 <= proporcao <= 1.35:
            continue

        preenchimento = area / float(w * h)

        if preenchimento < 0.65:
            continue

        centro = np.array(
            [x + w / 2, y + h / 2],
            dtype=np.float32
        )

        candidatos.append(centro)

    if len(candidatos) < 4:
        raise RuntimeError(
            "Não foram encontrados quatro marcadores."
        )

    # Procura candidatos próximos aos quatro cantos.
    referencias = [
        np.array([0, 0]),
        np.array([largura, 0]),
        np.array([largura, altura]),
        np.array([0, altura])
    ]

    selecionados = []
    usados = set()

    for referencia in referencias:
        distancias = [
            (
                np.linalg.norm(c - referencia),
                indice
            )
            for indice, c in enumerate(candidatos)
            if indice not in usados
        ]

        _, indice = min(distancias)
        selecionados.append(candidatos[indice])
        usados.add(indice)

    return np.float32(selecionados)


def alinhar_cartao(imagem, dados):
    pontos_origem = localizar_marcadores(imagem)

    largura_pdf = dados["pagina"]["largura"]
    altura_pdf = dados["pagina"]["altura"]

    largura_px = round(largura_pdf * ESCALA)
    altura_px = round(altura_pdf * ESCALA)

    marcadores = dados["marcadores"]

    ordem = [
        "superior_esquerdo",
        "superior_direito",
        "inferior_direito",
        "inferior_esquerdo"
    ]

    destino = []

    for nome in ordem:
        m = marcadores[nome]

        centro_x = m["x"] + m["largura"] / 2
        centro_y = m["y"] + m["altura"] / 2

        destino.append([
            centro_x * ESCALA,
            (altura_pdf - centro_y) * ESCALA
        ])

    pontos_destino = np.float32(destino)

    matriz = cv2.getPerspectiveTransform(
        pontos_origem, pontos_destino
    )

    alinhada = cv2.warpPerspective(
        imagem,
        matriz,
        (largura_px, altura_px),
        flags=cv2.INTER_LINEAR,
        borderValue=(255, 255, 255)
    )

    return alinhada


def analisar_bolha(cinza, x, y, raio):
    altura, largura = cinza.shape

    cx = round(x * ESCALA)
    cy = round(y * ESCALA)
    r = max(2, round(raio * ESCALA * 0.65))

    if (
        cx - r < 0 or cy - r < 0
        or cx + r >= largura
        or cy + r >= altura
    ):
        raise ValueError("Bolha fora da imagem.")

    regiao = cinza[
        cy - r:cy + r + 1,
        cx - r:cx + r + 1
    ]

    _, binaria = cv2.threshold(
        regiao,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    yy, xx = np.ogrid[
        -r:r + 1,
        -r:r + 1
    ]

    mascara = (xx * xx + yy * yy) <= r * r

    proporcao = np.count_nonzero(
        binaria[mascara]
    ) / np.count_nonzero(mascara)

    return float(proporcao)


def reconhecer_respostas(alinhada, dados):
    cinza = cv2.cvtColor(
        alinhada, cv2.COLOR_BGR2GRAY
    )

    visualizacao = alinhada.copy()
    resultados = {}

    for numero, alternativas in dados["bolhas"].items():
        preenchimentos = {}

        for letra, posicao in alternativas.items():
            taxa = analisar_bolha(
                cinza,
                posicao["x"],
                dados["pagina"]["altura"] - posicao["y"],
                posicao["raio"]
            )

            preenchimentos[letra] = round(taxa, 3)

            cx = round(posicao["x"] * ESCALA)
            cy = round(
                (dados["pagina"]["altura"] - posicao["y"])
                * ESCALA
            )

            cv2.circle(
                visualizacao,
                (cx, cy),
                round(posicao["raio"] * ESCALA),
                (255, 0, 0),
                2
            )

        # marcadas = [
        #     letra
        #     for letra, taxa in preenchimentos.items()
        #     if taxa >= LIMIAR_MARCACAO
        # ]

        # maior = max(preenchimentos.values())

        # if len(marcadas) > 1:
        #     status = "multipla"
        #     resposta = None
        # elif len(marcadas) == 1:
        #     status = "marcada"
        #     resposta = marcadas[0]
        # elif maior <= LIMIAR_BRANCO:
        #     status = "em_branco"
        #     resposta = None
        # else:
        #     status = "incerta"
        #     resposta = None
        marcadas = [
            letra
            for letra, taxa in preenchimentos.items()
            if taxa >= LIMIAR_MARCACAO
        ]

        suspeitas = [
            letra
            for letra, taxa in preenchimentos.items()
            if LIMIAR_BRANCO < taxa < LIMIAR_MARCACAO
        ]

        if len(marcadas) > 1:
            status = "multipla"
            resposta = None

        elif len(marcadas) == 1 and suspeitas:
            status = "incerta"
            resposta = None

        elif len(marcadas) == 1:
            status = "marcada"
            resposta = marcadas[0]

        elif suspeitas:
            status = "incerta"
            resposta = None

        else:
            status = "em_branco"
            resposta = None

        resultados[numero] = {
            "resposta": resposta,
            "status": status,
            "preenchimentos": preenchimentos
        }

    return resultados, visualizacao


def ler_qrcode(imagem):
    detector = cv2.QRCodeDetector()
    valor, _, _ = detector.detectAndDecode(imagem)
    return valor or None


def main():
    dados = carregar_dados()

    imagem = cv2.imread(str(FOTO))

    if imagem is None:
        raise FileNotFoundError(
            f"Fotografia não encontrada: {FOTO}"
        )

    alinhada = alinhar_cartao(imagem, dados)

    qr_lido = ler_qrcode(alinhada)

    if qr_lido != dados["cartao_id"]:
        raise RuntimeError(
            "QR Code não corresponde ao cartão esperado "
            "ou não pôde ser lido."
        )

    respostas, visualizacao = reconhecer_respostas(
        alinhada, dados
    )

    resultado = {
        "cartao_id": qr_lido,
        "avaliacao_id": dados["avaliacao_id"],
        "aluno_id": dados["aluno_id"],
        "respostas": respostas
    }

    cv2.imwrite(
        str(SAIDA / "cartao_alinhado.jpg"),
        alinhada
    )

    cv2.imwrite(
        str(SAIDA / "cartao_analisado.jpg"),
        visualizacao
    )

    with (SAIDA / "resultado_leitura.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(
            resultado,
            f,
            ensure_ascii=False,
            indent=2
        )
    print("\nVALIDAÇÃO DO QR CODE")
    print("-" * 35)
    print(f"QR Code lido: {qr_lido}")
    print(f"ID esperado: {dados['cartao_id']}")
    print("Status: QR Code validado com sucesso!")
    
    print("\nRESULTADO DA LEITURA")
    print("-" * 35)

    for numero, item in respostas.items():
        print(
            f"Questão {int(numero):02d}: "
            f"{item['resposta'] or '-'} "
            f"({item['status']})"
        )

    print("\nArquivos salvos em:", SAIDA)


if __name__ == "__main__":
    main()
