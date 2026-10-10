
import copy
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


# ============================================================
# CONFIGURAÇÕES
# ============================================================

BASE = Path(__file__).resolve().parent

AVALIACAO = BASE / "avaliacao.json"
CADASTRO = BASE / "alunos.json"
PASTA_RESULTADOS = BASE / "resultados"


# ============================================================
# ARQUIVOS E IDENTIFICAÇÃO
# ============================================================

def carregar(caminho):
    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def identificador(valor):
    if (
        not isinstance(valor, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", valor)
    ):
        raise ValueError(
            f"Identificador inválido: {valor}"
        )

    return valor


def pasta_aluno(avaliacao_id, aluno_id):
    return (
        PASTA_RESULTADOS
        / identificador(avaliacao_id)
        / identificador(aluno_id)
    )


def salvar(dados, caminho):
    caminho.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporario = caminho.with_suffix(".tmp")

    with temporario.open(
        "w", encoding="utf-8"
    ) as arquivo:
        json.dump(
            dados,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    temporario.replace(caminho)


def criar_backup(caminho):
    if not caminho.exists():
        return

    historico = caminho.parent / "historico"

    historico.mkdir(
        parents=True,
        exist_ok=True
    )

    agora = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    destino = historico / f"correcao_{agora}.json"

    shutil.copy2(caminho, destino)

    return destino


def carregar_turma():
    avaliacao = carregar(AVALIACAO)
    cadastro = carregar(CADASTRO)

    if cadastro.get("turma") != avaliacao.get("turma"):
        raise ValueError(
            "A turma do cadastro é diferente "
            "da turma da avaliação."
        )

    identificador(avaliacao["id"])

    alunos = cadastro.get("alunos")

    if not isinstance(alunos, list) or not alunos:
        raise ValueError(
            "O cadastro não possui alunos."
        )

    ids = set()

    for aluno in alunos:
        aluno_id = identificador(aluno["id"])

        if aluno_id in ids:
            raise ValueError(
                f"Aluno duplicado: {aluno_id}"
            )

        if not str(aluno.get("nome", "")).strip():
            raise ValueError(
                f"Nome ausente: {aluno_id}"
            )

        ids.add(aluno_id)

    return avaliacao, alunos


# ============================================================
# VALIDAÇÃO DA LEITURA
# ============================================================

def validar_leitura(avaliacao, aluno, leitura):
    if leitura.get("avaliacao_id") != avaliacao["id"]:
        raise ValueError(
            "A leitura pertence a outra avaliação."
        )

    if leitura.get("aluno_id") != aluno["id"]:
        raise ValueError(
            "A leitura pertence a outro aluno."
        )

    chave = f'{avaliacao["id"]}:{aluno["id"]}'

    cartao_esperado = str(
        uuid5(NAMESPACE_URL, chave)
    )

    if leitura.get("cartao_id") != cartao_esperado:
        raise ValueError(
            "O UUID da leitura não corresponde "
            "à avaliação e ao aluno."
        )

    if not isinstance(leitura.get("respostas"), dict):
        raise ValueError(
            "A leitura não possui respostas válidas."
        )


# ============================================================
# ENTRADA DE NOTAS E REVISÕES
# ============================================================

def solicitar_nota(numero, maximo):
    while True:
        entrada = input(
            f"Nota da questão {numero} "
            f"(0 a {maximo:g}, Enter = pendente): "
        ).strip()

        if not entrada:
            return None

        try:
            nota = float(
                entrada.replace(",", ".")
            )

            if 0 <= nota <= maximo:
                return round(nota, 2)

        except ValueError:
            pass

        print("Nota inválida.")


def revisar_resposta(numero, alternativas):
    print(f"\nRevisão da questão {numero}")

    while True:
        entrada = input(
            "Alternativa A-E, "
            "0 = em branco, "
            "M = múltipla, "
            "Enter = pendente: "
        ).strip().upper()

        if entrada == "":
            return None, "pendente"

        if entrada == "0":
            return None, "em_branco"

        if entrada == "M":
            return None, "multipla"

        if entrada in alternativas:
            return entrada, "revisada"

        print("Opção inválida.")


# ============================================================
# CRIAÇÃO DO RESULTADO INICIAL
# ============================================================

def criar_resultado_inicial(avaliacao, aluno, leitura):
    questoes = []

    for definicao in avaliacao["questoes"]:
        numero = definicao["numero"]
        tipo = definicao["tipo"]

        item = {
            "numero": numero,
            "tipo": tipo,
            "pontos_possiveis": float(
                definicao["pontos"]
            ),
            "pontos_obtidos": None
        }

        if tipo == "objetiva":
            leitura_q = leitura["respostas"].get(
                str(numero)
            )

            if leitura_q is None:
                raise ValueError(
                    f"Leitura ausente: questão {numero}"
                )

            status = leitura_q["status"]
            resposta = leitura_q["resposta"]

            if status not in (
                "marcada",
                "em_branco",
                "multipla",
                "incerta"
            ):
                raise ValueError(
                    f"Status inválido na questão {numero}."
                )

            alternativas = definicao["alternativas"]

            if (
                status == "marcada"
                and resposta not in alternativas
            ):
                raise ValueError(
                    f"Resposta inválida na questão {numero}."
                )

            if (
                status != "marcada"
                and resposta is not None
            ):
                raise ValueError(
                    f"Resposta incompatível na questão {numero}."
                )

            item.update({
                "resposta": resposta,
                "gabarito": definicao["gabarito"],
                "status": status
            })

        elif tipo == "discursiva":
            item["status"] = "pendente"

        else:
            raise ValueError(
                f"Tipo desconhecido: {tipo}"
            )

        questoes.append(item)

    return {
        "avaliacao_id": avaliacao["id"],
        "cartao_id": leitura["cartao_id"],
        "aluno_id": aluno["id"],
        "aluno_nome": aluno["nome"],
        "questoes": questoes,
        "pontos_possiveis": 0,
        "pontos_confirmados": 0,
        "nota_final": None,
        "status": "pendente",
        "pendencias": []
    }


# ============================================================
# CÁLCULO DA PONTUAÇÃO
# ============================================================

def atualizar_pontuacao(resultado):
    total = 0.0
    confirmados = 0.0
    pendencias = []

    for q in resultado["questoes"]:
        total += q["pontos_possiveis"]

        if q["status"] in ("pendente", "incerta"):
            q["pontos_obtidos"] = None
            pendencias.append(q["numero"])
            continue

        if q["tipo"] == "objetiva":
            q["pontos_obtidos"] = (
                q["pontos_possiveis"]
                if q["resposta"] == q["gabarito"]
                else 0.0
            )

        if q["pontos_obtidos"] is None:
            pendencias.append(q["numero"])
        else:
            confirmados += q["pontos_obtidos"]

    resultado["pontos_possiveis"] = round(
        total, 2
    )

    resultado["pontos_confirmados"] = round(
        confirmados, 2
    )

    resultado["pendencias"] = pendencias

    resultado["status"] = (
        "pendente"
        if pendencias
        else "finalizada"
    )

    resultado["nota_final"] = (
        None
        if pendencias
        else round(confirmados, 2)
    )


# ============================================================
# CORREÇÃO DAS QUESTÕES
# ============================================================

def corrigir_questao(q, definicao):
    numero = q["numero"]

    if q["tipo"] == "discursiva":
        nota = solicitar_nota(
            numero,
            q["pontos_possiveis"]
        )

        q["pontos_obtidos"] = nota

        q["status"] = (
            "corrigida"
            if nota is not None
            else "pendente"
        )

    else:
        resposta, status = revisar_resposta(
            numero,
            definicao["alternativas"]
        )

        q["resposta"] = resposta
        q["status"] = status


# ============================================================
# EXIBIÇÃO DO RESUMO
# ============================================================

def mostrar_resumo(resultado):
    print("\nRESUMO DA CORREÇÃO")
    print("-" * 45)

    print("Aluno:", resultado["aluno_nome"])
    print("ID:", resultado["aluno_id"])

    print("-" * 45)

    for q in resultado["questoes"]:
        nota = q["pontos_obtidos"]

        texto_nota = (
            "-"
            if nota is None
            else f"{nota:g}"
        )

        print(
            f"Q{q['numero']:02d} | "
            f"{q['status']:12} | "
            f"{texto_nota}"
        )

    print("-" * 45)

    print(
        "Pontos confirmados:",
        resultado["pontos_confirmados"]
    )

    print(
        "Pontuação máxima:",
        resultado["pontos_possiveis"]
    )

    print(
        "Situação:",
        resultado["status"]
    )

    print(
        "Pendências:",
        resultado["pendencias"]
    )

    print(
        "Nota final:",
        resultado["nota_final"]
    )


# ============================================================
# CORREÇÃO INDIVIDUAL
# ============================================================

def corrigir_aluno(avaliacao, aluno):
    pasta = pasta_aluno(
        avaliacao["id"],
        aluno["id"]
    )

    caminho_leitura = (
        pasta / "resultado_leitura.json"
    )

    caminho_correcao = (
        pasta / "resultado_correcao.json"
    )

    print("\n" + "=" * 50)
    print("CORREÇÃO DE AVALIAÇÃO")
    print("=" * 50)
    print("Aluno:", aluno["nome"])
    print("ID:", aluno["id"])

    if not caminho_leitura.exists():
        print(
            "Sem leitura óptica. "
            "Correção não iniciada."
        )
        return

    leitura = carregar(caminho_leitura)

    validar_leitura(
        avaliacao,
        aluno,
        leitura
    )

    definicoes = {
        q["numero"]: q
        for q in avaliacao["questoes"]
    }

    if caminho_correcao.exists():
        resultado = carregar(caminho_correcao)

        if (
            resultado.get("avaliacao_id")
            != avaliacao["id"]
            or resultado.get("aluno_id")
            != aluno["id"]
            or resultado.get("cartao_id")
            != leitura["cartao_id"]
        ):
            raise ValueError(
                "A correção existente pertence "
                "a outro aluno ou cartão."
            )

        print("Correção anterior encontrada.")

        estado_anterior = copy.deepcopy(
            resultado
        )

    else:
        resultado = criar_resultado_inicial(
            avaliacao,
            aluno,
            leitura
        )

        estado_anterior = None

        print("Nova correção iniciada.")

    atualizar_pontuacao(resultado)

    # Corrige apenas questões pendentes ou incertas.
    for q in resultado["questoes"]:
        if q["status"] in ("pendente", "incerta"):
            corrigir_questao(
                q,
                definicoes[q["numero"]]
            )

    atualizar_pontuacao(resultado)
    mostrar_resumo(resultado)

    # Permite revisão manual de qualquer questão.
    while True:
        entrada = input(
            "\nRevisar questão? "
            "(número ou Enter para finalizar): "
        ).strip()

        if not entrada:
            break

        if not entrada.isdigit():
            print(
                "Informe o número da questão."
            )
            continue

        numero = int(entrada)

        item = next(
            (
                q
                for q in resultado["questoes"]
                if q["numero"] == numero
            ),
            None
        )

        if item is None:
            print("Questão não encontrada.")
            continue

        corrigir_questao(
            item,
            definicoes[numero]
        )

        atualizar_pontuacao(resultado)
        mostrar_resumo(resultado)

    # Salva somente se houver mudança.
    if estado_anterior is None:
        salvar(
            resultado,
            caminho_correcao
        )

        print(
            "\nNova correção salva com sucesso."
        )

    elif resultado != estado_anterior:
        criar_backup(caminho_correcao)

        salvar(
            resultado,
            caminho_correcao
        )

        print(
            "\nAlterações salvas com sucesso."
        )

    else:
        print(
            "\nNenhuma alteração realizada."
        )

        print(
            "O histórico foi preservado."
        )

    print(
        "\nArquivo de correção:",
        caminho_correcao
    )


# ============================================================
# SITUAÇÃO DA TURMA
# ============================================================

def listar_situacao(avaliacao, alunos):
    print("\nSITUAÇÃO DAS CORREÇÕES")
    print("-" * 65)

    for aluno in alunos:
        pasta = pasta_aluno(
            avaliacao["id"],
            aluno["id"]
        )

        leitura = (
            pasta / "resultado_leitura.json"
        )

        correcao = (
            pasta / "resultado_correcao.json"
        )

        if correcao.exists():
            dados = carregar(correcao)

            if (
                dados.get("avaliacao_id") != avaliacao["id"]
                or dados.get("aluno_id") != aluno["id"]
            ):
                situacao = "identificação divergente"
                nota = "-"
            else:
                situacao = dados.get(
                    "status", "desconhecido"
                )

                nota_final = dados.get("nota_final")

                nota = (
                    "-"
                    if nota_final is None
                    else f"{nota_final:g}"
                )

        elif leitura.exists():
            situacao = "aguardando correção"
            nota = "-"

        else:
            situacao = "sem leitura"
            nota = "-"

        print(
            f"{aluno['id']:12} | "
            f"{situacao:25} | "
            f"Nota: {nota}"
        )


# ============================================================
# MENU PRINCIPAL
# ============================================================

def main():
    avaliacao, alunos = carregar_turma()

    while True:
        print("\n" + "=" * 50)
        print("SISTEMA DE CORREÇÃO - MMC")
        print("=" * 50)

        print("Avaliação:", avaliacao["id"])
        print("Turma:", avaliacao["turma"])

        print("\n1 - Corrigir um aluno")
        print("2 - Corrigir todos os alunos")
        print("3 - Listar situação das correções")
        print("0 - Sair")

        opcao = input(
            "\nEscolha uma opção: "
        ).strip()

        if opcao == "1":
            print("\nALUNOS CADASTRADOS")

            for aluno in alunos:
                print(
                    f"{aluno['id']} | {aluno['nome']}"
                )

            aluno_id = input(
                "\nInforme o ID do aluno: "
            ).strip().upper()

            aluno = next(
                (
                    a
                    for a in alunos
                    if a["id"] == aluno_id
                ),
                None
            )

            if aluno is None:
                print("Aluno não encontrado.")
                continue

            try:
                corrigir_aluno(
                    avaliacao,
                    aluno
                )
            except (
                ValueError,
                KeyError,
                FileNotFoundError
            ) as erro:
                print("Erro:", erro)

        elif opcao == "2":
            print(
                "\nCorreção sequencial da turma."
            )

            confirmar = input(
                "Deseja continuar? (S/N): "
            ).strip().upper()

            if confirmar != "S":
                continue

            for aluno in alunos:
                try:
                    corrigir_aluno(
                        avaliacao,
                        aluno
                    )
                except (
                    ValueError,
                    KeyError,
                    FileNotFoundError
                ) as erro:
                    print(
                        f"Erro em {aluno['id']}: {erro}"
                    )

        elif opcao == "3":
            listar_situacao(
                avaliacao,
                alunos
            )

        elif opcao == "0":
            print("Programa encerrado.")
            break

        else:
            print("Opção inválida.")


if __name__ == "__main__":
    main()
