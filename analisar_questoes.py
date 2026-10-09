
import csv
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from uuid import NAMESPACE_URL, uuid5


# ============================================================
# V0.7.2 — ANÁLISE DE DESEMPENHO POR QUESTÃO
# ============================================================

BASE = Path(__file__).resolve().parent
RESULTADOS = BASE / "resultados"
ARQ_AVALIACAO = BASE / "avaliacao.json"
ARQ_ALUNOS = BASE / "alunos.json"

TOLERANCIA = 0.001


def carregar_json(caminho):
    with caminho.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def numero(valor, descricao):
    if (
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(valor)
    ):
        raise ValueError(
            f"{descricao}: número inválido"
        )
    return float(valor)


def igual(a, b):
    return math.isclose(
        a, b, rel_tol=0, abs_tol=TOLERANCIA
    )


def identificador(valor, descricao):
    if (
        not isinstance(valor, str)
        or not valor
        or not all(
            c.isalnum() or c in "-_"
            for c in valor
        )
    ):
        raise ValueError(
            f"{descricao}: identificador inválido"
        )
    return valor


def formatar(valor):
    if valor is None:
        return "-"
    return f"{valor:.2f}"


def csv_numero(valor):
    if valor is None:
        return ""
    return f"{valor:.2f}".replace(".", ",")


