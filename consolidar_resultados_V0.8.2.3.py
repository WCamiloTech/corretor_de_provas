
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import mean
from uuid import NAMESPACE_URL, uuid5

from corrigir_avaliacao import carregar_turma

# ============================================================
# CONFIGURAÇÕES — V0.7.1
# ============================================================

BASE = Path(__file__).resolve().parent

RESULTADOS = BASE / "resultados"
AVALIACAO = BASE / "avaliacao.json"
ALUNOS = BASE / "alunos.json"


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def ler_json(caminho):
    with caminho.open(
        "r", encoding="utf-8-sig"
    ) as arquivo:
        return json.load(arquivo)


def numero(valor, campo):
    if (
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(valor)
    ):
        raise ValueError(
            f"{campo}: valor numérico inválido"
        )

    return float(valor)


def identificar_avaliacao(dados):
    identificador = dados.get(
        "id", dados.get("avaliacao_id")
    )

    if (
        not isinstance(identificador, str)
        or not identificador
        or "/" in identificador
        or "\\" in identificador
        or identificador in (".", "..")
    ):
        raise ValueError(
            "Identificador da avaliação inválido"
        )

    return identificador


def validar_correcao(
    dados, avaliacao_id, aluno, maximo
):
    aluno_id = aluno["id"]

    esperado = str(
        uuid5(
            NAMESPACE_URL,
            f"{avaliacao_id}:{aluno_id}"
        )
    )

    if (
        dados.get("avaliacao_id") != avaliacao_id
        or dados.get("aluno_id") != aluno_id
        or dados.get("cartao_id") != esperado
    ):
        raise ValueError(
            "Identificação da avaliação, "
            "aluno ou UUID incompatível"
        )

    if dados.get("aluno_nome") != aluno["nome"]:
        raise ValueError(
            "Nome do aluno incompatível"
        )

    possiveis = numero(
        dados.get("pontos_possiveis"),
        "pontos_possiveis"
    )

    confirmados = numero(
        dados.get("pontos_confirmados"),
        "pontos_confirmados"
    )

    if (
        not math.isclose(
            possiveis, maximo, abs_tol=0.001
        )
        or not 0 <= confirmados <= maximo
    ):
        raise ValueError(
            "Pontuação máxima ou confirmada "
            "inconsistente"
        )

    questoes = dados.get("questoes")

    if (
        not isinstance(questoes, list)
        or len(questoes) == 0
    ):
        raise ValueError(
            "Lista de questões inválida"
        )

    soma = sum(
        numero(
            q.get("pontos_obtidos"),
            "pontos_obtidos"
        )
        for q in questoes
        if q.get("pontos_obtidos") is not None
    )

    if not math.isclose(
        soma, confirmados, abs_tol=0.001
    ):
        raise ValueError(
            "Soma das questões diferente "
            "dos pontos confirmados"
        )

    status = dados.get("status")

    if status == "finalizada":
        if dados.get("pendencias"):
            raise ValueError(
                "Correção finalizada com pendências"
            )

        nota = numero(
            dados.get("nota_final"),
            "nota_final"
        )

        if not math.isclose(
            nota, confirmados, abs_tol=0.001
        ):
            raise ValueError(
                "Nota final diferente "
                "dos pontos confirmados"
            )

        return "finalizada", nota, confirmados

    if status in (
        "pendente",
        "em_correcao",
        "em andamento"
    ):
        if dados.get("nota_final") is not None:
            raise ValueError(
                "Correção pendente possui nota final"
            )

        return "pendente", None, confirmados

    raise ValueError(
        f"Situação de correção desconhecida: "
        f"{status!r}"
    )


def formatar(valor):
    if valor is None:
        return ""

    return f"{valor:.2f}".replace(".", ",")


# ============================================================
# CONSOLIDAÇÃO DOS RESULTADOS
# ============================================================

