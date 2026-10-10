
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path


# ============================================================
# GERENCIAMENTO DE PARTICIPANTES — V0.8.2.1
# ============================================================

BASE = Path(__file__).resolve().parent

ARQ_AVALIACAO = BASE / "avaliacao.json"
ARQ_ALUNOS = BASE / "alunos.json"
PASTA_RESULTADOS = BASE / "resultados"

SCHEMA_VERSION = 1


# ============================================================
# LEITURA E VALIDAÇÃO
# ============================================================

def ler_json(caminho):
    with caminho.open(
        "r", encoding="utf-8-sig"
    ) as arquivo:
        return json.load(arquivo)


def validar_identificador(valor, campo):
    if (
        not isinstance(valor, str)
        or not re.fullmatch(
            r"[A-Za-z0-9_-]+", valor
        )
    ):
        raise ValueError(
            f"{campo} inválido: {valor!r}"
        )

    return valor


def carregar_contexto():
    avaliacao = ler_json(ARQ_AVALIACAO)
    cadastro = ler_json(ARQ_ALUNOS)

    if not isinstance(avaliacao, dict):
        raise ValueError(
            "Estrutura da avaliação inválida."
        )

    if not isinstance(cadastro, dict):
        raise ValueError(
            "Estrutura do cadastro inválida."
        )

    avaliacao_id = validar_identificador(
        avaliacao.get("id"),
        "ID da avaliação"
    )

    turma = avaliacao.get("turma")

    if (
        not isinstance(turma, str)
        or not turma.strip()
    ):
        raise ValueError(
            "Turma da avaliação inválida."
        )

    if cadastro.get("turma") != turma:
        raise ValueError(
            "A turma do cadastro é diferente "
            "da turma da avaliação."
        )

    alunos = cadastro.get("alunos")

    if (
        not isinstance(alunos, list)
        or not alunos
    ):
        raise ValueError(
            "Nenhum aluno cadastrado."
        )

    ids = set()

    for aluno in alunos:
        if not isinstance(aluno, dict):
            raise ValueError(
                "Registro de aluno inválido."
            )

        aluno_id = validar_identificador(
            aluno.get("id"),
            "ID do aluno"
        )

        nome = aluno.get("nome")

        if (
            not isinstance(nome, str)
            or not nome.strip()
        ):
            raise ValueError(
                f"Nome inválido: {aluno_id}"
            )

        if (
            "ativo" in aluno
            and not isinstance(
                aluno["ativo"], bool
            )
        ):
            raise ValueError(
                f"Situação cadastral inválida: "
                f"{aluno_id}"
            )

        if aluno_id in ids:
            raise ValueError(
                f"ID duplicado: {aluno_id}"
            )

        ids.add(aluno_id)

    return avaliacao, cadastro


def caminho_participantes(avaliacao_id):
    return (
        PASTA_RESULTADOS
        / avaliacao_id
        / "participantes.json"
    )


