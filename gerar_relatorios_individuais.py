
import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)


# ============================================================
# V0.7.3 — RELATÓRIOS INDIVIDUAIS
# ============================================================

BASE = Path(__file__).resolve().parent
RESULTADOS = BASE / "resultados"
ARQ_AVALIACAO = BASE / "avaliacao.json"
ARQ_ALUNOS = BASE / "alunos.json"

TOLERANCIA = 0.001


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def carregar_json(caminho):
    with caminho.open(
        "r", encoding="utf-8-sig"
    ) as arquivo:
        return json.load(arquivo)


def identificador(valor, descricao):
    if (
        not isinstance(valor, str)
        or not re.fullmatch(
            r"[A-Za-z0-9_-]+", valor
        )
    ):
        raise ValueError(
            f"{descricao}: identificador inválido"
        )
    return valor


def numero(valor, descricao):
    if (
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(valor)
    ):
        raise ValueError(
            f"{descricao}: valor numérico inválido"
        )
    return float(valor)


def igual(a, b):
    return math.isclose(
        a, b, rel_tol=0, abs_tol=TOLERANCIA
    )


def decimal(valor):
    if valor is None:
        return "-"
    return f"{valor:.2f}".replace(".", ",")


def texto(valor):
    return escape(str(valor))


def data_hora():
    return datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )


# ============================================================
# VALIDAÇÃO DA AVALIAÇÃO
# ============================================================

def preparar_avaliacao(avaliacao):
    avaliacao_id = identificador(
        avaliacao.get(
            "id", avaliacao.get("avaliacao_id")
        ),
        "Avaliação"
    )

    questoes = avaliacao.get("questoes")

    if not isinstance(questoes, list) or not questoes:
        raise ValueError(
            "Avaliação sem questões"
        )

    definicoes = {}

    for q in questoes:
        n = q.get("numero")

        if (
            isinstance(n, bool)
            or not isinstance(n, int)
            or n <= 0
            or n in definicoes
        ):
            raise ValueError(
                f"Número de questão inválido: {n}"
            )

        tipo = q.get("tipo")
        pontos = numero(
            q.get("pontos"),
            f"Q{n}: pontuação"
        )

        if (
            tipo not in ("objetiva", "discursiva")
            or pontos <= 0
        ):
            raise ValueError(
                f"Q{n}: definição inválida"
            )

        if tipo == "objetiva":
            alternativas = q.get("alternativas")
            gabarito = q.get("gabarito")

            if (
                not isinstance(
                    alternativas, (list, dict)
                )
                or not alternativas
                or gabarito not in alternativas
            ):
                raise ValueError(
                    f"Q{n}: alternativas ou "
                    "gabarito inválidos"
                )

        definicoes[n] = q

    return avaliacao_id, definicoes


# ============================================================
# VALIDAÇÃO DA CORREÇÃO
# ============================================================

