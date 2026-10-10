
import json
import math
import os
import subprocess
import sys
import unicodedata
from pathlib import Path


# ============================================================
# SISTEMA DE CORREÇÃO DE AVALIAÇÕES
# V0.8.0 — MENU PRINCIPAL REFINADO
# ============================================================

VERSAO = "0.8.0"

BASE = Path(__file__).resolve().parent

ARQ_AVALIACAO = BASE / "avaliacao.json"
ARQ_ALUNOS = BASE / "alunos.json"
PASTA_RESULTADOS = BASE / "resultados"


# ============================================================
# CONFIGURAÇÃO DOS MÓDULOS
# ============================================================

MODULOS = {
    "1": {
        "titulo": "Gerenciar turma e alunos",
        "arquivo": "gerenciar_turma.py",
    },
    "2": {
        "titulo": "Gerar cartões de respostas",
        "arquivo": "gerar_cartao.py",
    },
    "3": {
        "titulo": "Ler cartões de respostas",
        "arquivo": "leitor_cartao.py",
    },
    "4": {
        "titulo": "Corrigir avaliações",
        "arquivo": "corrigir_avaliacao.py",
    },
    "6": {
        "titulo": "Consolidar resultados da turma",
        "arquivo": "consolidar_resultados.py",
    },
    "7": {
        "titulo": "Analisar desempenho por questão",
        "arquivo": "analisar_questoes.py",
    },
    "8": {
        "titulo": "Gerar relatórios individuais",
        "arquivo": "gerar_relatorios_individuais.py",
    },
}


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def limpar_tela():
    comando = "cls" if os.name == "nt" else "clear"
    os.system(comando)


def pausar():
    input(
        "\nPressione Enter para voltar "
        "ao menu principal..."
    )


def carregar_json(caminho):
    with caminho.open(
        "r", encoding="utf-8-sig"
    ) as arquivo:
        return json.load(arquivo)


def normalizar_texto(valor):
    """
    Remove diferenças entre maiúsculas, minúsculas
    e acentos durante a pesquisa.
    """
    valor = str(valor).strip().casefold()

    valor = unicodedata.normalize(
        "NFD", valor
    )

    return "".join(
        caractere
        for caractere in valor
        if unicodedata.category(caractere) != "Mn"
    )


def formatar_nota(valor):
    if (
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(valor)
    ):
        return "-"

    return f"{valor:.2f}".replace(".", ",")


def obter_contexto():
    contexto = {
        "avaliacao_id": "Não identificada",
        "turma": "Não identificada",
        "alunos": 0,
        "avisos": [],
    }

    try:
        avaliacao = carregar_json(
            ARQ_AVALIACAO
        )

        contexto["avaliacao_id"] = (
            avaliacao.get("id")
            or avaliacao.get("avaliacao_id")
            or "Não identificada"
        )

        contexto["turma"] = (
            avaliacao.get("turma")
            or "Não identificada"
        )

    except (OSError, ValueError, TypeError) as erro:
        contexto["avisos"].append(
            f"Erro ao ler avaliacao.json: {erro}"
        )

    try:
        cadastro = carregar_json(
            ARQ_ALUNOS
        )

        alunos = cadastro.get("alunos", [])

        if isinstance(alunos, list):
            contexto["alunos"] = len(alunos)

        turma_cadastro = cadastro.get("turma")

        if (
            turma_cadastro
            and contexto["turma"] != "Não identificada"
            and turma_cadastro != contexto["turma"]
        ):
            contexto["avisos"].append(
                "A turma de alunos.json é diferente "
                "da turma da avaliação."
            )

    except (OSError, ValueError, TypeError) as erro:
        contexto["avisos"].append(
            f"Erro ao ler alunos.json: {erro}"
        )

    return contexto


def carregar_alunos():
    cadastro = carregar_json(ARQ_ALUNOS)
    alunos = cadastro.get("alunos")

    if not isinstance(alunos, list):
        raise ValueError(
            "O cadastro de alunos é inválido."
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
            or not aluno_id
            or not isinstance(nome, str)
            or not nome.strip()
        ):
            raise ValueError(
                "Aluno sem ID ou nome válido."
            )

        if aluno_id in ids:
            raise ValueError(
                f"ID duplicado: {aluno_id}"
            )

        ids.add(aluno_id)

    return alunos


# ============================================================
# PESQUISA E SELEÇÃO DE ALUNOS
# ============================================================

