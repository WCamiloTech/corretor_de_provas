
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


# ============================================================
# GERADOR DE CARTÕES — V0.8.2.2
# ============================================================

BASE = Path(__file__).resolve().parent

ARQUIVO_JSON = BASE / "avaliacao.json"
ARQUIVO_ALUNOS = BASE / "alunos.json"

PASTA_RESULTADOS = BASE / "resultados"

# Mantida a pasta utilizada nos testes anteriores.
PASTA_SAIDA = BASE / "cartoes_teste_v06"

VERSAO_LAYOUT = "0.3"
VERSAO_PARTICIPANTES = 1


# ============================================================
# LEITURA DOS ARQUIVOS
# ============================================================

def carregar_avaliacao():
    if not ARQUIVO_JSON.is_file():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {ARQUIVO_JSON}"
        )

    with ARQUIVO_JSON.open(
        "r", encoding="utf-8-sig"
    ) as arquivo:
        prova = json.load(arquivo)

    if not isinstance(prova, dict):
        raise ValueError(
            "Estrutura da avaliação inválida."
        )

    return prova


def carregar_alunos():
    if not ARQUIVO_ALUNOS.is_file():
        raise FileNotFoundError(
            f"Cadastro não encontrado: {ARQUIVO_ALUNOS}"
        )

    with ARQUIVO_ALUNOS.open(
        "r", encoding="utf-8-sig"
    ) as arquivo:
        cadastro = json.load(arquivo)

    if not isinstance(cadastro, dict):
        raise ValueError(
            "Cadastro de alunos inválido."
        )

    alunos = cadastro.get("alunos")

    if not isinstance(alunos, list) or not alunos:
        raise ValueError(
            "Nenhum aluno cadastrado."
        )

    ids = set()

    for aluno in alunos:
        if not isinstance(aluno, dict):
            raise ValueError(
                "Registro de aluno inválido."
            )

        aluno_id = aluno.get("id")
        nome = aluno.get("nome")

        if (
            not isinstance(aluno_id, str)
            or not re.fullmatch(
                r"[A-Za-z0-9_-]+", aluno_id
            )
        ):
            raise ValueError(
                f"ID de aluno inválido: {aluno_id}"
            )

        if (
            not isinstance(nome, str)
            or not nome.strip()
        ):
            raise ValueError(
                f"Nome ausente para {aluno_id}"
            )

        if (
            "ativo" in aluno
            and not isinstance(aluno["ativo"], bool)
        ):
            raise ValueError(
                f"Situação cadastral inválida: {aluno_id}"
            )

        if aluno_id in ids:
            raise ValueError(
                f"ID duplicado: {aluno_id}"
            )

        ids.add(aluno_id)

    return cadastro


# ============================================================
# PARTICIPANTES DA AVALIAÇÃO
# ============================================================

def caminho_participantes(avaliacao_id):
    if (
        not isinstance(avaliacao_id, str)
        or not re.fullmatch(
            r"[A-Za-z0-9_-]+", avaliacao_id
        )
    ):
        raise ValueError(
            "ID da avaliação inválido."
        )

    return (
        PASTA_RESULTADOS
        / avaliacao_id
        / "participantes.json"
    )