def validar_correcao(
    dados, avaliacao_id, aluno, definicoes
):
    aluno_id = aluno["id"]

    uuid_esperado = str(
        uuid5(
            NAMESPACE_URL,
            f"{avaliacao_id}:{aluno_id}"
        )
    )

    if (
        dados.get("avaliacao_id") != avaliacao_id
        or dados.get("aluno_id") != aluno_id
        or dados.get("aluno_nome") != aluno["nome"]
        or dados.get("cartao_id") != uuid_esperado
    ):
        raise ValueError(
            "Identificação ou UUID incompatível"
        )

    questoes = dados.get("questoes")

    if not isinstance(questoes, list):
        raise ValueError(
            "Lista de questões inválida"
        )

    por_numero = {}

    for q in questoes:
        n = q.get("numero")

        if n not in definicoes or n in por_numero:
            raise ValueError(
                "Questão desconhecida ou duplicada"
            )

        por_numero[n] = q

    if set(por_numero) != set(definicoes):
        raise ValueError(
            "Questões incompatíveis com a avaliação"
        )

    soma = 0.0
    maximo_total = 0.0
    pendencias_calculadas = []

    for n, definicao in definicoes.items():
        q = por_numero[n]
        tipo = definicao["tipo"]

        maximo = numero(
            definicao["pontos"],
            f"Q{n}: pontuação máxima"
        )

        maximo_registrado = numero(
            q.get("pontos_possiveis"),
            f"Q{n}: pontuação registrada"
        )

        if (
            q.get("tipo") != tipo
            or not igual(maximo, maximo_registrado)
        ):
            raise ValueError(
                f"Q{n}: definição incompatível"
            )

        maximo_total += maximo

        status = q.get("status")
        valor = q.get("pontos_obtidos")

        if status in ("pendente", "incerta"):
            if valor is not None:
                raise ValueError(
                    f"Q{n}: pendência com pontuação"
                )

            pendencias_calculadas.append(n)
            continue

        pontos = numero(
            valor, f"Q{n}: pontos obtidos"
        )

        if not 0 <= pontos <= maximo:
            raise ValueError(
                f"Q{n}: pontuação fora do intervalo"
            )

        if tipo == "objetiva":
            if status not in (
                "marcada",
                "revisada",
                "em_branco",
                "multipla"
            ):
                raise ValueError(
                    f"Q{n}: status objetivo inválido"
                )

            if (
                q.get("gabarito")
                != definicao["gabarito"]
            ):
                raise ValueError(
                    f"Q{n}: gabarito divergente"
                )

            resposta = q.get("resposta")
            alternativas = definicao["alternativas"]

            if status in ("marcada", "revisada"):
                if resposta not in alternativas:
                    raise ValueError(
                        f"Q{n}: resposta inválida"
                    )

                esperado = (
                    maximo
                    if resposta == definicao["gabarito"]
                    else 0.0
                )

                if not igual(pontos, esperado):
                    raise ValueError(
                        f"Q{n}: nota objetiva divergente"
                    )

            elif (
                resposta is not None
                or not igual(pontos, 0)
            ):
                raise ValueError(
                    f"Q{n}: marcação especial inválida"
                )

        elif status != "corrigida":
            raise ValueError(
                f"Q{n}: status discursivo inválido"
            )

        soma += pontos

    possiveis = numero(
        dados.get("pontos_possiveis"),
        "Pontuação máxima"
    )

    confirmados = numero(
        dados.get("pontos_confirmados"),
        "Pontos confirmados"
    )

    if (
        not igual(possiveis, maximo_total)
        or not igual(confirmados, soma)
    ):
        raise ValueError(
            "Totais da correção inconsistentes"
        )

    pendencias = dados.get("pendencias", [])

    if (
        not isinstance(pendencias, list)
        or len(pendencias) != len(set(pendencias))
        or set(pendencias) != set(pendencias_calculadas)
    ):
        raise ValueError(
            "Pendências inconsistentes"
        )

    if dados.get("status") == "finalizada":
        if pendencias_calculadas:
            raise ValueError(
                "Correção finalizada com pendências"
            )

        nota = numero(
            dados.get("nota_final"),
            "Nota final"
        )

        if not igual(nota, soma):
            raise ValueError(
                "Nota final divergente"
            )

        return por_numero, nota, maximo_total

    if dados.get("status") == "pendente":
        if dados.get("nota_final") is not None:
            raise ValueError(
                "Correção pendente com nota final"
            )

        return por_numero, None, maximo_total

    raise ValueError(
        "Status geral desconhecido"
    )


# ============================================================
# PREPARAÇÃO DO RELATÓRIO
# ============================================================