def selecionar_aluno(alunos):
    """
    Permite pesquisar pelo nome ou ID.

    Enter lista todos os alunos.
    0 cancela a seleção.
    """

    ordenados = sorted(
        alunos,
        key=lambda aluno: normalizar_texto(
            aluno["nome"]
        )
    )

    while True:
        print("\nLOCALIZAR ALUNO")
        print("-" * 70)
        print("Digite parte do nome ou ID do aluno.")
        print("Pressione Enter para listar todos.")
        print("Digite 0 para cancelar.")

        pesquisa = input(
            "\nPesquisar aluno: "
        ).strip()

        if pesquisa == "0":
            return None

        termo = normalizar_texto(pesquisa)

        encontrados = [
            aluno
            for aluno in ordenados
            if (
                termo in normalizar_texto(
                    aluno["nome"]
                )
                or termo in normalizar_texto(
                    aluno["id"]
                )
            )
        ]

        if not encontrados:
            print(
                "\nNenhum aluno encontrado."
            )
            continue

        print("\nRESULTADOS ENCONTRADOS")
        print("-" * 70)

        print(
            f"{'Nº':<5}"
            f"{'ID':<16}"
            f"{'NOME'}"
        )

        print("-" * 70)

        for indice, aluno in enumerate(
            encontrados, start=1
        ):
            print(
                f"{indice:<5}"
                f"{aluno['id']:<16}"
                f"{aluno['nome']}"
            )

        while True:
            escolha = input(
                "\nSelecione o número do aluno "
                "(0 para voltar): "
            ).strip()

            if escolha == "0":
                break

            if not escolha.isdigit():
                print(
                    "Digite um número válido."
                )
                continue

            indice = int(escolha)

            if not 1 <= indice <= len(encontrados):
                print(
                    "Número fora da lista."
                )
                continue

            selecionado = encontrados[indice - 1]

            print(
                "\nAluno selecionado: "
                f"{selecionado['nome']} "
                f"({selecionado['id']})"
            )

            return selecionado


# ============================================================
# EXECUÇÃO DOS MÓDULOS
# ============================================================

def executar_modulo(opcao):
    modulo = MODULOS.get(opcao)

    if modulo is None:
        print(
            "\nMódulo não configurado."
        )
        return

    titulo = modulo["titulo"]
    arquivo = modulo["arquivo"]

    print("\n" + "=" * 64)
    print(titulo.upper())
    print("=" * 64)

    caminho = BASE / arquivo

    if not caminho.is_file():
        print(
            "\nArquivo do módulo não encontrado."
        )
        print(f"Esperado: {caminho}")
        return

    print(f"\nExecutando: {arquivo}")
    print("-" * 64)

    try:
        resultado = subprocess.run(
            [
                sys.executable,
                str(caminho),
            ],
            cwd=str(BASE),
            check=False,
        )

        print("\n" + "-" * 64)

        if resultado.returncode == 0:
            print(
                "O módulo retornou ao menu principal."
            )
            print(
                "Consulte as mensagens acima para "
                "verificar o resultado da operação."
            )
        else:
            print(
                "O módulo terminou com código "
                f"de saída {resultado.returncode}."
            )

            print(
                "Verifique as mensagens apresentadas "
                "durante a execução."
            )

    except KeyboardInterrupt:
        print(
            "\nExecução interrompida pelo usuário."
        )

    except OSError as erro:
        print(
            f"\nErro ao executar o módulo: {erro}"
        )


# ============================================================
# CONSULTA DE RESULTADOS
# ============================================================

def obter_resultado_aluno(
    avaliacao_id, aluno
):
    aluno_id = aluno["id"]

    caminho = (
        PASTA_RESULTADOS
        / avaliacao_id
        / aluno_id
        / "resultado_correcao.json"
    )

    if not caminho.is_file():
        return "Sem correção", "-"

    try:
        dados = carregar_json(caminho)

        if (
            dados.get("avaliacao_id") != avaliacao_id
            or dados.get("aluno_id") != aluno_id
            or dados.get("aluno_nome") != aluno["nome"]
        ):
            return "Inconsistente", "-"

        status = dados.get("status")

        if status == "pendente":
            return "Pendente", "-"

        if status != "finalizada":
            return "Inconsistente", "-"

        nota = dados.get("nota_final")
        maximo = dados.get("pontos_possiveis")

        if (
            isinstance(nota, bool)
            or isinstance(maximo, bool)
            or not isinstance(nota, (int, float))
            or not isinstance(maximo, (int, float))
            or not math.isfinite(nota)
            or not math.isfinite(maximo)
            or maximo <= 0
            or nota < 0
            or nota > maximo
        ):
            return "Inconsistente", "-"

        return (
            "Finalizada",
            f"{formatar_nota(nota)}/"
            f"{formatar_nota(maximo)}"
        )

    except (OSError, ValueError, TypeError):
        return "Erro de leitura", "-"


