
import json
import math
import shutil
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL


# ============================================================
# CONFIGURAÇÕES
# ============================================================

BASE = Path(__file__).resolve().parent

AVALIACAO = BASE / "avaliacao.json"
ALUNOS = BASE / "alunos.json"

ORIGEM = BASE / "resultados" / "resultado_correcao.json"
PASTA_RESULTADOS = BASE / "resultados"


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def carregar(caminho):
    if not caminho.is_file():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {caminho}"
        )

    with caminho.open("r", encoding="utf-8") as f:
        return json.load(f)


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def numero(valor, descricao):
    exigir(
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor),
        f"Valor numérico inválido: {descricao}"
    )
    return float(valor)


def igual(a, b):
    return math.isclose(
        a, b, rel_tol=0, abs_tol=0.001
    )


# ============================================================
# VALIDAÇÃO DA CORREÇÃO ANTIGA
# ============================================================

def validar_correcao(resultado, avaliacao, aluno, leitura):
    avaliacao_id = avaliacao["id"]
    aluno_id = aluno["id"]

    cartao_esperado = str(
        uuid5(
            NAMESPACE_URL,
            f"{avaliacao_id}:{aluno_id}"
        )
    )

    exigir(
        resultado.get("avaliacao_id") == avaliacao_id,
        "A correção pertence a outra avaliação."
    )

    exigir(
        resultado.get("aluno_id") == aluno_id,
        "A correção pertence a outro aluno."
    )

    exigir(
        resultado.get("cartao_id") == cartao_esperado,
        "UUID da correção incompatível."
    )

    exigir(
        leitura.get("avaliacao_id") == avaliacao_id,
        "A leitura pertence a outra avaliação."
    )

    exigir(
        leitura.get("aluno_id") == aluno_id,
        "A leitura pertence a outro aluno."
    )

    exigir(
        leitura.get("cartao_id") == cartao_esperado,
        "UUID da leitura incompatível."
    )

    exigir(
        resultado.get("aluno_nome") == aluno["nome"],
        "Nome do aluno divergente."
    )

    questoes = resultado.get("questoes")

    exigir(
        isinstance(questoes, list),
        "Lista de questões inválida."
    )

    definicoes = {
        q["numero"]: q
        for q in avaliacao["questoes"]
    }

    exigir(
        len(questoes) == len(definicoes),
        "Quantidade de questões incompatível."
    )

    numeros_encontrados = [
        q.get("numero") for q in questoes
    ]

    exigir(
        len(set(numeros_encontrados))
        == len(numeros_encontrados),
        "Existem questões duplicadas."
    )

    total = 0.0
    confirmados = 0.0
    pendencias = []

    for q in questoes:
        n = q["numero"]

        exigir(
            n in definicoes,
            f"Questão desconhecida: {n}"
        )

        definicao = definicoes[n]

        exigir(
            q.get("tipo") == definicao["tipo"],
            f"Tipo incompatível na questão {n}."
        )

        maximo = numero(
            definicao["pontos"],
            f"pontuação máxima da questão {n}"
        )

        registrado = numero(
            q["pontos_possiveis"],
            f"pontos possíveis da questão {n}"
        )

        exigir(
            igual(maximo, registrado),
            f"Pontuação máxima divergente na questão {n}."
        )

        total += maximo

        status = q.get("status")
        pontos = q.get("pontos_obtidos")

        if status in ("pendente", "incerta"):
            exigir(
                pontos is None,
                f"Questão {n} pendente possui nota."
            )
            pendencias.append(n)
            continue

        pontos = numero(
            pontos,
            f"pontos obtidos da questão {n}"
        )

        exigir(
            0 <= pontos <= maximo,
            f"Nota fora do intervalo na questão {n}."
        )

        if q["tipo"] == "objetiva":
            exigir(
                q.get("gabarito") == definicao["gabarito"],
                f"Gabarito divergente na questão {n}."
            )

            alternativas = definicao["alternativas"]
            resposta = q.get("resposta")

            exigir(
                resposta is None or resposta in alternativas,
                f"Alternativa inválida na questão {n}."
            )

            exigir(
                status in (
                    "marcada",
                    "revisada",
                    "em_branco",
                    "multipla"
                ),
                f"Status objetivo inválido na questão {n}."
            )

            if status in ("em_branco", "multipla"):
                exigir(
                    resposta is None,
                    f"Resposta incompatível na questão {n}."
                )

            if status in ("marcada", "revisada"):
                exigir(
                    resposta in alternativas,
                    f"Resposta ausente na questão {n}."
                )

            pontos_esperados = (
                maximo
                if resposta == definicao["gabarito"]
                else 0.0
            )

            exigir(
                igual(pontos, pontos_esperados),
                f"Nota objetiva divergente na questão {n}."
            )

        else:
            exigir(
                status == "corrigida",
                f"Status discursivo inválido na questão {n}."
            )

        confirmados += pontos

    exigir(
        igual(
            numero(
                resultado["pontos_possiveis"],
                "pontos_possiveis"
            ),
            total
        ),
        "Total de pontos possíveis divergente."
    )

    exigir(
        igual(
            numero(
                resultado["pontos_confirmados"],
                "pontos_confirmados"
            ),
            confirmados
        ),
        "Total de pontos confirmados divergente."
    )

    exigir(
        set(resultado.get("pendencias", []))
        == set(pendencias),
        "Lista de pendências divergente."
    )

    status_esperado = (
        "pendente" if pendencias else "finalizada"
    )

    exigir(
        resultado.get("status") == status_esperado,
        "Situação da correção incompatível."
    )

    if pendencias:
        exigir(
            resultado.get("nota_final") is None,
            "Correção pendente possui nota final."
        )
    else:
        exigir(
            igual(
                numero(
                    resultado["nota_final"],
                    "nota_final"
                ),
                confirmados
            ),
            "Nota final divergente."
        )

    return total, confirmados, status_esperado


