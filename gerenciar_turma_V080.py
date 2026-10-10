
import json
import os
import re
import shutil
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


# ============================================================
# GERENCIAMENTO DE TURMAS E ALUNOS — V0.8.1
# ============================================================

BASE = Path(__file__).resolve().parent
ARQ_ALUNOS = BASE / "alunos.json"
ARQ_AVALIACAO = BASE / "avaliacao.json"
RESULTADOS = BASE / "resultados"
BACKUPS = BASE / "backups" / "alunos"


def ler_json(caminho):
    with caminho.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def normalizar(valor):
    texto = unicodedata.normalize(
        "NFD", str(valor).strip().casefold()
    )
    return "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )


def confirmar(pergunta):
    resposta = input(
        f"{pergunta} (S/N): "
    ).strip().casefold()
    return resposta in ("s", "sim")


def validar_cadastro(dados):
    if not isinstance(dados, dict):
        raise ValueError("Cadastro deve ser um objeto JSON.")

    if not isinstance(dados.get("turma"), str):
        raise ValueError("Campo 'turma' inválido.")

    alunos = dados.get("alunos")
    if not isinstance(alunos, list):
        raise ValueError("Campo 'alunos' deve ser uma lista.")

    ids = set()

    for aluno in alunos:
        if not isinstance(aluno, dict):
            raise ValueError("Registro de aluno inválido.")

        aluno_id = aluno.get("id")
        nome = aluno.get("nome")

        if (
            not isinstance(aluno_id, str)
            or not re.fullmatch(r"ALUNO-\d+", aluno_id)
        ):
            raise ValueError(
                f"ID de aluno inválido: {aluno_id!r}"
            )

        if (
            not isinstance(nome, str)
            or not nome.strip()
        ):
            raise ValueError(
                f"Nome inválido para {aluno_id}."
            )

        if (
            "ativo" in aluno
            and not isinstance(aluno["ativo"], bool)
        ):
            raise ValueError(
                f"Campo 'ativo' inválido: {aluno_id}"
            )

        if aluno_id in ids:
            raise ValueError(
                f"ID duplicado: {aluno_id}"
            )

        ids.add(aluno_id)

    return dados


def carregar_cadastro():
    if not ARQ_ALUNOS.is_file():
        raise FileNotFoundError(
            f"Cadastro não encontrado: {ARQ_ALUNOS}"
        )

    return validar_cadastro(
        ler_json(ARQ_ALUNOS)
    )


def obter_avaliacao_id():
    dados = ler_json(ARQ_AVALIACAO)

    avaliacao_id = (
        dados.get("id")
        or dados.get("avaliacao_id")
    )

    if (
        not isinstance(avaliacao_id, str)
        or not avaliacao_id
        or "/" in avaliacao_id
        or "\\" in avaliacao_id
        or avaliacao_id in (".", "..")
    ):
        raise ValueError(
            "ID da avaliação inválido."
        )

    return avaliacao_id


def salvar_cadastro(dados):
    """
    Valida, cria backup e substitui o JSON
    de forma atômica, no mesmo diretório.
    """
    validar_cadastro(dados)

    # Garante que o JSON possa ser serializado
    conteudo = json.dumps(
        dados,
        ensure_ascii=False,
        indent=2
    ) + "\n"

    BACKUPS.mkdir(
        parents=True,
        exist_ok=True
    )

    instante = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    backup = BACKUPS / (
        f"alunos_{instante}.json"
    )

    shutil.copy2(ARQ_ALUNOS, backup)

    temporario = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=BASE,
            prefix=".alunos_",
            suffix=".tmp",
            delete=False
        ) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())

        # Confirma que o novo conteúdo é válido
        validar_cadastro(
            ler_json(temporario)
        )

        os.replace(
            temporario,
            ARQ_ALUNOS
        )

    finally:
        if (
            temporario is not None
            and temporario.exists()
        ):
            temporario.unlink()

    print("\nCadastro atualizado com sucesso.")
    print(f"Backup criado: {backup}")