def montar_relatorio(
    avaliacao_id, turma, aluno,
    dados, definicoes
):
    por_numero, nota, maximo = validar_correcao(
        dados,
        avaliacao_id,
        aluno,
        definicoes
    )

    if nota is None:
        raise ValueError(
            "A correção ainda não foi finalizada"
        )

    itens = []

    for n, definicao in sorted(
        definicoes.items()
    ):
        q = por_numero[n]
        tipo = definicao["tipo"]
        status = q["status"]
        pontos = float(q["pontos_obtidos"])
        possiveis = float(definicao["pontos"])

        if tipo == "objetiva":
            if status == "em_branco":
                resposta = "Não respondida"
            elif status == "multipla":
                resposta = "Marcação múltipla"
            else:
                resposta = str(q["resposta"])

            situacao = (
                "Acerto"
                if igual(pontos, possiveis)
                else "Sem pontuação"
            )

            if status == "em_branco":
                situacao = "Em branco"
            elif status == "multipla":
                situacao = "Marcação múltipla"
            elif status == "revisada":
                situacao += " (revisada)"

        else:
            resposta = "Correção manual"
            situacao = "Corrigida"

        itens.append({
            "numero": n,
            "tipo": tipo,
            "resposta": resposta,
            "situacao": situacao,
            "pontos": pontos,
            "maximo": possiveis
        })

    return {
        "avaliacao_id": avaliacao_id,
        "turma": turma,
        "aluno_id": aluno["id"],
        "aluno_nome": aluno["nome"],
        "nota": nota,
        "maximo": maximo,
        "nota_100": nota / maximo * 100,
        "aproveitamento": nota / maximo * 100,
        "questoes": itens,
        "gerado_em": data_hora()
    }


# ============================================================
# PDF INDIVIDUAL
# ============================================================

def gerar_pdf(relatorio, destino):
    documento = SimpleDocTemplate(
        str(destino),
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm
    )

    titulo = ParagraphStyle(
        "TituloRelatorio",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#24354A"),
        spaceAfter=12
    )

    subtitulo = ParagraphStyle(
        "SubtituloRelatorio",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=12,
        spaceAfter=7
    )

    normal = ParagraphStyle(
        "TextoRelatorio",
        fontName="Helvetica",
        fontSize=9,
        leading=13
    )

    pequeno = ParagraphStyle(
        "PequenoRelatorio",
        fontName="Helvetica",
        fontSize=8,
        leading=11
    )

    elementos = []

    elementos.append(
        Paragraph(
            "RELATÓRIO INDIVIDUAL DE DESEMPENHO",
            titulo
        )
    )

    elementos.append(
        Paragraph(
            f"<b>Avaliação:</b> "
            f"{texto(relatorio['avaliacao_id'])}",
            normal
        )
    )

    elementos.append(
        Paragraph(
            f"<b>Turma:</b> "
            f"{texto(relatorio['turma'])}",
            normal
        )
    )

    elementos.append(
        Paragraph(
            f"<b>Aluno:</b> "
            f"{texto(relatorio['aluno_nome'])}",
            normal
        )
    )

    elementos.append(
        Paragraph(
            f"<b>ID:</b> "
            f"{texto(relatorio['aluno_id'])}",
            normal
        )
    )

    elementos.append(
        Spacer(1, 10)
    )

    resumo = [
        ["Nota obtida", "Pontuação máxima", "Nota / 100"],
        [
            decimal(relatorio["nota"]),
            decimal(relatorio["maximo"]),
            decimal(relatorio["nota_100"])
        ]
    ]

    tabela_resumo = Table(
        resumo,
        colWidths=[58 * mm] * 3,
        rowHeights=[22, 28]
    )

    tabela_resumo.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#E9EEF5")),
            ("TEXTCOLOR", (0, 0), (-1, -1),
             colors.HexColor("#24354A")),
            ("FONTNAME", (0, 0), (-1, 0),
             "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, 1),
             "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, 1), 13),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1),
             0.5, colors.HexColor("#CED6E0")),
            ("INNERGRID", (0, 0), (-1, -1),
             0.5, colors.HexColor("#CED6E0")),
        ])
    )

    elementos.append(tabela_resumo)

    elementos.append(
        Paragraph(
            "DESEMPENHO POR QUESTÃO",
            subtitulo
        )
    )

    cabecalho = [
        "Questão",
        "Tipo",
        "Resposta",
        "Situação",
        "Pontos"
    ]

    linhas = [[
        Paragraph(f"<b>{x}</b>", pequeno)
        for x in cabecalho
    ]]

    for item in relatorio["questoes"]:
        linhas.append([
            f"Q{item['numero']:02d}",
            Paragraph(
                texto(item["tipo"].capitalize()),
                pequeno
            ),
            Paragraph(
                texto(item["resposta"]),
                pequeno
            ),
            Paragraph(
                texto(item["situacao"]),
                pequeno
            ),
            (
                f"{decimal(item['pontos'])}"
                f"/{decimal(item['maximo'])}"
            )
        ])

    tabela = Table(
        linhas,
        colWidths=[
            20 * mm,
            28 * mm,
            35 * mm,
            55 * mm,
            36 * mm
        ],
        repeatRows=1,
        hAlign="LEFT"
    )

    tabela.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#24354A")),
            ("TEXTCOLOR", (0, 0), (-1, 0),
             colors.white),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [
                 colors.white,
                 colors.HexColor("#F2F5F9")
             ]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, -1), (-1, -1),
             0.5, colors.HexColor("#CED6E0")),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (-1, 0), (-1, -1), "CENTER"),
        ])
    )

    elementos.append(tabela)

    elementos.append(Spacer(1, 14))

    elementos.append(
        Paragraph(
            "<b>Observações:</b> Este relatório "
            "apresenta os resultados registrados "
            "na correção finalizada. "
            "O gabarito não é divulgado neste documento.",
            pequeno
        )
    )

    elementos.append(
        Paragraph(
            f"<b>Gerado em:</b> "
            f"{texto(relatorio['gerado_em'])}",
            pequeno
        )
    )

    documento.build(elementos)