def carregar_participantes(prova, cadastro):
    caminho = caminho_participantes(prova["id"])

    if not caminho.is_file():
        raise FileNotFoundError(
            "Registro de participantes não encontrado: "
            f"{caminho}\n"
            "Crie o registro usando "
            "gerenciar_participantes.py."
        )

    with caminho.open(
        "r", encoding="utf-8-sig"
    ) as arquivo:
        dados = json.load(arquivo)

    if not isinstance(dados, dict):
        raise ValueError(
            "Registro de participantes inválido."
        )

    if (
        type(dados.get("schema_version")) is not int
        or dados["schema_version"]
        != VERSAO_PARTICIPANTES
    ):
        raise ValueError(
            "Versão do registro de participantes "
            "não suportada."
        )

    if dados.get("avaliacao_id") != prova["id"]:
        raise ValueError(
            "O ID do registro de participantes "
            "não corresponde à avaliação."
        )

    if dados.get("turma") != prova["turma"]:
        raise ValueError(
            "A turma do registro de participantes "
            "não corresponde à avaliação."
        )

    participantes = dados.get("participantes")

    if (
        not isinstance(participantes, list)
        or not participantes
    ):
        raise ValueError(
            "A avaliação não possui participantes "
            "válidos."
        )

    cadastro_por_id = {
        aluno["id"]: aluno
        for aluno in cadastro["alunos"]
    }

    ids_encontrados = set()
    alunos_avaliacao = []

    for participante in participantes:
        if not isinstance(participante, dict):
            raise ValueError(
                "Registro de participante inválido."
            )

        aluno_id = participante.get("aluno_id")
        nome_historico = participante.get(
            "nome_na_avaliacao"
        )

        if (
            not isinstance(aluno_id, str)
            or not re.fullmatch(
                r"[A-Za-z0-9_-]+", aluno_id
            )
        ):
            raise ValueError(
                f"ID de participante inválido: "
                f"{aluno_id}"
            )

        if (
            not isinstance(nome_historico, str)
            or not nome_historico.strip()
        ):
            raise ValueError(
                f"Nome histórico inválido: {aluno_id}"
            )

        if aluno_id in ids_encontrados:
            raise ValueError(
                f"Participante duplicado: {aluno_id}"
            )

        if aluno_id not in cadastro_por_id:
            raise ValueError(
                f"Participante {aluno_id} não "
                "encontrado no cadastro de alunos."
            )

        ids_encontrados.add(aluno_id)

        # O nome histórico prevalece sobre o nome
        # atual do cadastro.
        #
        # A situação 'ativo' não interfere na
        # participação em avaliações anteriores.
        alunos_avaliacao.append(
            {
                "id": aluno_id,
                "nome": nome_historico
            }
        )

    return alunos_avaliacao


# ============================================================
# VALIDAÇÃO DA AVALIAÇÃO
# ============================================================

def validar_avaliacao(prova):
    campos = [
        "id",
        "titulo",
        "disciplina",
        "turma",
        "data",
        "aluno",
        "questoes"
    ]

    if not isinstance(prova, dict):
        raise ValueError(
            "Estrutura da avaliação inválida."
        )

    for campo in campos:
        if campo not in prova:
            raise ValueError(
                f"Campo obrigatório ausente: {campo}"
            )

    if not isinstance(prova["aluno"], dict):
        raise ValueError(
            "Dados do aluno inválidos."
        )

    for campo in ("id", "nome"):
        if not str(
            prova["aluno"].get(campo, "")
        ).strip():
            raise ValueError(
                f"Campo do aluno ausente: {campo}"
            )

    for campo in (
        "id", "titulo", "disciplina", "turma"
    ):
        if not str(prova[campo]).strip():
            raise ValueError(
                f"Campo inválido: {campo}"
            )

    questoes = prova["questoes"]

    if (
        not isinstance(questoes, list)
        or not questoes
    ):
        raise ValueError(
            "A avaliação não possui questões."
        )

    numeros = []
    objetivas = []
    discursivas = []

    for q in questoes:
        if not isinstance(q, dict):
            raise ValueError(
                "Registro de questão inválido."
            )

        numero = q.get("numero")
        tipo = q.get("tipo")
        pontos = q.get("pontos")

        if (
            type(numero) is not int
            or numero <= 0
        ):
            raise ValueError(
                "Número de questão inválido."
            )

        if (
            type(pontos) not in (int, float)
            or not 0 < pontos < float("inf")
        ):
            raise ValueError(
                f"Pontuação inválida na "
                f"questão {numero}."
            )

        numeros.append(numero)

        if tipo == "objetiva":
            alternativas = q.get(
                "alternativas"
            )
            gabarito = q.get("gabarito")

            if (
                not isinstance(
                    alternativas, list
                )
                or not 2 <= len(
                    alternativas
                ) <= 5
            ):
                raise ValueError(
                    f"Alternativas inválidas na "
                    f"questão {numero}."
                )

            if (
                any(
                    type(a) is not str
                    or len(a) != 1
                    or a not in "ABCDE"
                    for a in alternativas
                )
                or len(set(alternativas))
                != len(alternativas)
            ):
                raise ValueError(
                    f"Alternativas inválidas na "
                    f"questão {numero}."
                )

            if gabarito not in alternativas:
                raise ValueError(
                    f"Gabarito inválido na "
                    f"questão {numero}."
                )

            objetivas.append(q)

        elif tipo == "discursiva":
            discursivas.append(q)

        else:
            raise ValueError(
                f"Tipo inválido na questão "
                f"{numero}: {tipo}"
            )

    if len(numeros) != len(set(numeros)):
        raise ValueError(
            "Existem questões repetidas."
        )

    if len(objetivas) > MAX_OBJETIVAS:
        raise ValueError(
            f"Limite de {MAX_OBJETIVAS} "
            "objetivas excedido."
        )

    objetivas.sort(
        key=lambda q: q["numero"]
    )

    discursivas.sort(
        key=lambda q: q["numero"]
    )

    return objetivas, discursivas


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def nome_seguro(valor):
    return re.sub(
        r"[^A-Za-z0-9_-]",
        "_",
        str(valor)
    )