def alunos_ordenados(cadastro):
    return sorted(
        cadastro["alunos"],
        key=lambda a: normalizar(a["nome"])
    )


def situacao_aluno(aluno):
    return (
        "Ativo"
        if aluno.get("ativo", True)
        else "Inativo"
    )


def imprimir_alunos(alunos):
    if not alunos:
        print("\nNenhum aluno encontrado.")
        return

    print("\n" + "-" * 78)
    print(
        f"{'Nº':<5}"
        f"{'ID':<16}"
        f"{'NOME':<43}"
        f"{'SITUAÇÃO'}"
    )
    print("-" * 78)

    for indice, aluno in enumerate(
        alunos, start=1
    ):
        print(
            f"{indice:<5}"
            f"{aluno['id']:<16}"
            f"{aluno['nome'][:42]:<43}"
            f"{situacao_aluno(aluno)}"
        )

    print("-" * 78)


def selecionar_aluno(cadastro):
    alunos = alunos_ordenados(cadastro)

    while True:
        print("\nPESQUISAR ALUNO")
        print("Enter - Listar todos")
        print("0 - Cancelar")

        pesquisa = input(
            "Nome ou ID: "
        ).strip()

        if pesquisa == "0":
            return None

        termo = normalizar(pesquisa)

        encontrados = [
            a for a in alunos
            if (
                termo in normalizar(a["nome"])
                or termo in normalizar(a["id"])
            )
        ]

        if not encontrados:
            print("Nenhum aluno encontrado.")
            continue

        imprimir_alunos(encontrados)

        while True:
            escolha = input(
                "Número do aluno "
                "(0 para nova pesquisa): "
            ).strip()

            if escolha == "0":
                break

            if (
                escolha.isdigit()
                and 1 <= int(escolha) <= len(encontrados)
            ):
                return encontrados[
                    int(escolha) - 1
                ]

            print("Seleção inválida.")


def listar_alunos(cadastro):
    imprimir_alunos(
        alunos_ordenados(cadastro)
    )


def proximo_id(cadastro):
    numeros = [
        int(a["id"].split("-")[1])
        for a in cadastro["alunos"]
    ]

    proximo = max(
        numeros,
        default=0
    ) + 1

    return f"ALUNO-{proximo:03d}"


def cadastrar_aluno(cadastro):
    print("\nCADASTRAR ALUNO")

    nome = " ".join(
        input("Nome completo: ").strip().split()
    )

    if not nome:
        print("Cadastro cancelado: nome vazio.")
        return

    if any(
        normalizar(a["nome"]) == normalizar(nome)
        for a in cadastro["alunos"]
    ):
        print(
            "Já existe um aluno com esse nome."
        )
        return

    aluno_id = proximo_id(cadastro)

    print(f"\nID gerado: {aluno_id}")
    print(f"Nome: {nome}")
    print("Situação: Ativo")

    if not confirmar("Confirmar cadastro?"):
        print("Operação cancelada.")
        return

    novo = {
        "id": aluno_id,
        "nome": nome,
        "ativo": True
    }

    cadastro["alunos"].append(novo)

    try:
        salvar_cadastro(cadastro)
    except Exception:
        cadastro["alunos"].remove(novo)
        raise


def possui_vinculos(aluno_id):
    """
    Verifica registros que podem depender do nome
    ou ID do aluno.

    Na dúvida, bloqueia a edição para preservar
    a integridade dos dados existentes.
    """
    avaliacao_id = obter_avaliacao_id()

    pasta_aluno = (
        RESULTADOS
        / avaliacao_id
        / aluno_id
    )

    if pasta_aluno.exists():
        # Uma pasta existente já indica que o
        # aluno pode ter registros vinculados.
        return True

    cartao_id = str(
        uuid5(
            NAMESPACE_URL,
            f"{avaliacao_id}:{aluno_id}"
        )
    )

    # Procura referências em arquivos gerados.
    for nome_pasta in (
        "cartoes",
        "cartoes_teste_v06"
    ):
        pasta = BASE / nome_pasta

        if not pasta.is_dir():
            continue

        for arquivo in pasta.rglob("*"):
            if not arquivo.is_file():
                continue

            if (
                aluno_id.casefold()
                in arquivo.name.casefold()
                or cartao_id.casefold()
                in arquivo.name.casefold()
            ):
                return True

            if arquivo.suffix.lower() == ".json":
                try:
                    conteudo = arquivo.read_text(
                        encoding="utf-8-sig"
                    )
                except (OSError, UnicodeError):
                    # Não assumir que está livre
                    # quando não foi possível verificar.
                    return True

                if (
                    aluno_id in conteudo
                    or cartao_id in conteudo
                ):
                    return True

    return False