# ============================================================
# CSV INDIVIDUAL
# ============================================================

def gerar_csv(relatorio, destino):
    with destino.open(
        "x", encoding="utf-8-sig", newline=""
    ) as arquivo:
        escritor = csv.writer(
            arquivo, delimiter=";"
        )

        escritor.writerow([
            "avaliacao_id",
            "turma",
            "aluno_id",
            "aluno_nome",
            "questao",
            "tipo",
            "resposta",
            "situacao",
            "pontos_obtidos",
            "pontos_possiveis",
            "nota_final",
            "nota_100"
        ])

        for item in relatorio["questoes"]:
            escritor.writerow([
                relatorio["avaliacao_id"],
                relatorio["turma"],
                relatorio["aluno_id"],
                relatorio["aluno_nome"],
                item["numero"],
                item["tipo"],
                item["resposta"],
                item["situacao"],
                decimal(item["pontos"]),
                decimal(item["maximo"]),
                decimal(relatorio["nota"]),
                decimal(relatorio["nota_100"])
            ])


# ============================================================
# SELEÇÃO E GERAÇÃO
# ============================================================

def executar():
    avaliacao = carregar_json(ARQ_AVALIACAO)
    cadastro = carregar_json(ARQ_ALUNOS)

    avaliacao_id, definicoes = preparar_avaliacao(
        avaliacao
    )

    turma = avaliacao.get("turma", "")

    if cadastro.get("turma") != turma:
        raise ValueError(
            "Turma incompatível"
        )

    alunos = cadastro.get("alunos")

    if not isinstance(alunos, list):
        raise ValueError(
            "Cadastro de alunos inválido"
        )

    alunos_por_id = {}

    for aluno in alunos:
        aluno_id = identificador(
            aluno.get("id"), "Aluno"
        )

        if aluno_id in alunos_por_id:
            raise ValueError(
                f"Aluno duplicado: {aluno_id}"
            )

        alunos_por_id[aluno_id] = aluno

    print("\nRELATÓRIOS INDIVIDUAIS — V0.7.3")
    print("=" * 60)
    print(f"Avaliação: {avaliacao_id}")
    print(f"Turma: {turma}")

    print("\n1 - Gerar relatório de um aluno")
    print("2 - Gerar relatórios de toda a turma")
    print("0 - Sair")

    opcao = input(
        "\nEscolha uma opção: "
    ).strip()

    if opcao == "0":
        print("Operação cancelada.")
        return

    if opcao == "1":
        aluno_id = input(
            "Informe o ID do aluno: "
        ).strip().upper()

        if aluno_id not in alunos_por_id:
            print("Aluno não encontrado.")
            return

        selecionados = [
            alunos_por_id[aluno_id]
        ]

    elif opcao == "2":
        selecionados = list(
            alunos_por_id.values()
        )

    else:
        print("Opção inválida.")
        return

    preparados = []
    ignorados = []
    erros = []

    # Validação anterior à geração
    for aluno in selecionados:
        aluno_id = aluno["id"]

        caminho = (
            RESULTADOS
            / avaliacao_id
            / aluno_id
            / "resultado_correcao.json"
        )

        if not caminho.is_file():
            ignorados.append(
                f"{aluno_id}: sem correção"
            )
            continue

        try:
            dados = carregar_json(caminho)

            if dados.get("status") != "finalizada":
                ignorados.append(
                    f"{aluno_id}: correção pendente"
                )
                continue

            relatorio = montar_relatorio(
                avaliacao_id,
                turma,
                aluno,
                dados,
                definicoes
            )

            preparados.append(relatorio)

        except (
            ValueError,
            KeyError,
            TypeError,
            OSError,
            json.JSONDecodeError
        ) as erro:
            erros.append(
                f"{aluno_id}: {erro}"
            )

    if erros:
        print(
            "\nGERAÇÃO BLOQUEADA: "
            "inconsistências encontradas."
        )

        for erro in erros:
            print(" -", erro)

        return

    if not preparados:
        print(
            "\nNenhuma correção finalizada "
            "disponível para gerar relatórios."
        )
        return

    print("\nPRÉVIA")
    print("-" * 60)

    for relatorio in preparados:
        print(
            f"{relatorio['aluno_id']:<12} | "
            f"{relatorio['aluno_nome']:<25} | "
            f"{decimal(relatorio['nota'])}"
            f"/{decimal(relatorio['maximo'])}"
        )

    if ignorados:
        print("\nRegistros ignorados:")
        for item in ignorados:
            print(" -", item)

    confirmacao = input(
        "\nConfirma a geração dos relatórios? "
        "Digite GERAR (maiúsculas ou minúsculas) "
        "ou pressione Enter para cancelar: "
    ).strip().upper()

    if confirmacao != "GERAR":
        print(
            "Operação cancelada. "
            "Nenhum relatório gerado."
        )
        return

    gerados = 0
    falhas = 0

    for relatorio in preparados:
        aluno_id = relatorio["aluno_id"]

        pasta = (
            RESULTADOS
            / avaliacao_id
            / aluno_id
            / "relatorios"
        )

        pasta.mkdir(
            parents=True, exist_ok=True
        )

        instante = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        nome_base = (
            f"relatorio_{aluno_id}_{instante}"
        )

        pdf = pasta / f"{nome_base}.pdf"
        csv_destino = pasta / f"{nome_base}.csv"

        if pdf.exists() or csv_destino.exists():
            print(
                f"[ERRO] {aluno_id}: "
                "nome de arquivo já existente"
            )
            falhas += 1
            continue

        try:
            gerar_pdf(relatorio, pdf)
            gerar_csv(relatorio, csv_destino)

            print(
                f"\n[GERADO] {aluno_id}"
            )
            print(f" PDF: {pdf}")
            print(f" CSV: {csv_destino}")

            gerados += 1

        except Exception as erro:
            print(
                f"[ERRO] {aluno_id}: {erro}"
            )
            falhas += 1

    print("\nRESUMO DA GERAÇÃO")
    print("-" * 60)
    print(f"Alunos processados: {len(preparados)}")
    print(f"Relatórios gerados: {gerados}")
    print(f"Falhas: {falhas}")
    print(f"Ignorados: {len(ignorados)}")
    print(
        "Nenhuma correção ou histórico foi alterado."
    )


if __name__ == "__main__":
    try:
        executar()
    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        json.JSONDecodeError
    ) as erro:
        print(
            f"\nOperação interrompida: {erro}"
        )