def validar_participantes(
    dados, avaliacao, cadastro
):
    if not isinstance(dados, dict):
        raise ValueError(
            "Registro de participantes inválido."
        )

    if (
        type(dados.get("schema_version")) is not int
        or dados["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError(
            "Versão do registro não suportada."
        )

    if dados.get("avaliacao_id") != avaliacao["id"]:
        raise ValueError(
            "ID da avaliação não corresponde."
        )

    if dados.get("turma") != avaliacao["turma"]:
        raise ValueError(
            "Turma do registro não corresponde."
        )

    participantes = dados.get("participantes")

    if (
        not isinstance(participantes, list)
        or not participantes
    ):
        raise ValueError(
            "A avaliação deve possuir "
            "ao menos um participante."
        )

    cadastro_por_id = {
        aluno["id"]: aluno
        for aluno in cadastro["alunos"]
    }

    ids = set()

    for participante in participantes:
        if not isinstance(participante, dict):
            raise ValueError(
                "Participante inválido."
            )

        aluno_id = participante.get("aluno_id")
        nome = participante.get(
            "nome_na_avaliacao"
        )

        validar_identificador(
            aluno_id, "ID do participante"
        )

        if aluno_id in ids:
            raise ValueError(
                f"Participante duplicado: {aluno_id}"
            )

        if aluno_id not in cadastro_por_id:
            raise ValueError(
                f"Aluno não encontrado no cadastro: "
                f"{aluno_id}"
            )

        if (
            not isinstance(nome, str)
            or not nome.strip()
        ):
            raise ValueError(
                f"Nome inválido: {aluno_id}"
            )

        ids.add(aluno_id)

    return dados


# ============================================================
# EXIBIÇÃO
# ============================================================

def listar_alunos(cadastro):
    print("\nALUNOS CADASTRADOS")
    print("-" * 75)

    print(
        f"{'Nº':<5}"
        f"{'ID':<16}"
        f"{'NOME':<39}"
        f"{'CADASTRO'}"
    )

    print("-" * 75)

    for indice, aluno in enumerate(
        cadastro["alunos"], start=1
    ):
        situacao = (
            "Ativo"
            if aluno.get("ativo", True)
            else "Inativo"
        )

        print(
            f"{indice:<5}"
            f"{aluno['id']:<16}"
            f"{aluno['nome'][:38]:<39}"
            f"{situacao}"
        )

    print("-" * 75)


def mostrar_participantes(dados):
    print("\nPARTICIPANTES DA AVALIAÇÃO")
    print("=" * 70)

    print(
        f"Avaliação: {dados['avaliacao_id']}"
    )
    print(f"Turma: {dados['turma']}")
    print(
        f"Total: {len(dados['participantes'])}"
    )

    for participante in dados["participantes"]:
        print(
            f" - {participante['aluno_id']} "
            f"— {participante['nome_na_avaliacao']}"
        )

    print("=" * 70)


# ============================================================
# CRIAÇÃO SEGURA
# ============================================================

def salvar_sem_sobrescrever(caminho, dados):
    """
    Cria um arquivo novo sem substituir
    participantes.json já existente.
    """
    caminho.parent.mkdir(
        parents=True, exist_ok=True
    )

    conteudo = (
        json.dumps(
            dados,
            ensure_ascii=False,
            indent=2
        )
        + "\n"
    )

    # Modo 'x': falha se o arquivo já existir.
    with caminho.open(
        "x", encoding="utf-8"
    ) as arquivo:
        arquivo.write(conteudo)


def criar_registro(avaliacao, cadastro):
    avaliacao_id = avaliacao["id"]
    destino = caminho_participantes(
        avaliacao_id
    )

    if destino.exists():
        print(
            "\nO registro de participantes "
            "já existe."
        )
        print(
            "Nenhum arquivo será sobrescrito."
        )
        print(f"Arquivo: {destino}")
        return

    listar_alunos(cadastro)

    print(
        "\nInforme os IDs dos participantes "
        "separados por vírgula."
    )
    print(
        "Exemplo: "
        "ALUNO-001,ALUNO-002,ALUNO-003"
    )

    entrada = input(
        "\nParticipantes: "
    ).strip()

    ids_informados = [
        item.strip().upper()
        for item in entrada.split(",")
    ]

    if (
        not entrada
        or any(not item for item in ids_informados)
    ):
        print(
            "Seleção inválida. "
            "Nenhum arquivo foi criado."
        )
        return

    if len(ids_informados) != len(
        set(ids_informados)
    ):
        print(
            "Existem IDs repetidos na seleção."
        )
        return

    cadastro_por_id = {
        aluno["id"]: aluno
        for aluno in cadastro["alunos"]
    }

    desconhecidos = [
        aluno_id
        for aluno_id in ids_informados
        if aluno_id not in cadastro_por_id
    ]

    if desconhecidos:
        print(
            "IDs não encontrados: "
            + ", ".join(desconhecidos)
        )
        return

    participantes = [
        {
            "aluno_id": aluno_id,
            "nome_na_avaliacao": (
                cadastro_por_id[aluno_id]["nome"]
            )
        }
        for aluno_id in ids_informados
    ]

    dados = {
        "schema_version": SCHEMA_VERSION,
        "avaliacao_id": avaliacao_id,
        "turma": avaliacao["turma"],
        "criado_em": datetime.now().isoformat(
            timespec="seconds"
        ),
        "participantes": participantes
    }

    validar_participantes(
        dados, avaliacao, cadastro
    )

    mostrar_participantes(dados)

    print(
        "\nA situação cadastral atual não "
        "altera a participação histórica."
    )

    resposta = input(
        "\nConfirmar criação? (S/N): "
    ).strip().casefold()

    if resposta not in ("s", "sim"):
        print(
            "Operação cancelada."
        )
        return

    try:
        salvar_sem_sobrescrever(
            destino, dados
        )
    except FileExistsError:
        print(
            "O arquivo já existe. "
            "Nenhum dado foi substituído."
        )
        return

    print(
        "\nRegistro criado com sucesso!"
    )
    print(f"Arquivo: {destino}")
    print(
        "Cartões, leituras, correções e "
        "históricos não foram modificados."
    )


# ============================================================
# CONSULTA
# ============================================================

def consultar_registro(avaliacao, cadastro):
    caminho = caminho_participantes(
        avaliacao["id"]
    )

    if not caminho.is_file():
        print(
            "\nAinda não existe registro "
            "de participantes."
        )
        return

    dados = ler_json(caminho)

    validar_participantes(
        dados, avaliacao, cadastro
    )

    mostrar_participantes(dados)
    print(f"\nArquivo: {caminho}")
    print("Consulta somente leitura.")


# ============================================================
# MENU
# ============================================================

def main():
    while True:
        avaliacao, cadastro = carregar_contexto()

        caminho = caminho_participantes(
            avaliacao["id"]
        )

        print("\n" + "=" * 64)
        print(
            "GERENCIAMENTO DE PARTICIPANTES — V0.8.2.1"
        )
        print("=" * 64)

        print(
            f"Avaliação: {avaliacao['id']}"
        )
        print(
            f"Turma: {avaliacao['turma']}"
        )
        print(
            f"Alunos cadastrados: "
            f"{len(cadastro['alunos'])}"
        )

        print(
            "Registro de participantes: "
            + (
                "Existente"
                if caminho.is_file()
                else "Não criado"
            )
        )

        print("\n1 - Listar alunos cadastrados")
        print("2 - Criar registro de participantes")
        print("3 - Consultar participantes")
        print("0 - Sair")

        opcao = input(
            "\nEscolha uma opção: "
        ).strip()

        try:
            if opcao == "0":
                print(
                    "Retornando ao sistema..."
                )
                return

            elif opcao == "1":
                listar_alunos(cadastro)

            elif opcao == "2":
                criar_registro(
                    avaliacao, cadastro
                )

            elif opcao == "3":
                consultar_registro(
                    avaliacao, cadastro
                )

            else:
                print("Opção inválida.")

        except (
            OSError,
            ValueError,
            TypeError,
            KeyError
        ) as erro:
            print(
                f"\nOperação não concluída: {erro}"
            )


if __name__ == "__main__":
    try:
        main()

    except (
        OSError,
        ValueError,
        TypeError,
        KeyError
    ) as erro:
        print(
            f"\nErro ao iniciar: {erro}"
        )
        raise SystemExit(1)

    except KeyboardInterrupt:
        print(
            "\nGerenciamento interrompido."
        )