# ============================================================
# MIGRAÇÃO
# ============================================================

def main():
    print("\nMIGRAÇÃO DE CORREÇÃO LEGADA")
    print("=" * 50)

    avaliacao = carregar(AVALIACAO)
    cadastro = carregar(ALUNOS)
    resultado = carregar(ORIGEM)

    avaliacao_id = avaliacao["id"]
    aluno_id = resultado["aluno_id"]

    exigir(
        cadastro.get("turma") == avaliacao.get("turma"),
        "Turma incompatível."
    )

    alunos = [
        a for a in cadastro["alunos"]
        if a["id"] == aluno_id
    ]

    exigir(
        len(alunos) == 1,
        "Aluno não encontrado ou duplicado no cadastro."
    )

    aluno = alunos[0]

    destino_pasta = (
        PASTA_RESULTADOS
        / avaliacao_id
        / aluno_id
    )

    leitura_arquivo = (
        destino_pasta / "resultado_leitura.json"
    )

    destino = (
        destino_pasta / "resultado_correcao.json"
    )

    leitura = carregar(leitura_arquivo)

    total, confirmados, status = validar_correcao(
        resultado,
        avaliacao,
        aluno,
        leitura
    )

    print("\nVALIDAÇÃO")
    print("-" * 50)
    print("Avaliação:", avaliacao_id)
    print("Aluno:", aluno["nome"])
    print("ID:", aluno_id)
    print("UUID:", resultado["cartao_id"])
    print("Situação:", status)
    print("Pontuação:", f"{confirmados:g}/{total:g}")

    print("\nORIGEM")
    print(ORIGEM)

    print("\nDESTINO")
    print(destino)

    if destino.exists():
        print(
            "\nMIGRAÇÃO BLOQUEADA: "
            "já existe uma correção no destino."
        )
        return

    if not destino_pasta.is_dir():
        raise FileNotFoundError(
            "Pasta individual do aluno não encontrada."
        )

    print("\nSIMULAÇÃO CONCLUÍDA")
    print(
        "Todos os dados foram validados. "
        "Nenhum arquivo foi alterado."
    )

    confirmacao = input(
        "\nPara copiar a correção, digite MIGRAR "
        "(ou Enter para cancelar): "
    ).strip()

    if confirmacao != "MIGRAR":
        print("\nOperação cancelada. Nenhuma alteração.")
        return

    # Cópia exclusiva: nunca substitui o destino.
    with ORIGEM.open("rb") as fonte:
        with destino.open("xb") as saida:
            shutil.copyfileobj(fonte, saida)

    # Confere o conteúdo copiado.
    copia = carregar(destino)

    exigir(
        copia == resultado,
        "A cópia não corresponde ao arquivo original."
    )

    print("\nMIGRAÇÃO CONCLUÍDA")
    print("-" * 50)
    print("Arquivo original preservado.")
    print("Correção individual criada em:", destino)


if __name__ == "__main__":
    try:
        main()
    except (
        FileNotFoundError,
        FileExistsError,
        ValueError,
        KeyError,
        TypeError,
        OSError
    ) as erro:
        print(f"\nOperação interrompida: {erro}")