# ============================================================
# CONFIGURAÇÃO DA AVALIAÇÃO
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
            "Avaliação sem questões válidas"
        )

    definicoes = {}

    for questao in questoes:
        n = questao.get("numero")

        if (
            isinstance(n, bool)
            or not isinstance(n, int)
            or n <= 0
            or n in definicoes
        ):
            raise ValueError(
                f"Número de questão inválido: {n}"
            )

        tipo = questao.get("tipo")

        if tipo not in ("objetiva", "discursiva"):
            raise ValueError(
                f"Q{n}: tipo desconhecido"
            )

        pontos = numero(
            questao.get("pontos"),
            f"Q{n}: pontuação"
        )

        if pontos <= 0:
            raise ValueError(
                f"Q{n}: pontuação deve ser positiva"
            )

        if tipo == "objetiva":
            alternativas = questao.get("alternativas")
            gabarito = questao.get("gabarito")

            if (
                not isinstance(alternativas, (list, dict))
                or not alternativas
                or gabarito not in alternativas
            ):
                raise ValueError(
                    f"Q{n}: alternativas ou "
                    "gabarito inválidos"
                )

        definicoes[n] = questao

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

    for questao in questoes:
        n = questao.get("numero")

        if n not in definicoes or n in por_numero:
            raise ValueError(
                "Questão desconhecida ou duplicada"
            )

        por_numero[n] = questao

    if set(por_numero) != set(definicoes):
        raise ValueError(
            "Quantidade ou numeração de "
            "questões incompatível"
        )

    soma = 0.0
    maximo_total = 0.0
    pendencias_calculadas = []

    for n, definicao in definicoes.items():
        q = por_numero[n]
        tipo = definicao["tipo"]

        maximo = numero(
            definicao["pontos"],
            f"Q{n}: máximo"
        )

        maximo_registrado = numero(
            q.get("pontos_possiveis"),
            f"Q{n}: máximo registrado"
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
                    f"Q{n}: pendência com nota"
                )
            pendencias_calculadas.append(n)
            continue

        pontos = numero(
            valor, f"Q{n}: pontos obtidos"
        )

        if not 0 <= pontos <= maximo:
            raise ValueError(
                f"Q{n}: pontos fora do intervalo"
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

            else:
                if resposta is not None or not igual(
                    pontos, 0
                ):
                    raise ValueError(
                        f"Q{n}: marcação especial "
                        "incompatível"
                    )

        else:
            if status != "corrigida":
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
        or set(pendencias) != set(pendencias_calculadas)
        or len(pendencias) != len(set(pendencias))
    ):
        raise ValueError(
            "Lista de pendências inconsistente"
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

        return "finalizada", por_numero

    if dados.get("status") == "pendente":
        if dados.get("nota_final") is not None:
            raise ValueError(
                "Correção pendente com nota final"
            )

        return "pendente", por_numero

    raise ValueError(
        "Status geral desconhecido"
    )


# ============================================================
# ANÁLISE DAS QUESTÕES
# ============================================================

def analisar_questao(numero_questao, definicao, correcoes):
    tipo = definicao["tipo"]
    maximo = float(definicao["pontos"])

    notas = []
    status_contagem = Counter()
    respostas = Counter()

    acertos = 0
    erros = 0
    brancos = 0
    multiplas = 0

    for correcao in correcoes:
        q = correcao[numero_questao]

        pontos = float(q["pontos_obtidos"])
        notas.append(pontos)

        status = q["status"]
        status_contagem[status] += 1

        if tipo == "objetiva":
            if status == "em_branco":
                brancos += 1
            elif status == "multipla":
                multiplas += 1
            else:
                resposta = q["resposta"]
                respostas[resposta] += 1

                if igual(pontos, maximo):
                    acertos += 1
                else:
                    erros += 1

    quantidade = len(notas)
    media = mean(notas) if notas else None

    aproveitamento = (
        sum(notas) / (quantidade * maximo) * 100
        if quantidade
        else None
    )

    return {
        "numero": numero_questao,
        "tipo": tipo,
        "maximo": maximo,
        "quantidade": quantidade,
        "media": media,
        "menor": min(notas) if notas else None,
        "maior": max(notas) if notas else None,
        "aproveitamento": aproveitamento,
        "acertos": acertos if tipo == "objetiva" else None,
        "erros": erros if tipo == "objetiva" else None,
        "brancos": brancos if tipo == "objetiva" else None,
        "multiplas": multiplas if tipo == "objetiva" else None,
        "respostas": dict(sorted(respostas.items())),
        "status": dict(status_contagem)
    }


# ============================================================
# EXIBIÇÃO
# ============================================================


def mostrar_resultados(
    avaliacao_id, turma, total_alunos,
    correcoes, pendentes, ausentes, analises
):
    print(
        "\nANÁLISE DE DESEMPENHO POR QUESTÃO — V0.7.2"
    )
    print("=" * 89)

    print(f"Avaliação: {avaliacao_id}")
    print(f"Turma: {turma}")
    print(f"Alunos cadastrados: {total_alunos}")
    print(f"Correções finalizadas: {len(correcoes)}")
    print(f"Correções pendentes: {pendentes}")
    print(f"Sem correção: {ausentes}")

    # ========================================================
    # TABELA COMPARATIVA
    # ========================================================

    print("\nDESEMPENHO POR QUESTÃO")
    print("=" * 89)

    cabecalho = (
        f"{'Questão':<9}"
        f"{'Tipo':<14}"
        f"{'Média':>7}"
        f"{'Mín.':>9}"
        f"{'Máx.':>8}"
        f"{'Aprov.':>11}"
        f"{'Acertos':>9}"
        f"{'Erros':>7}"
        f"{'Branco':>8}"
        f"{'Múlt.':>7}"
    )

    print(cabecalho)
    print("-" * 89)

    for item in analises:
        n = item["numero"]

        tipo = item["tipo"].capitalize()

        media = formatar(item["media"])
        menor = formatar(item["menor"])
        maior = formatar(item["maior"])

        if item["aproveitamento"] is not None:
            aproveitamento = (
                f"{item['aproveitamento']:.2f}%"
            )
        else:
            aproveitamento = "-"

        def contador(valor):
            return "-" if valor is None else str(valor)

        linha = (
            f"{'Q' + str(n).zfill(2):<9}"
            f"{tipo:<14}"
            f"{media:>7}"
            f"{menor:>9}"
            f"{maior:>8}"
            f"{aproveitamento:>11}"
            f"{contador(item['acertos']):>9}"
            f"{contador(item['erros']):>7}"
            f"{contador(item['brancos']):>8}"
            f"{contador(item['multiplas']):>7}"
        )

        print(linha)

    print("=" * 89)

    # ========================================================
    # DISTRIBUIÇÃO DAS RESPOSTAS OBJETIVAS
    # ========================================================

    print("\nDISTRIBUIÇÃO DAS ALTERNATIVAS")
    print("-" * 60)

    for item in analises:
        if item["tipo"] != "objetiva":
            continue

        numero = item["numero"]

        respostas = item["respostas"]

        if respostas:
            distribuicao = " | ".join(
                f"{alternativa}: {quantidade}"
                for alternativa, quantidade
                in respostas.items()
            )
        else:
            distribuicao = (
                "Nenhuma alternativa válida registrada"
            )

        print(
            f"Q{numero:02d} | {distribuicao}"
        )

    # ========================================================
    # PRIORIDADE DE REVISÃO
    # ========================================================

    print("\nPRIORIDADE DE REVISÃO")
    print("-" * 60)

    ordenadas = sorted(
        (
            item for item in analises
            if item["aproveitamento"] is not None
        ),
        key=lambda item: (
            item["aproveitamento"],
            item["numero"]
        )
    )

    if not ordenadas:
        print(
            "Sem correções finalizadas para análise."
        )
        return

    for posicao, item in enumerate(
        ordenadas, start=1
    ):
        print(
            f"{posicao:>2}. "
            f"Q{item['numero']:02d} "
            f"({item['tipo']}) — "
            f"{item['aproveitamento']:.2f}%"
        )

    print(
        "\nObservação: a prioridade é definida "
        "pelo menor aproveitamento, não "
        "necessariamente pela dificuldade "
        "conceitual."
    )

# ============================================================
# EXPORTAÇÃO CSV
# ============================================================

def exportar_csv(
    avaliacao_id, turma, analises
):
    pasta = (
        RESULTADOS
        / avaliacao_id
        / "relatorios"
    )

    pasta.mkdir(
        parents=True, exist_ok=True
    )

    instante = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    destino = (
        pasta
        / f"analise_questoes_{instante}.csv"
    )

    campos = [
        "avaliacao_id",
        "turma",
        "questao",
        "tipo",
        "alunos_analisados",
        "pontos_maximos",
        "media_pontos",
        "menor_nota",
        "maior_nota",
        "aproveitamento_percentual",
        "acertos",
        "erros",
        "em_branco",
        "multiplas",
        "distribuicao_respostas"
    ]

    with destino.open(
        "x", encoding="utf-8-sig", newline=""
    ) as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=campos,
            delimiter=";"
        )

        escritor.writeheader()

        for item in analises:
            escritor.writerow({
                "avaliacao_id": avaliacao_id,
                "turma": turma,
                "questao": item["numero"],
                "tipo": item["tipo"],
                "alunos_analisados": item["quantidade"],
                "pontos_maximos": csv_numero(item["maximo"]),
                "media_pontos": csv_numero(item["media"]),
                "menor_nota": csv_numero(item["menor"]),
                "maior_nota": csv_numero(item["maior"]),
                "aproveitamento_percentual": csv_numero(
                    item["aproveitamento"]
                ),
                "acertos": (
                    item["acertos"]
                    if item["acertos"] is not None else ""
                ),
                "erros": (
                    item["erros"]
                    if item["erros"] is not None else ""
                ),
                "em_branco": (
                    item["brancos"]
                    if item["brancos"] is not None else ""
                ),
                "multiplas": (
                    item["multiplas"]
                    if item["multiplas"] is not None else ""
                ),
                "distribuicao_respostas": json.dumps(
                    item["respostas"],
                    ensure_ascii=False
                )
            })

    return destino


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    avaliacao = carregar_json(ARQ_AVALIACAO)
    cadastro = carregar_json(ARQ_ALUNOS)

    avaliacao_id, definicoes = preparar_avaliacao(
        avaliacao
    )

    turma = avaliacao.get("turma", "")

    if cadastro.get("turma") != turma:
        raise ValueError(
            "Turma incompatível com o cadastro"
        )

    alunos = cadastro.get("alunos")

    if not isinstance(alunos, list):
        raise ValueError(
            "Lista de alunos inválida"
        )

    correcoes = []
    pendentes = 0
    ausentes = 0
    erros = []
    ids_vistos = set()

    for aluno in alunos:
        aluno_id = identificador(
            aluno.get("id"), "Aluno"
        )

        if aluno_id in ids_vistos:
            erros.append(
                f"{aluno_id}: cadastro duplicado"
            )
            continue

        ids_vistos.add(aluno_id)

        caminho = (
            RESULTADOS
            / avaliacao_id
            / aluno_id
            / "resultado_correcao.json"
        )

        if not caminho.exists():
            ausentes += 1
            continue

        try:
            dados = carregar_json(caminho)

            situacao, questoes = validar_correcao(
                dados,
                avaliacao_id,
                aluno,
                definicoes
            )

            if situacao == "finalizada":
                correcoes.append(questoes)
            else:
                pendentes += 1

        except (
            ValueError, KeyError, TypeError,
            OSError, json.JSONDecodeError
        ) as erro:
            erros.append(
                f"{aluno_id}: {erro}"
            )

    if erros:
        print(
            "\nANÁLISE BLOQUEADA: "
            "foram encontradas inconsistências."
        )

        for erro in erros:
            print(" -", erro)

        print(
            "\nNenhum relatório foi gerado."
        )
        return

    analises = [
        analisar_questao(n, definicao, correcoes)
        for n, definicao in sorted(
            definicoes.items()
        )
    ]

    mostrar_resultados(
        avaliacao_id,
        turma,
        len(alunos),
        correcoes,
        pendentes,
        ausentes,
        analises
    )

    if not correcoes:
        print(
            "\nSem correções finalizadas. "
            "CSV não gerado."
        )
        return

    destino = exportar_csv(
        avaliacao_id, turma, analises
    )

    print("\nRELATÓRIO CSV GERADO")
    print("-" * 72)
    print(destino)

    print(
        "\nNenhuma correção ou histórico "
        "foi modificado."
    )


if __name__ == "__main__":
    try:
        main()
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