def main():
    avaliacao, alunos = carregar_turma()

    avaliacao_id = identificar_avaliacao(
        avaliacao
    )

    turma = avaliacao.get("turma", "")

    questoes = avaliacao.get("questoes")

    if (
        not isinstance(questoes, list)
        or not questoes
    ):
        raise ValueError(
            "Avaliação sem questões"
        )

    maximo = sum(
        numero(
            q.get("pontos"),
            "pontos da questão"
        )
        for q in questoes
    )

    if maximo <= 0:
        raise ValueError(
            "Pontuação máxima deve ser positiva"
        )

    registros = []
    vistos = set()
    erros = []

    for aluno in alunos:
        aluno_id = aluno["id"]

        if aluno_id in vistos:
            erros.append(
                f"{aluno_id}: aluno duplicado "
                "no cadastro"
            )
            continue

        vistos.add(aluno_id)

        caminho = (
            RESULTADOS
            / avaliacao_id
            / aluno_id
            / "resultado_correcao.json"
        )

        registro = {
            "aluno_id": aluno_id,
            "nome": aluno["nome"],
            "situacao": "sem_correcao",
            "nota": None,
            "confirmados": None
        }

        if caminho.exists():
            try:
                dados = ler_json(caminho)

                (
                    registro["situacao"],
                    registro["nota"],
                    registro["confirmados"]
                ) = validar_correcao(
                    dados,
                    avaliacao_id,
                    aluno,
                    maximo
                )

            except (
                ValueError,
                TypeError,
                KeyError,
                OSError,
                json.JSONDecodeError
            ) as erro:
                erros.append(
                    f"{aluno_id}: {erro}"
                )

                registro["situacao"] = (
                    "inconsistente"
                )

        registros.append(registro)

    # ========================================================
    # EXIBIÇÃO DOS RESULTADOS
    # ========================================================

    print(
        "\nCONSOLIDAÇÃO DE RESULTADOS — V0.8.2.3"
    )
    print("=" * 68)

    print(
        f"Avaliação: {avaliacao_id} | "
        f"Turma: {turma} | "
        f"Máximo: {maximo:g}"
    )

    print("-" * 68)

    for registro in registros:
        if registro["nota"] is not None:
            nota = (
                f"{registro['nota']:.2f}"
                f"/{maximo:g}"
            )
        else:
            nota = "-"

        print(
            f"{registro['aluno_id']:<12} | "
            f"{registro['situacao']:<14} | "
            f"{nota}"
        )

    # ========================================================
    # ESTATÍSTICAS DA TURMA
    # ========================================================

    notas = [
        registro["nota"]
        for registro in registros
        if registro["situacao"] == "finalizada"
    ]

    print("\nESTATÍSTICAS")
    print("-" * 68)

    print(
        f"Participantes da avaliação: {len(registros)}"
    )

    print(
        f"Finalizadas: {len(notas)}"
    )

    print(
        "Pendentes:",
        sum(
            registro["situacao"] == "pendente"
            for registro in registros
        )
    )

    print(
        "Sem correção:",
        sum(
            registro["situacao"] == "sem_correcao"
            for registro in registros
        )
    )

    print(
        "Inconsistentes:",
        sum(
            registro["situacao"] == "inconsistente"
            for registro in registros
        )
    )

    if notas:
        media = mean(notas)
        media_100 = media / maximo * 100

        print(
            f"Média: {media:.2f}/{maximo:g} "
            f"({media_100:.2f}/100)"
        )

        print(
            f"Maior nota: {max(notas):.2f} | "
            f"Menor nota: {min(notas):.2f}"
        )

    # ========================================================
    # BLOQUEIO POR INCONSISTÊNCIAS
    # ========================================================

    if erros:
        print(
            "\nEXPORTAÇÃO BLOQUEADA: "
            "inconsistências encontradas."
        )

        for erro in erros:
            print(" -", erro)

        return

    # ========================================================
    # EXPORTAÇÃO PARA CSV
    # ========================================================

    pasta = (
        RESULTADOS
        / avaliacao_id
        / "relatorios"
    )

    pasta.mkdir(
        parents=True,
        exist_ok=True
    )

    momento = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    destino = (
        pasta
        / f"consolidado_{momento}.csv"
    )

    with destino.open(
        "x",
        newline="",
        encoding="utf-8-sig"
    ) as arquivo:
        escritor = csv.writer(
            arquivo,
            delimiter=";"
        )

        escritor.writerow([
            "avaliacao_id",
            "turma",
            "aluno_id",
            "aluno_nome",
            "situacao",
            "nota_original",
            "pontuacao_maxima",
            "nota_100",
            "pontos_confirmados"
        ])

        for registro in registros:
            nota = registro["nota"]

            if nota is not None:
                nota_100 = nota / maximo * 100
            else:
                nota_100 = None

            escritor.writerow([
                avaliacao_id,
                turma,
                registro["aluno_id"],
                registro["nome"],
                registro["situacao"],
                formatar(nota),
                formatar(maximo),
                formatar(nota_100),
                formatar(registro["confirmados"])
            ])

    print("\nCSV GERADO COM SUCESSO")
    print(destino)

    print(
        "Nenhuma correção ou histórico "
        "foi modificado."
    )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    try:
        main()

    except (
        FileNotFoundError,
        ValueError,
        TypeError,
        KeyError,
        OSError,
        json.JSONDecodeError
    ) as erro:
        print(
            f"\nOperação interrompida: {erro}"
        )