def editar_aluno(cadastro):
    print("\nEDITAR DADOS CADASTRAIS")

    aluno = selecionar_aluno(cadastro)

    if aluno is None:
        return

    print(
        f"\nAluno: {aluno['nome']}"
    )
    print(
        f"ID: {aluno['id']} (não editável)"
    )

    if possui_vinculos(aluno["id"]):
        print(
            "\nEdição bloqueada: existem registros "
            "ou pastas vinculados a esse aluno."
        )
        print(
            "Nenhum dado foi modificado."
        )
        return

    novo_nome = " ".join(
        input("Novo nome: ").strip().split()
    )

    if not novo_nome:
        print("Operação cancelada.")
        return

    if any(
        a["id"] != aluno["id"]
        and normalizar(a["nome"]) == normalizar(novo_nome)
        for a in cadastro["alunos"]
    ):
        print("Nome já cadastrado.")
        return

    if novo_nome == aluno["nome"]:
        print("Nenhuma alteração necessária.")
        return

    print(f"Nome anterior: {aluno['nome']}")
    print(f"Novo nome: {novo_nome}")

    if not confirmar("Confirmar alteração?"):
        return

    anterior = aluno["nome"]
    aluno["nome"] = novo_nome

    try:
        salvar_cadastro(cadastro)
    except Exception:
        aluno["nome"] = anterior
        raise


def alterar_atividade(cadastro, ativo):
    acao = "REATIVAR" if ativo else "DESATIVAR"
    print(f"\n{acao} ALUNO")

    aluno = selecionar_aluno(cadastro)

    if aluno is None:
        return

    atual = aluno.get("ativo", True)

    if atual == ativo:
        print(
            "O aluno já está nessa situação."
        )
        return

    print(f"\nAluno: {aluno['nome']}")
    print(f"ID: {aluno['id']}")
    print(
        "Nenhum histórico ou resultado será excluído."
    )

    print(
        "A situação 'ativo' ainda não é aplicada "
        "automaticamente pelos outros módulos."
    )

    if not confirmar(
        f"Confirmar {acao.lower()}?"
    ):
        return

    tinha_campo = "ativo" in aluno
    valor_anterior = aluno.get("ativo")

    aluno["ativo"] = ativo

    try:
        salvar_cadastro(cadastro)
    except Exception:
        if tinha_campo:
            aluno["ativo"] = valor_anterior
        else:
            aluno.pop("ativo", None)
        raise


def preparar_pastas(cadastro):
    avaliacao_id = obter_avaliacao_id()
    raiz = RESULTADOS / avaliacao_id

    alunos = cadastro["alunos"]

    print("\nPREPARAR PASTAS DOS ALUNOS")
    print(f"Avaliação: {avaliacao_id}")
    print(f"Alunos cadastrados: {len(alunos)}")

    print(
        "A operação não apagará arquivos existentes."
    )

    if not confirmar("Continuar?"):
        return

    criadas = 0
    existentes = 0

    for aluno in alunos:
        pasta = raiz / aluno["id"]

        if pasta.is_dir():
            existentes += 1
        else:
            pasta.mkdir(
                parents=True,
                exist_ok=True
            )
            criadas += 1

    print(f"\nPastas criadas: {criadas}")
    print(f"Pastas já existentes: {existentes}")


