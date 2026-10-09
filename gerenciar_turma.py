
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARQUIVO_AVALIACAO = BASE / "avaliacao.json"
ARQUIVO_ALUNOS = BASE / "alunos.json"

def carregar(caminho):
    with caminho.open("r", encoding="utf-8") as f:
        return json.load(f)

def identificador(valor):
    if not isinstance(valor, str):
        raise ValueError("Identificador inválido.")

    if not re.fullmatch(r"[A-Za-z0-9_-]+", valor):
        raise ValueError(
            f"Identificador não permitido: {valor}"
        )

    return valor

def pasta_aluno(avaliacao_id, aluno_id):
    avaliacao_id = identificador(avaliacao_id)
    aluno_id = identificador(aluno_id)

    return (
        BASE / "resultados" /
        avaliacao_id / aluno_id
    )

def preparar_turma():
    avaliacao = carregar(ARQUIVO_AVALIACAO)
    cadastro = carregar(ARQUIVO_ALUNOS)

    if cadastro["turma"] != avaliacao["turma"]:
        raise ValueError(
            "Turma do cadastro diferente da avaliação."
        )

    alunos = cadastro["alunos"]

    ids = [identificador(a["id"]) for a in alunos]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Existem IDs de alunos duplicados."
        )

    avaliacao_id = identificador(avaliacao["id"])

    print(f"\nAvaliação: {avaliacao_id}")
    print(f"Turma: {avaliacao['turma']}")
    print(f"Alunos cadastrados: {len(alunos)}")
    print("-" * 45)

    for aluno in alunos:
        destino = pasta_aluno(
            avaliacao_id, aluno["id"]
        )

        destino.mkdir(
            parents=True, exist_ok=True
        )

        (destino / "historico").mkdir(
            exist_ok=True
        )

        identificacao = {
            "avaliacao_id": avaliacao_id,
            "aluno_id": aluno["id"],
            "aluno_nome": aluno["nome"],
            "turma": avaliacao["turma"]
        }

        arquivo = destino / "identificacao.json"

        if arquivo.exists():
            anterior = carregar(arquivo)

            if anterior != identificacao:
                raise ValueError(
                    "Identificação divergente em "
                    f"{arquivo}. Verifique antes de alterar."
                )
        else:
            with arquivo.open(
                "w", encoding="utf-8"
            ) as f:
                json.dump(
                    identificacao,
                    f,
                    ensure_ascii=False,
                    indent=2
                )

        print(
            f"{aluno['id']} | {aluno['nome']}"
        )

    print("\nEstrutura preparada com sucesso.")

def listar_resultados():
    avaliacao = carregar(ARQUIVO_AVALIACAO)
    cadastro = carregar(ARQUIVO_ALUNOS)

    print("\nSITUAÇÃO DAS CORREÇÕES")
    print("-" * 55)

    for aluno in cadastro["alunos"]:
        pasta = pasta_aluno(
            avaliacao["id"], aluno["id"]
        )

        arquivo = pasta / "resultado_correcao.json"

        if not arquivo.exists():
            status = "sem correção"
            nota = "-"
        else:
            dados = carregar(arquivo)

            if (
                dados.get("avaliacao_id") != avaliacao["id"]
                or dados.get("aluno_id") != aluno["id"]
            ):
                status = "identificação divergente"
                nota = "-"
            else:
                status = dados["status"]
                nota_final = dados["nota_final"]
                nota = (
                    "-" if nota_final is None
                    else f"{nota_final:g}"
                )

        print(
            f"{aluno['id']} | "
            f"{status:24} | Nota: {nota}"
        )

def main():
    while True:
        print("\nGERENCIAMENTO DA TURMA")
        print("1 - Preparar pastas dos alunos")
        print("2 - Listar situação das correções")
        print("0 - Sair")

        opcao = input("Escolha: ").strip()

        if opcao == "1":
            preparar_turma()
        elif opcao == "2":
            listar_resultados()
        elif opcao == "0":
            break
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    main()