def caminhos_cartao(prova, aluno):
    nome = (
        f'{nome_seguro(prova["id"])}_'
        f'{nome_seguro(aluno["id"])}'
    )

    return (
        PASTA_SAIDA / f"{nome}.pdf",
        PASTA_SAIDA / f"{nome}.json"
    )


def desenhar_texto_limitado(
    pdf, texto, x, y, max_largura
):
    texto = str(texto)

    for tamanho in (10, 9, 8, 7):
        pdf.setFont(
            "Helvetica", tamanho
        )

        if (
            pdf.stringWidth(
                texto,
                "Helvetica",
                tamanho
            ) <= max_largura
        ):
            pdf.drawString(
                x, y, texto
            )
            return

    raise ValueError(
        "Texto muito longo para o cartão: "
        f"{texto}"
    )


# ============================================================
# DESENHO DO CARTÃO
# ============================================================

def desenhar_cabecalho(
    pdf, prova, cartao_id
):
    pdf.setFont(
        "Helvetica-Bold", 14
    )

    titulo = str(prova["titulo"])

    if (
        pdf.stringWidth(
            titulo,
            "Helvetica-Bold",
            14
        ) > 380
    ):
        raise ValueError(
            "Título muito longo. "
            "Use um título mais curto."
        )

    pdf.drawString(
        55,
        ALTURA - 78,
        titulo
    )

    desenhar_texto_limitado(
        pdf,
        prova["disciplina"],
        55,
        ALTURA - 102,
        380
    )

    desenhar_texto_limitado(
        pdf,
        f'Aluno: {prova["aluno"]["nome"]}',
        55,
        ALTURA - 125,
        380
    )

    desenhar_texto_limitado(
        pdf,
        f'Turma: {prova["turma"]}',
        55,
        ALTURA - 145,
        380
    )

    desenhar_texto_limitado(
        pdf,
        f'Data: {prova["data"]}',
        55,
        ALTURA - 165,
        380
    )

    # Mantém o mesmo conteúdo e algoritmo
    # de identificação do QR Code.
    qr = qrcode.QRCode(
        version=None,
        error_correction=(
            qrcode.constants.ERROR_CORRECT_M
        ),
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

    pdf.setFont(
        "Helvetica-Bold", 10
    )

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


def desenhar_rodape(
    pdf, objetivas, discursivas
):
    total_obj = sum(
        q["pontos"]
        for q in objetivas
    )

    total_disc = sum(
        q["pontos"]
        for q in discursivas
    )

    total = total_obj + total_disc

    pdf.setFont(
        "Helvetica-Bold", 10
    )

    pdf.drawString(
        55,
        140,
        "QUESTÕES DISCURSIVAS"
    )

    pdf.setFont(
        "Helvetica", 9
    )

    if discursivas:
        numeros = ", ".join(
            str(q["numero"])
            for q in discursivas
        )

        texto = (
            f"Questões: {numeros} "
            "- correção manual"
        )
    else:
        texto = (
            "Não há questões discursivas."
        )

    desenhar_texto_limitado(
        pdf,
        texto,
        55,
        121,
        LARGURA - 110
    )

    pdf.line(
        55,
        108,
        LARGURA - 55,
        108
    )

    pdf.setFont(
        "Helvetica", 9
    )

    pdf.drawString(
        55,
        90,
        f"Objetivas: {total_obj:g} pontos"
    )

    pdf.drawString(
        225,
        90,
        f"Discursivas: {total_disc:g} pontos"
    )

    pdf.drawString(
        410,
        90,
        f"Total: {total:g}"
    )

    pdf.drawString(
        55,
        68,
        "Nota final: __________"
    )


# ============================================================
# GERAÇÃO INDIVIDUAL
# ============================================================

def gerar_cartao(prova, aluno):
    prova = dict(prova)
    prova["aluno"] = dict(aluno)

    objetivas, discursivas = (
        validar_avaliacao(prova)
    )

    caminho_pdf, caminho_mapa = (
        caminhos_cartao(prova, aluno)
    )

    # Proteção também na geração individual.
    if (
        caminho_pdf.exists()
        or caminho_mapa.exists()
    ):
        raise FileExistsError(
            "Já existem arquivos do cartão "
            f"para {aluno['id']}."
        )

    PASTA_SAIDA.mkdir(
        parents=True,
        exist_ok=True
    )

    # Regra de UUID preservada.
    chave = (
        f'{prova["id"]}:'
        f'{prova["aluno"]["id"]}'
    )

    cartao_id = str(
        uuid5(NAMESPACE_URL, chave)
    )

    pdf = canvas.Canvas(
        str(caminho_pdf),
        pagesize=A4
    )

    pdf.setTitle(
        "Cartão-resposta"
    )

    pdf.setAuthor(
        "Sistema de Avaliações"
    )

    mapa_marcadores = (
        desenhar_marcadores(pdf)
    )

    desenhar_cabecalho(
        pdf,
        prova,
        cartao_id
    )

    mapa_bolhas = desenhar_questoes(
        pdf,
        objetivas
    )

    desenhar_rodape(
        pdf,
        objetivas,
        discursivas
    )

    pdf.save()

    # Estrutura do mapa preservada.
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
        "x", encoding="utf-8"
    ) as arquivo:
        json.dump(
            registro,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    total = sum(
        q["pontos"]
        for q in prova["questoes"]
    )

    print(
        "\nCartão gerado com sucesso!"
    )
    print(f"PDF: {caminho_pdf}")
    print(f"Mapa: {caminho_mapa}")
    print(f"ID: {cartao_id}")
    print(
        f"Objetivas: {len(objetivas)}"
    )
    print(
        f"Discursivas: {len(discursivas)}"
    )
    print(
        f"Pontuação total: {total:g}"
    )


# ============================================================
# GERAÇÃO EM LOTE
# ============================================================

def gerar_cartoes_turma():
    prova = carregar_avaliacao()
    cadastro = carregar_alunos()

    if (
        cadastro.get("turma")
        != prova.get("turma")
    ):
        raise ValueError(
            "A turma do cadastro não corresponde "
            "à turma da avaliação."
        )

    # Seleção exclusiva pelo registro
    # de participantes da avaliação.
    participantes = carregar_participantes(
        prova,
        cadastro
    )

    # Validação antes de iniciar o lote.
    prova_validacao = dict(prova)
    prova_validacao["aluno"] = (
        dict(participantes[0])
    )

    validar_avaliacao(
        prova_validacao
    )

    print(
        "\nGERAÇÃO DE CARTÕES EM LOTE"
    )
    print("-" * 45)
    print(
        "Avaliação:", prova["id"]
    )
    print(
        "Turma:", prova["turma"]
    )
    print(
        "Alunos cadastrados:",
        len(cadastro["alunos"])
    )
    print(
        "Participantes da avaliação:",
        len(participantes)
    )

    print(
        "\nPARTICIPANTES SELECIONADOS"
    )

    for aluno in participantes:
        print(
            f" - {aluno['id']}: "
            f"{aluno['nome']}"
        )

    # Verifica todo o lote antes de gerar.
    # Se algum arquivo já existir,
    # nenhum novo cartão será produzido.
    existentes = []

    for aluno in participantes:
        caminho_pdf, caminho_mapa = (
            caminhos_cartao(prova, aluno)
        )

        if (
            caminho_pdf.exists()
            or caminho_mapa.exists()
        ):
            existentes.append(
                aluno["id"]
            )

    if existentes:
        raise FileExistsError(
            "Já existem cartões ou mapas para: "
            + ", ".join(existentes)
            + ". Nenhum cartão será gerado "
            "neste lote. Os arquivos existentes "
            "foram preservados."
        )

    for indice, aluno in enumerate(
        participantes,
        start=1
    ):
        print(
            f"\n[{indice}/{len(participantes)}] "
            f"{aluno['nome']}"
        )

        gerar_cartao(
            prova,
            aluno
        )

    print(
        "\nTodos os cartões dos participantes "
        "foram gerados."
    )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    try:
        gerar_cartoes_turma()

    except (
        FileExistsError,
        ValueError,
        FileNotFoundError,
        json.JSONDecodeError,
        OSError
    ) as erro:
        print(
            f"\nOperação interrompida: {erro}"
        )
        raise SystemExit(1)

    except KeyboardInterrupt:
        print(
            "\nGeração interrompida pelo usuário."
        )
        raise SystemExit(130)