def consultar_resultados():
    contexto = obter_contexto()
    avaliacao_id = contexto["avaliacao_id"]

    if avaliacao_id == "Não identificada":
        print(
            "\nAvaliação não identificada."
        )
        return

    try:
        alunos = carregar_alunos()

    except (OSError, ValueError, TypeError) as erro:
        print(
            f"\nErro ao carregar alunos: {erro}"
        )
        return

    while True:
        print("\nCONSULTAR RESULTADOS")
        print("-" * 64)
        print("1 - Consultar todos os alunos")
        print("2 - Pesquisar um aluno")
        print("0 - Voltar ao menu principal")

        opcao = input(
            "\nEscolha uma opção: "
        ).strip()

        if opcao == "0":
            return

        if opcao == "1":
            selecionados = sorted(
                alunos,
                key=lambda aluno: normalizar_texto(
                    aluno["nome"]
                )
            )

        elif opcao == "2":
            aluno = selecionar_aluno(alunos)

            if aluno is None:
                continue

            selecionados = [aluno]

        else:
            print("Opção inválida.")
            continue

        print("\nRESULTADOS DOS ALUNOS")
        print("=" * 78)

        print(
            f"{'ID':<14}"
            f"{'NOME':<27}"
            f"{'SITUAÇÃO':<19}"
            f"{'NOTA':>14}"
        )

        print("-" * 78)

        for aluno in selecionados:
            situacao, nota = obter_resultado_aluno(
                avaliacao_id,
                aluno
            )

            print(
                f"{aluno['id']:<14}"
                f"{aluno['nome'][:26]:<27}"
                f"{situacao:<19}"
                f"{nota:>14}"
            )

        print("=" * 78)

        print(
            "\nConsulta informativa. "
            "Para validar os cálculos, "
            "utilize a opção 6 do menu principal."
        )


# ============================================================
# CONSULTA DE HISTÓRICO
# ============================================================

def consultar_historico():
    contexto = obter_contexto()
    avaliacao_id = contexto["avaliacao_id"]

    if avaliacao_id == "Não identificada":
        print(
            "\nAvaliação não identificada."
        )
        return

    try:
        alunos = carregar_alunos()

    except (OSError, ValueError, TypeError) as erro:
        print(
            f"\nErro ao carregar alunos: {erro}"
        )
        return

    while True:
        print("\nCONSULTAR HISTÓRICO")
        print("-" * 64)
        print("1 - Histórico de todos os alunos")
        print("2 - Pesquisar histórico de um aluno")
        print("0 - Voltar ao menu principal")

        opcao = input(
            "\nEscolha uma opção: "
        ).strip()

        if opcao == "0":
            return

        if opcao == "1":
            selecionados = sorted(
                alunos,
                key=lambda aluno: normalizar_texto(
                    aluno["nome"]
                )
            )

        elif opcao == "2":
            aluno = selecionar_aluno(alunos)

            if aluno is None:
                continue

            selecionados = [aluno]

        else:
            print("Opção inválida.")
            continue

        print("\nHISTÓRICO DE CORREÇÕES")
        print("=" * 70)

        total = 0

        for aluno in selecionados:
            aluno_id = aluno["id"]

            pasta = (
                PASTA_RESULTADOS
                / avaliacao_id
                / aluno_id
                / "historico"
            )

            print(
                f"\n{aluno_id} — {aluno['nome']}"
            )

            if not pasta.is_dir():
                print(
                    "  Nenhum histórico encontrado."
                )
                continue

            arquivos = sorted(
                pasta.glob("*.json")
            )

            if not arquivos:
                print(
                    "  Nenhum histórico encontrado."
                )
                continue

            for arquivo in arquivos:
                print(
                    f"  - {arquivo.name}"
                )
                total += 1

        print("\n" + "-" * 70)
        print(
            f"Arquivos históricos encontrados: "
            f"{total}"
        )

        print(
            "Consulta somente leitura. "
            "Nenhum histórico foi alterado."
        )


# ============================================================
# MENU PRINCIPAL
# ============================================================

def exibir_menu():
    contexto = obter_contexto()

    print("=" * 64)
    print(
        "SISTEMA DE CORREÇÃO DE AVALIAÇÕES".center(64)
    )
    print(
        f"VERSÃO {VERSAO}".center(64)
    )
    print("=" * 64)

    print(
        f"\nAvaliação: {contexto['avaliacao_id']}"
    )

    print(
        f"Turma: {contexto['turma']}"
    )

    print(
        f"Alunos cadastrados: {contexto['alunos']}"
    )

    if contexto["avisos"]:
        print("\nAVISOS:")

        for aviso in contexto["avisos"]:
            print(f" - {aviso}")

    print("\nMENU PRINCIPAL")
    print("-" * 64)

    print("1 - Gerenciar turma e alunos")
    print("2 - Gerar cartões de respostas")
    print("3 - Ler cartões de respostas")
    print("4 - Corrigir avaliações")
    print("5 - Consultar resultados dos alunos")
    print("6 - Consolidar resultados da turma")
    print("7 - Analisar desempenho por questão")
    print("8 - Gerar relatórios individuais")
    print("9 - Consultar histórico de correções")
    print("0 - Sair")

    print("-" * 64)


def main():
    while True:
        limpar_tela()
        exibir_menu()

        opcao = input(
            "\nEscolha uma opção: "
        ).strip()

        if opcao == "0":
            print(
                "\nEncerrando o sistema..."
            )
            break

        elif opcao in MODULOS:
            executar_modulo(opcao)
            pausar()

        elif opcao == "5":
            consultar_resultados()
            pausar()

        elif opcao == "9":
            consultar_historico()
            pausar()

        else:
            print(
                "\nOpção inválida."
            )
            pausar()


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print(
            "\n\nSistema encerrado pelo usuário."
        )