def listar_correcoes(cadastro):
    avaliacao_id = obter_avaliacao_id()

    print("\nSITUAÇÃO DAS CORREÇÕES")
    print("-" * 78)

    print(
        f"{'ID':<16}"
        f"{'NOME':<35}"
        f"{'CORREÇÃO'}"
    )

    print("-" * 78)

    for aluno in alunos_ordenados(cadastro):
        caminho = (
            RESULTADOS
            / avaliacao_id
            / aluno["id"]
            / "resultado_correcao.json"
        )

        if not caminho.is_file():
            situacao = "Sem correção"
        else:
            try:
                dados = ler_json(caminho)

                if (
                    dados.get("avaliacao_id") != avaliacao_id
                    or dados.get("aluno_id") != aluno["id"]
                    or dados.get("aluno_nome") != aluno["nome"]
                ):
                    situacao = "Inconsistente"
                else:
                    situacao = str(
                        dados.get("status", "Sem status")
                    )
            except (OSError, ValueError, TypeError):
                situacao = "Erro de leitura"

        print(
            f"{aluno['id']:<16}"
            f"{aluno['nome'][:34]:<35}"
            f"{situacao}"
        )

    print("-" * 78)
    print(
        "Consulta informativa; não substitui "
        "a consolidação e validação das notas."
    )


def informacoes_turma(cadastro):
    alunos = cadastro["alunos"]

    ativos = sum(
        a.get("ativo", True)
        for a in alunos
    )

    print("\nINFORMAÇÕES DA TURMA")
    print("-" * 55)

    print(f"Turma: {cadastro['turma']}")
    print(f"Total cadastrado: {len(alunos)}")
    print(f"Alunos ativos: {ativos}")
    print(
        f"Alunos inativos: {len(alunos) - ativos}"
    )

    try:
        print(
            f"Avaliação: {obter_avaliacao_id()}"
        )
    except (OSError, ValueError, TypeError):
        print("Avaliação: não identificada")

    print(f"Cadastro: {ARQ_ALUNOS}")
    print(f"Backups: {BACKUPS}")


def menu():
    while True:
        cadastro = carregar_cadastro()

        print("\n" + "=" * 64)
        print("GERENCIAMENTO DE TURMA — V0.8.1")
        print("=" * 64)

        print(f"Turma: {cadastro['turma']}")
        print(
            f"Alunos cadastrados: "
            f"{len(cadastro['alunos'])}"
        )

        print("\n1 - Listar alunos")
        print("2 - Pesquisar aluno")
        print("3 - Cadastrar novo aluno")
        print("4 - Editar dados cadastrais")
        print("5 - Desativar aluno")
        print("6 - Reativar aluno")
        print("7 - Preparar pastas dos alunos")
        print("8 - Listar situação das correções")
        print("9 - Consultar informações da turma")
        print("0 - Voltar ao menu principal")

        opcao = input(
            "\nEscolha uma opção: "
        ).strip()

        if opcao == "0":
            print("Retornando ao menu principal...")
            return

        try:
            if opcao == "1":
                listar_alunos(cadastro)

            elif opcao == "2":
                aluno = selecionar_aluno(cadastro)

                if aluno:
                    print(
                        f"\nID: {aluno['id']}"
                    )
                    print(
                        f"Nome: {aluno['nome']}"
                    )
                    print(
                        f"Situação: {situacao_aluno(aluno)}"
                    )

            elif opcao == "3":
                cadastrar_aluno(cadastro)

            elif opcao == "4":
                editar_aluno(cadastro)

            elif opcao == "5":
                alterar_atividade(
                    cadastro, False
                )

            elif opcao == "6":
                alterar_atividade(
                    cadastro, True
                )

            elif opcao == "7":
                preparar_pastas(cadastro)

            elif opcao == "8":
                listar_correcoes(cadastro)

            elif opcao == "9":
                informacoes_turma(cadastro)

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
        menu()
    except (OSError, ValueError, TypeError) as erro:
        print(f"\nErro ao iniciar: {erro}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nGerenciamento interrompido.")
